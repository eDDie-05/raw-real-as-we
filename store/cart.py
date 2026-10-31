import uuid

from django.db import transaction

from .models import Cart, CartItem


def get_cart(request):
    raw_key = request.session.get("raw_cart_key")
    try:
        session_key = uuid.UUID(raw_key) if raw_key else uuid.uuid4()
    except (ValueError, TypeError, AttributeError):
        session_key = uuid.uuid4()
    request.session["raw_cart_key"] = str(session_key)

    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(
            owner=request.user,
            defaults={"session_key": session_key, "is_active": True},
        )
        guest_cart = Cart.objects.filter(
            session_key=session_key, owner__isnull=True, is_active=True
        ).first()
        if guest_cart and guest_cart.pk != cart.pk:
            with transaction.atomic():
                for item in guest_cart.items.select_related("variant"):
                    target, created = CartItem.objects.get_or_create(
                        cart=cart, variant=item.variant,
                        defaults={"quantity": item.quantity},
                    )
                    if not created:
                        target.quantity = min(target.quantity + item.quantity, 99)
                        target.save(update_fields=["quantity", "updated_at"])
                guest_cart.delete()
        return cart
    cart, _ = Cart.objects.get_or_create(
        session_key=session_key, defaults={"is_active": True}
    )
    return cart


def cart_count(request):
    if request.user.is_authenticated:
        cart = Cart.objects.filter(owner=request.user, is_active=True).first()
    else:
        raw_key = request.session.get("raw_cart_key")
        try:
            cart = Cart.objects.filter(session_key=uuid.UUID(raw_key), is_active=True).first()
        except (ValueError, TypeError, AttributeError):
            cart = None
    return cart.item_count if cart else 0
