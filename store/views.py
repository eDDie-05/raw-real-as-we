from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Max, Min, Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .cart import get_cart
from .forms import CheckoutForm, NewsletterForm, ProductImageAdminForm, SignUpForm
from .models import (
    AuditLog, CartItem, Category, CustomerProfile, NewsletterSubscriber, Order,
    OrderItem, OrderStatusLog, Product, ProductVariant, ShippingAddress,
)
from .services import build_whatsapp_message, format_tzs, whatsapp_url

GALLERY_ASSETS = json.loads(
    (Path(__file__).resolve().parent / "gallery_assets.json").read_text(encoding="utf-8")
)


def home(request):
    products = Product.objects.filter(is_active=True).prefetch_related("images", "variants")
    context = {
        "featured_products": products.filter(is_featured=True)[:4],
        "new_products": products.filter(is_new_arrival=True)[:4],
        "best_sellers": products.filter(is_best_seller=True)[:6],
        "categories": Category.objects.filter(is_active=True)[:6],
    }
    return render(request, "store/home.html", context)


def shop(request, category_slug=None):
    products = Product.objects.filter(is_active=True).select_related("category").prefetch_related(
        "images", "variants"
    )
    category = None
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug, is_active=True)
        products = products.filter(category=category)
    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
            | Q(sku__icontains=query) | Q(category__name__icontains=query)
        )
    selected_size = request.GET.get("size", "").strip()
    if selected_size:
        products = products.filter(variants__size__iexact=selected_size, variants__stock__gt=0)
    selected_colour = request.GET.get("colour", "").strip()
    if selected_colour:
        products = products.filter(
            variants__colour__iexact=selected_colour, variants__stock__gt=0
        )
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()
    try:
        if min_price:
            products = products.filter(price__gte=Decimal(min_price))
    except InvalidOperation:
        min_price = ""
    try:
        if max_price:
            products = products.filter(price__lte=Decimal(max_price))
    except InvalidOperation:
        max_price = ""
    sort = request.GET.get("sort", "newest")
    ordering = {
        "price-low": "price",
        "price-high": "-price",
        "name": "name",
        "newest": "-published_at",
    }.get(sort, "-published_at")
    products = products.distinct().order_by(ordering)
    paginator = Paginator(products, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "store/shop.html", {
        "page_obj": page_obj,
        "products": page_obj.object_list,
        "category": category,
        "categories": Category.objects.filter(is_active=True),
        "query": query,
        "selected_size": selected_size,
        "selected_colour": selected_colour,
        "sizes": ProductVariant.objects.filter(
            is_active=True, stock__gt=0, product__is_active=True
        ).values_list("size", flat=True).distinct().order_by("size"),
        "colours": ProductVariant.objects.filter(
            is_active=True, stock__gt=0, product__is_active=True
        ).values_list("colour", flat=True).distinct().order_by("colour"),
        "min_price": min_price,
        "max_price": max_price,
        "sort": sort,
        "query_string": urlencode(params),
    })


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.prefetch_related("images", "variants", "category"),
        slug=slug, is_active=True,
    )
    related = Product.objects.filter(
        is_active=True, category=product.category
    ).exclude(pk=product.pk).prefetch_related("images")[:4]
    variants = product.variants.filter(is_active=True)
    sizes = sorted(set(variants.values_list("size", flat=True)))
    colours = sorted(set(variants.values_list("colour", flat=True)))
    return render(request, "store/product_detail.html", {
        "product": product,
        "related_products": related,
        "variants": variants,
        "sizes": sizes,
        "colours": colours,
        "variants_data": [
            {
                "id": item.pk, "size": item.size, "colour": item.colour,
                "stock": item.stock, "available": item.available,
                "price": str(item.current_price),
            }
            for item in variants
        ],
    })


def quick_view(request, slug):
    product = get_object_or_404(
        Product.objects.prefetch_related("images", "variants"), slug=slug, is_active=True
    )
    variants = list(product.variants.filter(is_active=True))
    return render(request, "store/quick_view.html", {
        "product": product,
        "variants": variants,
        "sizes": sorted({item.size for item in variants}),
        "colours": sorted({item.colour for item in variants}),
        "variants_data": [
            {
                "id": item.pk, "size": item.size, "colour": item.colour,
                "stock": item.stock, "available": item.available,
                "price": str(item.current_price),
            }
            for item in variants
        ],
    })


def _cart_or_redirect(request):
    if not request.user.is_authenticated:
        # The cart belongs to the browser session and works without an account.
        return get_cart(request)
    return get_cart(request)


def cart_detail(request):
    cart = _cart_or_redirect(request)
    items = cart.items.select_related("variant__product").prefetch_related(
        "variant__product__images"
    )
    return render(request, "store/cart.html", {"cart": cart, "items": items})


@require_POST
def cart_add(request):
    cart = get_cart(request)
    variant = get_object_or_404(
        ProductVariant.objects.select_related("product"),
        pk=request.POST.get("variant_id"), is_active=True, product__is_active=True,
    )
    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    quantity = max(1, min(quantity, 99))
    if not variant.available:
        messages.error(request, "That size and colour are currently unavailable.")
    else:
        item = CartItem.objects.filter(cart=cart, variant=variant).first()
        requested = quantity + (item.quantity if item else 0)
        if requested > variant.stock:
            messages.error(request, f"Only {variant.stock} of that variation are available.")
        elif item:
            item.quantity = requested
            item.save(update_fields=["quantity", "updated_at"])
            messages.success(request, f"{variant.product.name} added to your bag.")
        else:
            CartItem.objects.create(cart=cart, variant=variant, quantity=quantity)
            messages.success(request, f"{variant.product.name} added to your bag.")
    next_url = request.POST.get("next", "")
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect("cart")


@require_POST
def cart_update(request, item_id):
    cart = get_cart(request)
    item = get_object_or_404(
        CartItem.objects.select_related("variant__product"), pk=item_id, cart=cart
    )
    try:
        quantity = int(request.POST.get("quantity", item.quantity))
    except (TypeError, ValueError):
        quantity = item.quantity
    variant_id = request.POST.get("variant_id")
    variant = item.variant
    if variant_id:
        variant = get_object_or_404(
            ProductVariant, pk=variant_id, product=item.variant.product,
            is_active=True, product__is_active=True,
        )
    if quantity < 1:
        item.delete()
        messages.info(request, "Item removed from your bag.")
    elif not variant.available or quantity > variant.stock:
        messages.error(request, "The requested size, colour, or quantity is unavailable.")
    else:
        item.variant = variant
        item.quantity = min(quantity, 99)
        item.save(update_fields=["variant", "quantity", "updated_at"])
        messages.success(request, "Your bag was updated.")
    return redirect("cart")


@require_POST
def cart_remove(request, item_id):
    cart = get_cart(request)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    item.delete()
    messages.info(request, "Item removed from your bag.")
    return redirect("cart")


def checkout(request):
    cart = get_cart(request)
    items = list(cart.items.select_related("variant__product").prefetch_related(
        "variant__product__images"
    ))
    if not items:
        messages.info(request, "Your bag is empty.")
        return redirect("shop")
    initial = {}
    if request.user.is_authenticated:
        initial.update({
            "customer_name": request.user.get_full_name(),
            "email": request.user.email,
        })
        profile = getattr(request.user, "raw_profile", None)
        if profile:
            initial["phone"] = profile.phone
        address = request.user.raw_addresses.filter(is_default=True).first()
        if address:
            initial.update({
                "customer_name": address.recipient,
                "phone": address.phone,
                "region": address.region,
                "city": address.city,
                "address": address.address,
                "delivery_instructions": address.delivery_instructions,
            })
    form = CheckoutForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                locked_items = list(
                    cart.items.select_for_update().select_related("variant__product")
                )
                if not locked_items:
                    raise ValueError("Your bag is empty.")
                subtotal = Decimal("0.00")
                line_data = []
                for item in locked_items:
                    variant = ProductVariant.objects.select_for_update().select_related(
                        "product"
                    ).get(pk=item.variant_id)
                    if not variant.available or item.quantity > variant.stock:
                        raise ValueError(
                            f"{variant.product.name} ({variant.size}, {variant.colour}) "
                            "is no longer available in that quantity."
                        )
                    price = variant.current_price
                    subtotal += price * item.quantity
                    line_data.append((variant, item.quantity, price))
                values = form.cleaned_data
                order = Order.objects.create(
                    customer=request.user if request.user.is_authenticated else None,
                    customer_name=values["customer_name"],
                    phone=values["phone"],
                    email=values.get("email", ""),
                    region=values["region"],
                    city=values["city"],
                    address=values["address"],
                    delivery_instructions=values.get("delivery_instructions", ""),
                    subtotal=subtotal,
                )
                for variant, quantity, price in line_data:
                    OrderItem.objects.create(
                        order=order,
                        variant=variant,
                        product_name=variant.product.name,
                        sku=variant.sku,
                        size=variant.size,
                        colour=variant.colour,
                        unit_price=price,
                        quantity=quantity,
                    )
                OrderStatusLog.objects.create(
                    order=order,
                    new_status=Order.Status.PENDING_WHATSAPP,
                    note="Order created; awaiting customer WhatsApp confirmation.",
                )
                cart.items.all().delete()
            return redirect("order_review", token=order.public_token)
        except ValueError as error:
            form.add_error(None, str(error))
    return render(request, "store/checkout.html", {
        "form": form, "cart": cart, "items": items
    })


def order_review(request, token):
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "status_history"),
        public_token=token,
    )
    return render(request, "store/order_review.html", {
        "order": order,
        "whatsapp_url": whatsapp_url(order),
        "whatsapp_message": build_whatsapp_message(order),
    })


def whatsapp_order(request, token):
    order = get_object_or_404(Order, public_token=token)
    if order.status != Order.Status.PENDING_WHATSAPP:
        messages.info(request, "This order is no longer awaiting WhatsApp confirmation.")
        return redirect("order_review", token=token)
    order.whatsapp_opened_at = timezone.now()
    order.save(update_fields=["whatsapp_opened_at", "updated_at"])
    return redirect(whatsapp_url(order))


def about(request):
    return render(request, "store/about.html")


def collection_gallery(request, slug):
    collections = {
        "men": ("Men's collection", "MEN / REAL AS WE", "A full visual archive of RAW menswear campaigns and pieces.", "men"),
        "women": ("Women's collection", "WOMEN / REAL AS WE", "Every supplied RAW womenswear photograph, together in one collection.", "women"),
        "campaign": ("RAW campaign archive", "THE RAW IMAGE ARCHIVE", "The complete RAW campaign library, including the original brand mark and campaign artwork.", "campaign"),
    }
    if slug not in collections:
        raise Http404("Collection not found")
    title, eyebrow, description, asset_group = collections[slug]
    photos = [asset for asset in GALLERY_ASSETS if asset["collection"] == asset_group]
    products = Product.objects.filter(is_active=True, category__slug=slug).prefetch_related(
        "images", "variants"
    )
    return render(request, "store/collection_gallery.html", {
        "collection_title": title,
        "collection_eyebrow": eyebrow,
        "collection_description": description,
        "collection_slug": slug,
        "collection_photos": photos,
        "collection_count": len(photos),
        "collection_products": products,
    })


def contact(request):
    return render(request, "store/contact.html")


@require_POST
def newsletter_signup(request):
    form = NewsletterForm(request.POST)
    if form.is_valid():
        subscriber, created = NewsletterSubscriber.objects.get_or_create(
            email=form.cleaned_data["email"].lower(),
            defaults={"is_active": True},
        )
        if not subscriber.is_active:
            subscriber.is_active = True
            subscriber.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "You're on the list. Watch this space.")
    else:
        messages.error(request, "Enter a valid email address.")
    return redirect("home")


def signup(request):
    if request.user.is_authenticated:
        return redirect("profile")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        CustomerProfile.objects.get_or_create(user=user)
        login(request, user)
        messages.success(request, "Welcome to RAW.")
        return redirect("profile")
    return render(request, "store/signup.html", {"form": form})


@login_required
def profile(request):
    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()[:150]
        last_name = request.POST.get("last_name", "").strip()[:150]
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()[:30]
        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.email = email
        request.user.save(update_fields=["first_name", "last_name", "email"])
        profile.phone = phone
        profile.save(update_fields=["phone", "updated_at"])
        messages.success(request, "Your profile is updated.")
        return redirect("profile")
    return render(request, "store/profile.html", {"profile": profile})


@login_required
def address_book(request):
    addresses = request.user.raw_addresses.all()
    return render(request, "store/address_book.html", {"addresses": addresses})


@login_required
@require_POST
def address_add(request):
    values = {
        "label": request.POST.get("label", "Home").strip()[:50] or "Home",
        "recipient": request.POST.get("recipient", "").strip()[:120],
        "phone": request.POST.get("phone", "").strip()[:30],
        "region": request.POST.get("region", "").strip()[:100],
        "city": request.POST.get("city", "").strip()[:100],
        "address": request.POST.get("address", "").strip()[:240],
        "delivery_instructions": request.POST.get("delivery_instructions", "").strip(),
    }
    if not all(values[key] for key in ("recipient", "phone", "region", "city", "address")):
        messages.error(request, "Complete the recipient, phone, region, city, and address fields.")
    else:
        values["user"] = request.user
        values["is_default"] = not request.user.raw_addresses.exists()
        ShippingAddress.objects.create(**values)
        messages.success(request, "Address saved.")
    return redirect("address_book")


@login_required
def order_history(request):
    orders = request.user.raw_orders.prefetch_related("items").all()
    return render(request, "store/order_history.html", {"orders": orders})


@login_required
def account_order(request, reference):
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "status_history"),
        reference=reference, customer=request.user,
    )
    return render(request, "store/account_order.html", {
        "order": order, "whatsapp_url": whatsapp_url(order)
    })


def terms(request):
    return render(request, "store/terms.html")


def privacy(request):
    return render(request, "store/privacy.html")


def robots(request):
    return HttpResponse(
        "User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /account/\n",
        content_type="text/plain",
    )


def offline(request):
    return render(request, "store/offline.html")


def service_worker(request):
    worker = Path(__file__).resolve().parent / "static" / "store" / "js" / "sw.js"
    return HttpResponse(
        worker.read_text(encoding="utf-8"),
        content_type="application/javascript; charset=utf-8",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


@login_required
@user_passes_test(lambda user: user.is_staff)
def dashboard(request):
    orders = Order.objects.all()
    total_orders = orders.count()
    pending = orders.filter(status=Order.Status.PENDING_WHATSAPP).count()
    confirmed = orders.filter(status__in=[
        Order.Status.CONFIRMED, Order.Status.PROCESSING, Order.Status.READY,
        Order.Status.SHIPPED, Order.Status.DELIVERED,
    ])
    confirmed_value = confirmed.aggregate(value=Sum("subtotal"))["value"] or Decimal("0.00")
    low_stock = ProductVariant.objects.filter(
        is_active=True, stock__lte=3, product__is_active=True
    ).select_related("product").order_by("stock")[:8]
    return render(request, "store/dashboard.html", {
        "total_orders": total_orders,
        "pending_orders": pending,
        "confirmed_orders": confirmed.count(),
        "confirmed_value": confirmed_value,
        "customers": CustomerProfile.objects.count(),
        "low_stock": low_stock,
        "recent_orders": orders.prefetch_related("items")[:8],
    })

