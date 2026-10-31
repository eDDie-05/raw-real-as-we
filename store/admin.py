from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .forms import ProductImageAdminForm
from .models import (
    AuditLog, Cart, CartItem, Category, CustomerProfile, NewsletterSubscriber,
    Notification, Order, OrderItem, OrderStatusLog, Product, ProductImage,
    ProductVariant, Promotion, Review, ShippingAddress,
)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    form = ProductImageAdminForm
    extra = 1
    fields = ("image", "alt_text", "is_primary", "sort_order")


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ("sku", "size", "colour", "stock", "price_override", "is_active")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name", "sku", "category", "price", "discounted_price",
        "inventory_summary", "is_active", "is_featured", "is_new_arrival",
    )
    list_filter = ("category", "is_active", "is_featured", "is_new_arrival", "is_best_seller")
    search_fields = ("name", "sku", "description", "variants__sku")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("is_active", "is_featured", "is_new_arrival")
    inlines = (ProductImageInline, ProductVariantInline)
    save_on_top = True

    @admin.display(description="Units in stock")
    def inventory_summary(self, obj):
        return sum(obj.variants.values_list("stock", flat=True))


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "product_name", "sku", "size", "colour", "unit_price", "quantity", "line_total"
    )
    fields = readonly_fields

    @admin.display(description="Line total")
    def line_total(self, obj):
        return obj.line_total


class OrderStatusLogInline(admin.TabularInline):
    model = OrderStatusLog
    extra = 0
    can_delete = False
    readonly_fields = ("old_status", "new_status", "note", "changed_by", "created_at")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "reference", "customer_name", "phone", "status", "subtotal",
        "delivery_fee", "created_at",
    )
    list_filter = ("status", "created_at", "region")
    search_fields = ("reference", "customer_name", "phone", "email", "city")
    readonly_fields = (
        "reference", "public_token", "customer", "subtotal", "status",
        "whatsapp_opened_at", "confirmed_at", "created_at", "updated_at",
    )
    fields = (
        "reference", "public_token", "customer", "customer_name", "phone", "email",
        "region", "city", "address", "delivery_instructions", "subtotal",
        "delivery_fee", "status", "whatsapp_opened_at", "confirmed_at",
        "created_at", "updated_at",
    )
    inlines = (OrderItemInline, OrderStatusLogInline)
    actions = (
        "mark_confirmed", "mark_processing", "mark_ready",
        "mark_shipped", "mark_delivered", "mark_cancelled",
    )

    def _move(self, request, queryset, status, label):
        changed = 0
        for order in queryset:
            try:
                order.change_status(status, actor=request.user, note=f"Updated in admin: {label}.")
                changed += 1
            except ValidationError as error:
                self.message_user(
                    request, f"{order.reference}: {error}", level=messages.ERROR
                )
        if changed:
            self.message_user(request, f"{changed} order(s) moved to {label}.")

    @admin.action(description="Confirm selected orders (checks and reserves stock)")
    def mark_confirmed(self, request, queryset):
        self._move(request, queryset, Order.Status.CONFIRMED, "confirmed")

    @admin.action(description="Move selected orders to processing")
    def mark_processing(self, request, queryset):
        self._move(request, queryset, Order.Status.PROCESSING, "processing")

    @admin.action(description="Mark selected orders ready for dispatch")
    def mark_ready(self, request, queryset):
        self._move(request, queryset, Order.Status.READY, "ready for dispatch")

    @admin.action(description="Mark selected orders shipped")
    def mark_shipped(self, request, queryset):
        self._move(request, queryset, Order.Status.SHIPPED, "shipped")

    @admin.action(description="Mark selected orders delivered")
    def mark_delivered(self, request, queryset):
        self._move(request, queryset, Order.Status.DELIVERED, "delivered")

    @admin.action(description="Cancel selected orders (restores reserved stock)")
    def mark_cancelled(self, request, queryset):
        self._move(request, queryset, Order.Status.CANCELLED, "cancelled")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    form = ProductImageAdminForm
    list_display = ("product", "alt_text", "is_primary", "sort_order")
    list_filter = ("is_primary",)
    search_fields = ("product__name", "alt_text")


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("sku", "product", "size", "colour", "stock", "is_active")
    list_filter = ("is_active", "size", "colour", "product__category")
    search_fields = ("sku", "product__name", "colour")
    list_editable = ("stock", "is_active")


@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ("recipient", "user", "phone", "region", "city", "is_default")
    search_fields = ("recipient", "phone", "user__username", "city")


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "percent_off", "amount_off", "starts_at", "ends_at", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("email",)
    actions = ("unsubscribe",)

    @admin.action(description="Unsubscribe selected addresses")
    def unsubscribe(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "customer", "rating", "is_approved", "created_at")
    list_filter = ("is_approved", "rating")
    search_fields = ("product__name", "customer__username", "body")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("subject", "user", "email", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("subject", "email", "message")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "object_type", "object_id", "created_at")
    list_filter = ("action", "object_type", "created_at")
    search_fields = ("action", "object_type", "object_id")
    readonly_fields = ("actor", "action", "object_type", "object_id", "detail", "created_at")


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "updated_at")
    search_fields = ("user__username", "user__email", "phone")


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "is_active", "updated_at")
    list_filter = ("is_active",)
    inlines = (CartItemInline,)
