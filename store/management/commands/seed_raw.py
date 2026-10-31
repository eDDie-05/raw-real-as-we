from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from store.models import Category, Product, ProductImage, ProductVariant


CATALOG = [
    ("Men", "men", 1),
    ("Women", "women", 2),
    ("Streetwear", "streetwear", 3),
    ("New Arrivals", "new-arrivals", 4),
    ("Limited Edition", "limited-edition", 5),
]

PRODUCTS = [
    ("RAW Signature Red Tee", "RAW-TEE-RED", "streetwear", "product-red-tee.webp", "A statement tee from RAW. Real as we. Inspired by the fear of being average.", 35000, True, True),
    ("RAW Essential White Tee", "RAW-TEE-WHT", "men", "product-white-tee.webp", "A clean everyday essential with RAW identity and an easy, confident fit.", 35000, True, False),
    ("RAW KOIOPHOBIA Hoodie", "RAW-HD-KOI", "limited-edition", "product-koio-hoodie.webp", "A warm layer carrying the KOIOPHOBIA statement. Wear your identity.", 65000, True, True),
    ("RAW Black Hoodie", "RAW-HD-BLK", "streetwear", "product-black-hoodie.webp", "A versatile heavyweight-inspired streetwear layer in black.", 65000, True, False),
    ("RAW Graphic Black Tee", "RAW-TEE-BLK", "new-arrivals", "product-black-tee.webp", "Original RAW graphic tee. Not made to blend in.", 35000, True, False),
    ("RAW Identity Tee", "RAW-TEE-ID", "women", "product-white-model.webp", "A minimal piece for bold self-expression. Be original. Be real. Be RAW.", 35000, False, True),
]


class Command(BaseCommand):
    help = "Create an editable starter catalogue from the supplied RAW campaign assets."

    def handle(self, *args, **options):
        categories = {}
        for name, slug, order in CATALOG:
            category, _ = Category.objects.update_or_create(
                slug=slug, defaults={"name": name, "sort_order": order, "is_active": True}
            )
            categories[slug] = category
        image_root = Path(settings.BASE_DIR) / "store" / "static" / "store" / "images"
        for name, sku, category_slug, image_name, description, price, new, featured in PRODUCTS:
            product, _ = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "slug": slugify(name),
                    "category": categories[category_slug],
                    "description": description,
                    "price": Decimal(price),
                    "discounted_price": None,
                    "is_active": True,
                    "is_new_arrival": new,
                    "is_featured": featured,
                    "is_best_seller": sku in {"RAW-TEE-RED", "RAW-HD-KOI"},
                },
            )
            for size in ("S", "M", "L", "XL"):
                ProductVariant.objects.update_or_create(
                    product=product, size=size, colour="Black" if "Black" in name or "Hoodie" in name else "White",
                    defaults={"sku": f"{sku}-{size}", "stock": 5, "is_active": True},
                )
            if not product.images.exists():
                path = image_root / image_name
                with path.open("rb") as source:
                    ProductImage.objects.create(
                        product=product,
                        image=File(source, name=path.name),
                        alt_text=f"{name} — RAW campaign photograph",
                        is_primary=True,
                    )
        self.stdout.write(self.style.SUCCESS(
            "Starter RAW catalogue created. Review sample prices and stock in Django Admin before taking orders."
        ))
