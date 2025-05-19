from rest_framework import serializers
from .models import Product, Brand, Category

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']

class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ['id', 'name']

class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name_en', 'name_ar', 'description_en', 'description_ar',
            'category', 'brand', 'nutrition_facts'
        ] 