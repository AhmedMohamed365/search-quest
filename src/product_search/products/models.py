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
    search_vector = SearchVectorField(null=True)
    
    nutrition_facts = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'], name='prod_search_idx'),
        ]
        
    def save(self, *args, **kwargs):
        # We'll let the database trigger handle the search vector update
        super().save(*args, **kwargs)