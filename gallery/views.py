from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from .forms import GalleryUploadForm
from .models import ApprovalStatus, GalleryItem


def gallery_list(request):
    """Public gallery page showing approved media only."""
    items = GalleryItem.objects.filter(status=ApprovalStatus.APPROVED).select_related(
        "uploaded_by"
    )
    return render(
        request,
        "gallery/gallery_list.html",
        {"gallery_items": items},
    )


@login_required
@require_http_methods(["GET", "POST"])
def gallery_upload(request):
    """Allow registered users to submit media for admin approval."""
    if request.method == "POST":
        form = GalleryUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                _(
                    "Your upload was submitted successfully. "
                    "It will appear in the gallery once approved by our team."
                ),
            )
            return redirect("gallery:my_uploads")
    else:
        form = GalleryUploadForm(user=request.user)

    return render(request, "gallery/upload.html", {"form": form})


@login_required
def my_uploads(request):
    """Show the current user's gallery uploads and their approval status."""
    items = GalleryItem.objects.filter(uploaded_by=request.user)
    return render(
        request,
        "gallery/my_uploads.html",
        {"gallery_items": items},
    )
