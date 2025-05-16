from django.db import models
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField

class Category(models.Model):
    name = models.CharField(max_length=100)
    def __str__(self): return self.name

class Brand(models.Model):
    name = models.CharField(max_length=100)
    def __str__(self): return self.name

class Product(models.Model):
    name_en = models.CharField(max_length=200)
    name_ar = models.CharField(max_length=200)
    description_en = models.TextField()
    description_ar = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE)
    # For full-text search vector
    search_vector_en = SearchVectorField(null=True)
    search_vector_ar = SearchVectorField(null=True)

    class Meta:
        indexes = [
        GinIndex(fields=['search_vector_en'], name='prod_search_en_idx'),
        GinIndex(fields=['search_vector_ar'], name='prod_search_ar_idx'),
        ]