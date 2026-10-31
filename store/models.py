import uuid
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    sku = models.CharField(max_length=40, unique=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    discounted_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    is_best_seller = models.BooleanField(default=False)
    published_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-is_featured", "-published_at", "name"]
        indexes = [
            models.Index(fields=["is_active", "published_at"]),
            models.Index(fields=["category", "is_active"]),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse("product_detail", kwargs={"slug": self.slug})

    @property
    def current_price(self):
        return self.discounted_price if self.discounted_price is not None else self.price

    def clean(self):
        super().clean()
        if self.discounted_price is not None and self.discounted_price >= self.price:
            raise ValidationError({"discounted_price": "The sale price must be lower than the regular price."})

    @property
    def in_stock(self):
        return self.variants.filter(stock__gt=0, is_active=True).exists()

    @property
    def primary_image(self):
        return self.images.filter(is_primary=True).first() or self.images.first()


def product_image_path(instance, filename):
    suffix = Path(filename).suffix.lower()[:10] or ".jpg"
    return f"products/{instance.product_id}/{uuid.uuid4().hex}{suffix}"


class ProductImage(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=product_image_path)
    alt_text = models.CharField(max_length=180, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def clean(self):
        super().clean()
        if not self.image:
            return
        if self.image.size > 10 * 1024 * 1024:
            raise ValidationError({"image": "Images must be 10 MB or smaller."})
        try:
            self.image.seek(0)
            with Image.open(self.image) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValidationError({"image": "Upload a JPEG, PNG, or WebP image."})
                image.verify()
            self.image.seek(0)
        except (UnidentifiedImageError, OSError):
            raise ValidationError({"image": "This file is not a valid image."})

    def save(self, *args, **kwargs):
        self.full_clean()
        with transaction.atomic():
            if self.is_primary:
                ProductImage.objects.filter(product=self.product, is_primary=True).exclude(
                    pk=self.pk
                ).update(is_primary=False)
            elif not ProductImage.objects.filter(
                product=self.product, is_primary=True
            ).exclude(pk=self.pk).exists():
                self.is_primary = True
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product} image"


class ProductVariant(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=50, unique=True)
    size = models.CharField(max_length=24)
    colour = models.CharField(max_length=40)
    stock = models.PositiveIntegerField(default=0)
    price_override = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["size", "colour"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "size", "colour"], name="unique_product_size_colour"
            )
        ]

    def __str__(self):
        return f"{self.product.name} · {self.size} · {self.colour}"

    @property
    def current_price(self):
        return self.price_override if self.price_override is not None else self.product.current_price

    @property
    def available(self):
        return self.is_active and self.product.is_active and self.stock > 0


class Cart(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
        related_name="raw_carts",
    )
    session_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["owner", "is_active"])]

    def __str__(self):
        return f"Cart {self.pk}"

    @property
    def subtotal(self):
        return sum(
            (item.variant.current_price * item.quantity for item in self.items.select_related(
                "variant__product"
            )),
            Decimal("0.00"),
        )

    @property
    def item_count(self):
        return sum(self.items.values_list("quantity", flat=True))


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="cart_items")
    quantity = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "variant"], name="unique_cart_variant"),
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="cart_qty_positive"),
        ]

    def __str__(self):
        return f"{self.quantity} × {self.variant}"


class CustomerProfile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="raw_profile"
    )
    phone = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f"RAW profile: {self.user}"


class ShippingAddress(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="raw_addresses"
    )
    label = models.CharField(max_length=50, default="Home")
    recipient = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    region = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=240)
    delivery_instructions = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_default", "label"]

    def __str__(self):
        return f"{self.label} · {self.city}"


class Promotion(TimeStampedModel):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40, unique=True, blank=True)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    percent_off = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    amount_off = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING_WHATSAPP = "pending_whatsapp", "Pending WhatsApp confirmation"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready for dispatch"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    reference = models.CharField(max_length=32, unique=True, default="", editable=False)
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="raw_orders",
    )
    customer_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    region = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=240)
    delivery_instructions = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.PENDING_WHATSAPP
    )
    whatsapp_opened_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["phone", "-created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            stamp = timezone.localtime().strftime("%y%m%d")
            self.reference = f"RAW-{stamp}-{uuid.uuid4().hex[:6].upper()}"
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.reference

    @property
    def total(self):
        return self.subtotal + (self.delivery_fee or Decimal("0.00"))

    @property
    def inventory_committed(self):
        return self.status in {
            self.Status.CONFIRMED, self.Status.PROCESSING, self.Status.READY,
            self.Status.SHIPPED, self.Status.DELIVERED,
        }

    @transaction.atomic
    def change_status(self, new_status, actor=None, note=""):
        locked = Order.objects.select_for_update().get(pk=self.pk)
        if new_status not in self.Status.values:
            raise ValidationError("Choose a valid order status.")
        was_committed = locked.inventory_committed
        will_be_committed = new_status in {
            self.Status.CONFIRMED, self.Status.PROCESSING, self.Status.READY,
            self.Status.SHIPPED, self.Status.DELIVERED,
        }
        items = list(locked.items.select_related("variant").select_for_update())
        if not was_committed and will_be_committed:
            for item in items:
                if item.variant.stock < item.quantity:
                    raise ValidationError(
                        f"Not enough stock for {item.product_name} ({item.size}, {item.colour})."
                    )
            for item in items:
                item.variant.stock -= item.quantity
                item.variant.save(update_fields=["stock", "updated_at"])
        elif was_committed and not will_be_committed:
            for item in items:
                item.variant.stock += item.quantity
                item.variant.save(update_fields=["stock", "updated_at"])
        old_status = locked.status
        locked.status = new_status
        if new_status == self.Status.CONFIRMED and not locked.confirmed_at:
            locked.confirmed_at = timezone.now()
        locked.save(update_fields=["status", "confirmed_at", "updated_at"])
        OrderStatusLog.objects.create(
            order=locked, old_status=old_status, new_status=new_status,
            note=note, changed_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
        self.refresh_from_db()
        return self


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name="order_items"
    )
    product_name = models.CharField(max_length=160)
    sku = models.CharField(max_length=50)
    size = models.CharField(max_length=24)
    colour = models.CharField(max_length=40)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"


class OrderStatusLog(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    old_status = models.CharField(max_length=24, blank=True)
    new_status = models.CharField(max_length=24, choices=Order.Status.choices)
    note = models.CharField(max_length=240, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Review(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="raw_reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)], choices=[(n, str(n)) for n in range(1, 6)]
    )
    title = models.CharField(max_length=120, blank=True)
    body = models.TextField()
    is_approved = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "customer"], name="one_review_per_customer")
        ]

    def __str__(self):
        return f"{self.product} · {self.rating}/5"


class NewsletterSubscriber(TimeStampedModel):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.email


class Notification(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
        related_name="raw_notifications",
    )
    email = models.EmailField(blank=True)
    subject = models.CharField(max_length=140)
    message = models.TextField()
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return self.subject


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=120)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=80, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} · {self.created_at:%Y-%m-%d %H:%M}"
