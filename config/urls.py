from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from store import views
from store.sitemaps import ProductSitemap

admin.site.site_header = "RAW · REAL AS WE"
admin.site.site_title = "RAW Control"
admin.site.index_title = "Manage the RAW store"

sitemaps = {"products": ProductSitemap}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("studio/", views.dashboard, name="dashboard"),
    path("account/", include("django.contrib.auth.urls")),
    path("account/register/", views.signup, name="signup"),
    path("account/profile/", views.profile, name="profile"),
    path("account/addresses/", views.address_book, name="address_book"),
    path("account/addresses/add/", views.address_add, name="address_add"),
    path("account/orders/", views.order_history, name="order_history"),
    path("account/orders/<str:reference>/", views.account_order, name="account_order"),
    path("shop/", views.shop, name="shop"),
    path("shop/category/<slug:category_slug>/", views.shop, name="category_shop"),
    path("collections/<slug:slug>/", views.collection_gallery, name="collection_gallery"),
    path("products/<slug:slug>/", views.product_detail, name="product_detail"),
    path("products/<slug:slug>/quick-view/", views.quick_view, name="quick_view"),
    path("bag/", views.cart_detail, name="cart"),
    path("bag/add/", views.cart_add, name="cart_add"),
    path("bag/update/<int:item_id>/", views.cart_update, name="cart_update"),
    path("bag/remove/<int:item_id>/", views.cart_remove, name="cart_remove"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/<uuid:token>/", views.order_review, name="order_review"),
    path("orders/<uuid:token>/whatsapp/", views.whatsapp_order, name="whatsapp_order"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("newsletter/subscribe/", views.newsletter_signup, name="newsletter_signup"),
    path("terms/", views.terms, name="terms"),
    path("privacy/", views.privacy, name="privacy"),
    path("offline/", views.offline, name="offline"),
    path("manifest.webmanifest", views.web_manifest, name="web_manifest"),
    path("service-worker.js", views.service_worker, name="service_worker"),
    path("robots.txt", views.robots, name="robots"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("", views.home, name="home"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
