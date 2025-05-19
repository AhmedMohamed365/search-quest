from django.shortcuts import render
from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from django.db.models import Q, F, Value
from django.db.models.functions import Greatest
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Product, Category, Brand
from .serializers import ProductSerializer

class ProductSearchRateThrottle(AnonRateThrottle):
    rate = '30/minute'

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for searching products with advanced features.
    Includes rate limiting, caching, and advanced filters.
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    throttle_classes = [ProductSearchRateThrottle]
    
    @swagger_auto_schema(
        method='get',
        operation_description="Search products with support for partial keywords, misspellings, and mixed languages",
        manual_parameters=[
            openapi.Parameter(
                name='q',
                in_=openapi.IN_QUERY,
                description='Search query term',
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                name='category',
                in_=openapi.IN_QUERY,
                description='Filter by category name',
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                name='brand',
                in_=openapi.IN_QUERY,
                description='Filter by brand name',
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                name='max_calories',
                in_=openapi.IN_QUERY,
                description='Maximum calories value',
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                name='min_protein',
                in_=openapi.IN_QUERY,
                description='Minimum protein value',
                type=openapi.TYPE_INTEGER,
                required=False
            ),
        ],
        responses={
            200: ProductSerializer(many=True),
            400: 'Bad Request'
        }
    )
    @method_decorator(cache_page(60*5))  # Cache for 5 minutes
    @method_decorator(vary_on_cookie)
    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Search products with support for:
        - Partial keywords
        - Misspellings (using trigram similarity)
        - Mixed language (English/Arabic)
        - Advanced filtering by category, brand, nutrition facts
        """
        query = request.query_params.get('q', '')
        if not query:
            return Response(
                {"error": "Please provide a search query parameter 'q'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine if query contains Arabic characters
        has_arabic = any('\u0600' <= c <= '\u06FF' for c in query)
        
        # For mixed-language queries, we need to split and handle each part
        english_part = ''.join(c for c in query if not ('\u0600' <= c <= '\u06FF'))
        arabic_part = ''.join(c for c in query if '\u0600' <= c <= '\u06FF')
        
        # Search with individual parts
        search_results = self._search_products(query, english_part, arabic_part)
        
        # Apply filters
        search_results = self._apply_filters(search_results, request.query_params)
        
        serializer = self.get_serializer(search_results, many=True)
        return Response(serializer.data)
    
    def _search_products(self, full_query, english_part='', arabic_part=''):
        """
        Perform the actual search using PostgreSQL full-text search
        with fallback to trigram similarity for misspellings
        """
        results = []
        
        # Try exact full-text search first with the full query
        search_query_en = SearchQuery(full_query)
        exact_matches_en = Product.objects.filter(search_vector_en=search_query_en)
        if exact_matches_en.exists():
            results.extend(list(exact_matches_en))
        
        # If we have Arabic characters, also search in Arabic
        if arabic_part:
            search_query_ar = SearchQuery(full_query)
            exact_matches_ar = Product.objects.filter(search_vector_ar=search_query_ar)
            if exact_matches_ar.exists():
                results.extend(list(exact_matches_ar))
        
        # If we found full-text matches, return them with proper ranking
        if results:
            result_ids = [result.id for result in results]
            return Product.objects.filter(id__in=result_ids).distinct()
        
        # No exact matches, use trigram similarity for fuzzy matching
        # Set a lower threshold for mixed language queries
        similarity_threshold = 0.1  # Lower threshold for mixed language
        
        # Create a combined query for English part
        combined_query = Q()
        
        # If we have an English part, search English fields
        if english_part:
            # Lower threshold for shorter queries
            if len(english_part) <= 2:
                similarity_threshold = 0.05
            
            # Add trigram similarity for English fields
            english_results = Product.objects.annotate(
                name_en_sim=TrigramSimilarity('name_en', english_part),
                desc_en_sim=TrigramSimilarity('description_en', english_part),
                eng_similarity=Greatest('name_en_sim', 'desc_en_sim')
            ).filter(eng_similarity__gt=similarity_threshold)
            
            if english_results.exists():
                combined_query |= Q(id__in=[p.id for p in english_results])
        
        # If we have an Arabic part, search Arabic fields
        if arabic_part:
            # Add trigram similarity for Arabic fields
            arabic_results = Product.objects.annotate(
                name_ar_sim=TrigramSimilarity('name_ar', arabic_part),
                desc_ar_sim=TrigramSimilarity('description_ar', arabic_part),
                ar_similarity=Greatest('name_ar_sim', 'desc_ar_sim')
            ).filter(ar_similarity__gt=similarity_threshold)
            
            if arabic_results.exists():
                combined_query |= Q(id__in=[p.id for p in arabic_results])
        
        # If we found similarity matches
        if combined_query:
            return Product.objects.filter(combined_query).distinct()
        
        # Last resort: partial matching
        combined_query = Q()
        
        if english_part:
            combined_query |= Q(name_en__icontains=english_part) | Q(description_en__icontains=english_part)
        
        if arabic_part:
            combined_query |= Q(name_ar__icontains=arabic_part) | Q(description_ar__icontains=arabic_part)
        
        # If no parts matched, try with the full query
        if not combined_query:
            combined_query = (
                Q(name_en__icontains=full_query) | 
                Q(description_en__icontains=full_query) |
                Q(name_ar__icontains=full_query) | 
                Q(description_ar__icontains=full_query)
            )
        
        return Product.objects.filter(combined_query).distinct()
    
    def _apply_filters(self, queryset, params):
        """Apply advanced filters based on query parameters"""
        # Filter by category
        category = params.get('category')
        if category:
            queryset = queryset.filter(category__name__icontains=category)
        
        # Filter by brand
        brand = params.get('brand')
        if brand:
            queryset = queryset.filter(brand__name__icontains=brand)
        
        # Filter by nutrition facts (e.g. max_calories=100)
        max_calories = params.get('max_calories')
        if max_calories:
            queryset = queryset.filter(nutrition_facts__calories__lte=int(max_calories))
        
        min_protein = params.get('min_protein')
        if min_protein:
            queryset = queryset.filter(nutrition_facts__protein__gte=int(min_protein))
        
        # Add additional nutrition filters as needed
        
        return queryset
