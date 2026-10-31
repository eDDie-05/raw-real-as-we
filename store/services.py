from urllib.parse import quote

from django.utils import timezone

WHATSAPP_NUMBER = "255775794221"


def format_tzs(amount):
    return f"TZS {amount:,.0f}"


def build_whatsapp_message(order):
    lines = [
        "Hello RAW! I would like to place an order.",
        "",
        f"ORDER REFERENCE: {order.reference}",
        "",
        "CUSTOMER DETAILS:",
        f"Name: {order.customer_name}",
        f"Phone: {order.phone}",
        f"Location: {order.region}, {order.city}",
        f"Address: {order.address}",
        "",
        "ORDER DETAILS:",
    ]
    for item in order.items.all():
        lines.extend([
            "",
            f"Product: {item.product_name}",
            f"Size: {item.size}",
            f"Colour: {item.colour}",
            f"Quantity: {item.quantity}",
            f"Unit Price: {format_tzs(item.unit_price)}",
            f"Subtotal: {format_tzs(item.line_total)}",
        ])
    lines.extend([
        "",
        "ORDER SUMMARY:",
        f"Subtotal: {format_tzs(order.subtotal)}",
        f"Delivery: {format_tzs(order.delivery_fee) if order.delivery_fee is not None else 'To be confirmed'}",
        f"Total: {format_tzs(order.total)}",
        "",
        "Please confirm availability and provide payment and delivery instructions.",
        "Thank you for choosing RAW.",
    ])
    return "\n".join(lines)


def whatsapp_url(order):
    return f"https://wa.me/{WHATSAPP_NUMBER}?text={quote(build_whatsapp_message(order), safe='')}"


def mark_whatsapp_opened(order):
    order.whatsapp_opened_at = timezone.now()
    order.save(update_fields=["whatsapp_opened_at", "updated_at"])
