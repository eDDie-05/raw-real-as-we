from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

from .models import NewsletterSubscriber, ProductImage


class CheckoutForm(forms.Form):
    customer_name = forms.CharField(max_length=120, label="Full name")
    phone = forms.CharField(max_length=30, label="Phone number")
    email = forms.EmailField(required=False)
    region = forms.CharField(max_length=100)
    city = forms.CharField(max_length=100)
    address = forms.CharField(max_length=240, label="Delivery address")
    delivery_instructions = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        digits = "".join(ch for ch in phone if ch.isdigit())
        if len(digits) < 9 or len(digits) > 15:
            raise ValidationError("Enter a valid phone number.")
        return phone


class NewsletterForm(forms.ModelForm):
    class Meta:
        model = NewsletterSubscriber
        fields = ["email"]
        widgets = {"email": forms.EmailInput(attrs={"placeholder": "Your email address"})}


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=False)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")


class ProductImageAdminForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = "__all__"

    def clean_image(self):
        image_file = self.cleaned_data.get("image")
        if not image_file:
            return image_file
        if image_file.size > 10 * 1024 * 1024:
            raise ValidationError("Images must be 10 MB or smaller.")
        try:
            image_file.seek(0)
            with Image.open(image_file) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValidationError("Upload a JPEG, PNG, or WebP image.")
                image.verify()
            image_file.seek(0)
        except (UnidentifiedImageError, OSError):
            raise ValidationError("This file is not a valid image.")
        return image_file
