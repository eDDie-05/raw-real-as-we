from decimal import Decimal
from urllib.parse import urlparse, parse_qs

from django.test import TestCase
from django.urls import reverse

from .models import (
    CartItem, Category, Order, OrderItem, OrderStatusLog, Product, ProductVariant,
)
from .services import build_whatsapp_message


class StorefrontTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Streetwear", slug="streetwear")
        self.product = Product.objects.create(
            name="RAW Tee", slug="raw-tee", sku="RAW-TEE", category=self.category,
            description="Wear your identity.", price=Decimal("35000.00"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, sku="RAW-TEE-M-BLK", size="M", colour="Black", stock=4,
        )

    def add_to_bag(self, quantity=2):
        return self.client.post(reverse("cart_add"), {
            "variant_id": self.variant.pk, "quantity": quantity,
        })

    def checkout_data(self):
        return {
            "customer_name": "Test Customer", "phone": "+255 700 000 000",
            "email": "customer@example.com", "region": "Dar es Salaam",
            "city": "Dar es Salaam", "address": "City Centre",
            "delivery_instructions": "Call on arrival",
        }

    def test_store_pages_and_catalog_filter(self):
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
        response = self.client.get(reverse("shop"), {"q": "tee", "size": "M"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "RAW Tee")
        self.assertEqual(self.client.get(self.product.get_absolute_url()).status_code, 200)

    def test_cart_rejects_overstock_without_creating_item(self):
        response = self.add_to_bag(5)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CartItem.objects.exists())
        self.add_to_bag(2)
        self.assertEqual(CartItem.objects.get().quantity, 2)

    def test_checkout_creates_pending_order_before_whatsapp(self):
        self.add_to_bag(2)
        response = self.client.post(reverse("checkout"), self.checkout_data())
        order = Order.objects.get()
        self.assertRedirects(response, reverse("order_review", args=[order.public_token]), fetch_redirect_response=False)
        self.assertEqual(order.status, Order.Status.PENDING_WHATSAPP)
        self.assertEqual(order.subtotal, Decimal("70000.00"))
        self.assertEqual(order.items.get().quantity, 2)
        self.assertEqual(self.variant.__class__.objects.get(pk=self.variant.pk).stock, 4)
        self.assertEqual(OrderStatusLog.objects.filter(order=order).count(), 1)
        review = self.client.get(reverse("order_review", args=[order.public_token]))
        self.assertContains(review, "REVIEW & SEND IN WHATSAPP")
        self.assertIn("wa.me/255775794221", review.content.decode())

    def test_whatsapp_message_has_multiple_lines_and_encoded_link(self):
        self.add_to_bag(1)
        self.client.post(reverse("checkout"), self.checkout_data())
        order = Order.objects.get()
        OrderItem.objects.create(
            order=order, variant=self.variant, product_name="RAW Hoodie", sku="HD-M",
            size="M", colour="Black", unit_price=Decimal("65000"), quantity=1,
        )
        order.subtotal += Decimal("65000")
        order.save(update_fields=["subtotal"])
        message = build_whatsapp_message(order)
        self.assertIn("RAW-", message)
        self.assertIn("RAW Tee", message)
        self.assertIn("RAW Hoodie", message)
        self.assertIn("Total: TZS 100,000", message)
        response = self.client.get(reverse("whatsapp_order", args=[order.public_token]))
        parsed = urlparse(response.url)
        self.assertEqual(parsed.netloc, "wa.me")
        self.assertIn("ORDER REFERENCE", parse_qs(parsed.query)["text"][0])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING_WHATSAPP)
        self.assertIsNotNone(order.whatsapp_opened_at)

    def test_confirming_and_cancelling_reserves_then_restores_stock(self):
        self.add_to_bag(2)
        self.client.post(reverse("checkout"), self.checkout_data())
        order = Order.objects.get()
        order.change_status(Order.Status.CONFIRMED, note="Confirmed by customer")
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 2)
        order.change_status(Order.Status.CANCELLED, note="Cancelled")
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 4)
        self.assertEqual(OrderStatusLog.objects.filter(order=order).count(), 3)
