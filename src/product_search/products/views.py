from django.contrib.postgres.search import TrigramSimilarity, SearchQuery, SearchRank, SearchVector
from django.db.models import Q, F, Value
from django.db.models.functions import Greatest
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Product
from .serializers import ProductSerializer

class ProductSearchRateThrottle(AnonRateThrottle):
    rate = '30/minute'

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for searching products with advanced features:
    - Full-text and trigram search (handles partial keywords, misspellings, mixed languages)
    - Advanced filters (category, brand, nutrition)
    - Caching and rate limiting for performance
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    throttle_classes = [ProductSearchRateThrottle]

    @swagger_auto_schema(
        method='get',
        operation_description="Search products with support for partial keywords, misspellings, and mixed languages",
        manual_parameters=[
            openapi.Parameter(
                name='q', in_=openapi.IN_QUERY, description='Search query term', type=openapi.TYPE_STRING, required=True
            ),
            openapi.Parameter(
                name='category', in_=openapi.IN_QUERY, description='Filter by category name', type=openapi.TYPE_STRING, required=False
            ),
            openapi.Parameter(
                name='brand', in_=openapi.IN_QUERY, description='Filter by brand name', type=openapi.TYPE_STRING, required=False
            ),
            openapi.Parameter(
                name='max_calories', in_=openapi.IN_QUERY, description='Maximum calories value', type=openapi.TYPE_INTEGER, required=False
            ),
            openapi.Parameter(
                name='min_protein', in_=openapi.IN_QUERY, description='Minimum protein value', type=openapi.TYPE_INTEGER, required=False
            ),
            openapi.Parameter(
                name='search_type', in_=openapi.IN_QUERY, description='Type of search: "full_text" (default), "trigram", or "hybrid"', type=openapi.TYPE_STRING, required=False
            ),
        ],
        responses={
            200: ProductSerializer(many=True),
            400: 'Bad Request'
        }
    )
    @method_decorator(cache_page(60*15))  # Cache for 15 minutes
    @method_decorator(vary_on_cookie)
    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Advanced search endpoint with multiple search strategies:
        1. Full-text search (fastest for words and phrases)
        2. Trigram similarity (best for misspellings)
        3. Hybrid approach (combines both strategies)
        Supports advanced filters and is optimized for performance.
        """
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response(
                {"error": "Please provide a search query parameter 'q'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        search_type = request.query_params.get('search_type', 'full_text')
        english_part = ''.join(c for c in query if not ('\u0600' <= c <= '\u06FF'))
        arabic_part = ''.join(c for c in query if ('\u0600' <= c <= '\u06FF'))

        if search_type == 'trigram':
            search_results = self._trigram_search(english_part, arabic_part)
        elif search_type == 'hybrid':
            search_results = self._hybrid_search(query, english_part, arabic_part)
        else:
            search_results = self._full_text_search(query, english_part, arabic_part)

        search_results = self._apply_filters(search_results, request.query_params)
        search_results = search_results.select_related('category', 'brand')[:20]
        serializer = self.get_serializer(search_results, many=True)
        return Response(serializer.data)

    def _full_text_search(self, full_query, english_part, arabic_part):
        """
        PostgreSQL full-text search using tsquery and tsvector
        Handles both English and Arabic queries using a unified search_vector.
        """
        combined_query = []
        if english_part:
            english_search_query = self._prepare_tsquery(english_part, 'english')
            combined_query.append(english_search_query)
        if arabic_part:
            arabic_search_query = self._prepare_tsquery(arabic_part, 'simple')
            combined_query.append(arabic_search_query)
        if len(combined_query) == 2:
            final_query = combined_query[0] | combined_query[1]
        elif len(combined_query) == 1:
            final_query = combined_query[0]
        else:
            return Product.objects.none()
        results = Product.objects.filter(
            search_vector=final_query
        ).annotate(
            rank=SearchRank(F('search_vector'), final_query)
        ).order_by('-rank')
        if results.exists():
            return results
        return self._fallback_search(full_query, english_part, arabic_part)

    def _prepare_tsquery(self, query, config='english'):
        """
        Prepare a tsquery for partial matching and special operators.
        """
        words = query.replace("'", "").replace('"', '').strip().split()
        if not words:
            return SearchQuery('')
        search_query = None
        for word in words:
            if len(word) < 2:
                continue
            word_query = SearchQuery(f"{word}:*", search_type='raw', config=config)
            if search_query is None:
                search_query = word_query
            else:
                search_query = search_query | word_query
        return search_query or SearchQuery('')

    def _trigram_search(self, english_part, arabic_part):
        """
        Trigram similarity search for handling misspellings and partial matches.
        """
        en_threshold = 0.05 if len(english_part) <= 2 else 0.1
        ar_threshold = 0.05 if len(arabic_part) <= 2 else 0.1
        queryset = Product.objects.all()
        similarity_expressions = []
        if english_part:
            queryset = queryset.annotate(
                name_en_sim=TrigramSimilarity('name_en', english_part),
                desc_en_sim=TrigramSimilarity('description_en', english_part) * 0.5
            )
            similarity_expressions.extend(['name_en_sim', 'desc_en_sim'])
        if arabic_part:
            queryset = queryset.annotate(
                name_ar_sim=TrigramSimilarity('name_ar', arabic_part),
                desc_ar_sim=TrigramSimilarity('description_ar', arabic_part) * 0.5
            )
            similarity_expressions.extend(['name_ar_sim', 'desc_ar_sim'])
        if not similarity_expressions:
            return queryset.none()
        queryset = queryset.annotate(
            best_score=Greatest(*[F(expr) for expr in similarity_expressions], Value(0.0))
        )
        min_threshold = min(en_threshold, ar_threshold) if arabic_part and english_part else (en_threshold if english_part else ar_threshold)
        return queryset.filter(best_score__gt=min_threshold).order_by('-best_score')

    def _hybrid_search(self, full_query, english_part, arabic_part):
        """
        Hybrid search: try full-text first, then trigram if no results.
        """
        full_text_results = self._full_text_search(full_query, english_part, arabic_part)
        if full_text_results.exists():
            return full_text_results
        return self._trigram_search(english_part, arabic_part)

    def _fallback_search(self, full_query, english_part, arabic_part):
        """
        Fallback: ILIKE on name fields, then trigram.
        """
        combined_query = Q()
        if english_part:
            combined_query |= Q(name_en__icontains=english_part)
        if arabic_part:
            combined_query |= Q(name_ar__icontains=arabic_part)
        direct_matches = Product.objects.filter(combined_query)
        if direct_matches.exists():
            return direct_matches
        return self._trigram_search(english_part, arabic_part)

    def _apply_filters(self, queryset, params):
        """
        Apply advanced filters: category, brand, nutrition facts.
        """
        category = params.get('category')
        if category:
            queryset = queryset.filter(category__name__icontains=category)
        brand = params.get('brand')
        if brand:
            queryset = queryset.filter(brand__name__icontains=brand)
        max_calories = params.get('max_calories')
        if max_calories:
            queryset = queryset.filter(nutrition_facts__calories__lte=int(max_calories))
        min_protein = params.get('min_protein')
        if min_protein:
            queryset = queryset.filter(nutrition_facts__protein__gte=int(min_protein))
        return queryset
