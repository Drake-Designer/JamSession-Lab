from django.shortcuts import render

from .models import HomeCarouselSlide


def home(request):
    """Render the public home page."""
    carousel_slides = HomeCarouselSlide.objects.filter(is_active=True)
    return render(
        request,
        "pages/home.html",
        {"carousel_slides": carousel_slides},
    )
