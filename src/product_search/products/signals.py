from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.postgres.search import SearchVector
from .models import Product

@receiver(post_save, sender=Product)
def update_search_vectors(sender, instance, **kwargs):
    """
    Update the search vectors when a product is saved
    """
    # Update without triggering the signal again
    Product.objects.filter(pk=instance.pk).update(
        search_vector_en=SearchVector('name_en', weight='A') + 
                         SearchVector('description_en', weight='B'),
        search_vector_ar=SearchVector('name_ar', weight='A') + 
                         SearchVector('description_ar', weight='B')
    ) 