from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from django.views.decorators.http import require_http_methods

from .forms import GalleryBatchUploadForm
from .models import ApprovalStatus, GalleryItem


def gallery_list(request):
    """Public gallery page showing approved media in separate photo/video sections."""
    approved = (
        GalleryItem.objects.filter(status=ApprovalStatus.APPROVED)
        .select_related("uploaded_by")
        .order_by("-created_at")
    )

    photo_items = [item for item in approved if not item.is_video]
    video_items = [item for item in approved if item.is_video]

    return render(
        request,
        "gallery/gallery_list.html",
        {
            "photo_items": photo_items,
            "video_items": video_items,
            "has_gallery_content": bool(photo_items or video_items),
        },
    )


def build_gallery_upload_summary_message(success_count, failures, *, auto_published=False):
    """Build a single British English summary for batch upload results."""
    parts = []

    if success_count:
        if auto_published:
            parts.append(
                ngettext(
                    "%(count)d file uploaded successfully and published in the gallery.",
                    "%(count)d files uploaded successfully and published in the gallery.",
                    success_count,
                )
                % {"count": success_count}
            )
        else:
            parts.append(
                ngettext(
                    "%(count)d file uploaded successfully and submitted for approval.",
                    "%(count)d files uploaded successfully and submitted for approval.",
                    success_count,
                )
                % {"count": success_count}
            )

    if failures:
        rejected_details = ", ".join(
            f"'{filename}' ({reason})" for filename, reason in failures
        )
        reject_count = len(failures)
        if success_count:
            parts.append(
                ngettext(
                    "%(count)d file was rejected: %(details)s.",
                    "%(count)d files were rejected: %(details)s.",
                    reject_count,
                )
                % {"count": reject_count, "details": rejected_details}
            )
        else:
            parts.append(
                ngettext(
                    "No files were uploaded. %(count)d file was rejected: %(details)s.",
                    "No files were uploaded. %(count)d files were rejected: %(details)s.",
                    reject_count,
                )
                % {"count": reject_count, "details": rejected_details}
            )

    return " ".join(parts)


@login_required
@require_http_methods(["GET", "POST"])
def gallery_upload(request):
    """Allow registered users to submit media for admin approval."""
    if request.method == "POST":
        form = GalleryBatchUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            success_count, failures = form.process_uploads()
            auto_published = request.user.is_staff or request.user.is_superuser
            summary = build_gallery_upload_summary_message(
                success_count,
                failures,
                auto_published=auto_published,
            )

            if success_count:
                messages.success(request, summary)
                return redirect("gallery:list")

            messages.error(request, summary)
    else:
        form = GalleryBatchUploadForm(user=request.user)

    return render(request, "gallery/upload.html", {"form": form})
