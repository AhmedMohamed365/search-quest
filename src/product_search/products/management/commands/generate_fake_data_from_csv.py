from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker
import random
from products.models import Product, Category, Brand
import os
import sys
import csv
sys.path.append(os.path.join(os.path.dirname(__file__), 'assets'))
from translation_model import translate_text
# Setup Django environment
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "product_search.settings")
# django.setup()

# Now import Django models

# Add the assets directory to sys.path for import

# Custom fallback dictionary for common food/ingredient words
CUSTOM_TRANSLATIONS = {
    "protein": "بروتين",
    "egg": "بيض",
    "chicken": "دجاج",
    "beef": "لحم بقري",
    "apple": "تفاح",
    "banana": "موز",
    "oats": "شوفان",
    "milk": "حليب",
    "cheese": "جبن",
    "rice": "أرز",
    "bread": "خبز",
    "butter": "زبدة",
    "yogurt": "زبادي",
    "quinoa": "كينوا",
    "carrot": "جزر",
    "grapes": "عنب",
    "orange": "برتقال",
    "cookies": "بسكويت",
    "nuts": "مكسرات",
    "snack": "وجبة خفيفة",
    "meat": "لحم",
    "fish": "سمك",
    "salmon": "سلمون",
    "pasta": "معكرونة",
    "potato": "بطاطس",
    "spinach": "سبانخ",
    "strawberry": "فراولة",
    "water": "ماء",
    "juice": "عصير",
    "coffee": "قهوة",
    "tea": "شاي",
    "bar": "بار",
    "snacks": "وجبات خفيفة",
    "dairy": "منتجات الألبان",
    "vegetables": "خضروات",
    "fruits": "فواكه",
    "grains": "حبوب",
    "beverages": "مشروبات",
}

# Simple English to Arabic character transliteration map
EN_AR_CHAR_MAP = {
    'a': 'ا', 'b': 'ب', 'c': 'ك', 'd': 'د', 'e': 'ي', 'f': 'ف', 'g': 'ج', 'h': 'ه', 'i': 'ي', 'j': 'ج',
    'k': 'ك', 'l': 'ل', 'm': 'م', 'n': 'ن', 'o': 'و', 'p': 'ب', 'q': 'ق', 'r': 'ر', 's': 'س', 't': 'ت',
    'u': 'و', 'v': 'ف', 'w': 'و', 'x': 'كس', 'y': 'ي', 'z': 'ز',
    'A': 'ا', 'B': 'ب', 'C': 'ك', 'D': 'د', 'E': 'ي', 'F': 'ف', 'G': 'ج', 'H': 'ه', 'I': 'ي', 'J': 'ج',
    'K': 'ك', 'L': 'ل', 'M': 'م', 'N': 'ن', 'O': 'و', 'P': 'ب', 'Q': 'ق', 'R': 'ر', 'S': 'س', 'T': 'ت',
    'U': 'و', 'V': 'ف', 'W': 'و', 'X': 'كس', 'Y': 'ي', 'Z': 'ز',
}

def transliterate_en_ar(text):
    # Transliterates each character to its Arabic equivalent
    return ''.join(EN_AR_CHAR_MAP.get(c, c) for c in text)

def smart_translate(text, from_code, to_code):
    translated = translate_text(text, from_code, to_code)
    replaced = False
    if translated.strip().lower() == text.strip().lower():
        # Try to replace known words
        for en_word, ar_word in CUSTOM_TRANSLATIONS.items():
            if en_word.lower() in text.lower():
                replaced = True
                # Replace whole word (case-insensitive)
                translated = text
                for word in text.split():
                    lw = word.lower()
                    if lw in CUSTOM_TRANSLATIONS:
                        translated = translated.replace(word, CUSTOM_TRANSLATIONS[lw])
                break
    if not replaced and translated.strip().lower() == text.strip().lower():
        # Fallback: transliterate
        translated = transliterate_en_ar(text)
    return translated

class Command(BaseCommand):
    help = 'Import nutrition data from CSV, translate names, and insert into DB.'

    def add_arguments(self, parser):
        parser.add_argument('--csv-path', type=str, default=os.path.join(os.path.dirname(__file__), 'assets/Dataset/daily_food_nutrition_dataset.csv'), help='Path to the CSV file')
        parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for bulk creation')

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        batch_size = options['batch_size']
        self.stdout.write(f'Loading data from {csv_path}...')
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            products = []
            categories = {}
            brands = {}
            for row in reader:
                # Category
                cat_name_en = row['Category']
                cat_name_ar = smart_translate(cat_name_en, 'en', 'ar')
                if cat_name_en not in categories:
                    cat_obj, _ = Category.objects.get_or_create(name=cat_name_en)
                    categories[cat_name_en] = cat_obj
                category = categories[cat_name_en]

                # Brand (use Food_Item as brand if no brand info)
                brand_name = row.get('Brand', row['Food_Item'])
                if brand_name not in brands:
                    brand_obj, _ = Brand.objects.get_or_create(name=brand_name)
                    brands[brand_name] = brand_obj
                brand = brands[brand_name]

                # Product names
                name_en = row['Food_Item']
                name_ar = smart_translate(name_en, 'en', 'ar')
                desc_en = f"{name_en} ({cat_name_en})"
                desc_ar = smart_translate(desc_en, 'en', 'ar')

                # Nutrition facts
                nutrition_facts = {
                    'calories': float(row['Calories (kcal)']),
                    'protein_g': float(row['Protein (g)']),
                    'carbs_g': float(row['Carbohydrates (g)']),
                    'fat_g': float(row['Fat (g)']),
                    'fiber_g': float(row['Fiber (g)']),
                    'sugar_g': float(row['Sugars (g)']),
                    'sodium_mg': float(row['Sodium (mg)']),
                    'cholesterol_mg': float(row['Cholesterol (mg)']),
                    'water_ml': float(row['Water_Intake (ml)']),
                }

                products.append(Product(
                    name_en=name_en,
                    name_ar=name_ar,
                    description_en=desc_en,
                    description_ar=desc_ar,
                    category=category,
                    brand=brand,
                    nutrition_facts=nutrition_facts
                ))

                if len(products) >= batch_size:
                    Product.objects.bulk_create(products)
                    products = []

            if products:
                Product.objects.bulk_create(products)
        self.stdout.write(self.style.SUCCESS('CSV data import complete!'))
        # Show a few products
        for prod in Product.objects.all()[:5]:
            self.stdout.write(f"EN: {prod.name_en} | AR: {prod.name_ar} | Nutrition: {prod.nutrition_facts}")
