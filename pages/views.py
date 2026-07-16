from django.shortcuts import render

from .models import HomeCarouselSlide


def home(request):
    """Render the public home page."""
    carousel_slides = HomeCarouselSlide.objects.filter(is_active=True).order_by("order")
    return render(
        request,
        "pages/home.html",
        {"carousel_slides": carousel_slides},
    )


def about(request):
    """Render the public About page."""
    return render(request, "pages/about.html")


def terms(request):
    """Render the public Terms of Service page."""
    return render(request, "pages/terms.html")


def privacy(request):
    """Render the Privacy Policy page (placeholder to be completed)."""
    return render(request, "pages/privacy.html")


def contact(request):
    """Render the public Contact Us page."""
    return render(request, "pages/contact.html")


def bad_request(request, exception=None):
    """Custom 400 error page — rendered only when DEBUG=False."""
    return render(request, "errors/400.html", status=400)


def permission_denied(request, exception=None):
    """Custom 403 error page — rendered only when DEBUG=False."""
    return render(request, "errors/403.html", status=403)


def page_not_found(request, exception=None):
    """Custom 404 error page — rendered only when DEBUG=False."""
    return render(request, "errors/404.html", status=404)


def server_error(request):
    """Custom 500 error page — rendered only when DEBUG=False."""
    return render(request, "errors/500.html", status=500)