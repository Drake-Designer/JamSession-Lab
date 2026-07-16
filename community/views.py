from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods, require_POST

from gallery.models import GalleryItem
from jamsession.moderation import ApprovalStatus

from .forms import CommunityCommentForm, CommunityPostForm
from .models import CommunityComment, CommunityLike, CommunityPost

POSTS_PER_PAGE = 10


def _user_can_moderate_or_owns(user, author_id):
    """
    Deletion permission rule, checked in the view (never trusting the template).

    True for staff/superusers (moderators) or for the content's own author.
    A None author_id (author account deleted) is only removable by moderators.
    """
    if user.is_staff or user.is_superuser:
        return True
    return author_id is not None and author_id == user.id


def _require_moderator(user):
    """
    Raise PermissionDenied (-> 403) unless the user is staff/superuser.

    Used only by the moderation queue and its approve/reject/delete action
    views below. This is an explicit, single-purpose check — not a new
    permission system — kept separate from _user_can_moderate_or_owns()
    because the moderation queue has no "author exception": it is staff/
    superuser only, full stop.
    """
    if not (user.is_staff or user.is_superuser):
        raise PermissionDenied


def _visible_post_or_404(request, slug):
    """
    Return the post if the current user is allowed to see it.

    Approved posts are public. The author may preview their own post only
    while it is still PENDING. Rejected posts (and any other non-approved
    status) are a 404 for everyone — including the author — if opened via
    community:post_detail.
    """
    post = get_object_or_404(
        CommunityPost.objects.select_related("author"), slug=slug
    )

    if post.status == ApprovalStatus.APPROVED:
        return post

    if (
        post.status == ApprovalStatus.PENDING
        and request.user.is_authenticated
        and post.author_id == request.user.id
    ):
        return post

    raise Http404


def post_list(request):
    """Public list of approved community posts, paginated."""
    approved_posts = CommunityPost.objects.filter(
        status=ApprovalStatus.APPROVED
    ).select_related("author")

    paginator = Paginator(approved_posts, POSTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "community/post_list.html", {"page_obj": page_obj})


def post_detail(request, slug):
    """
    Public detail for an approved post; the author may also preview their own
    post while it is still pending approval (flagged for a badge in the template).
    """
    post = _visible_post_or_404(request, slug)

    comments = post.comments.filter(
        status=ApprovalStatus.APPROVED
    ).select_related("author")

    user = request.user
    context = {
        "post": post,
        "is_pending_preview": post.status == ApprovalStatus.PENDING,
        "comments": comments,
        "comment_form": CommunityCommentForm(),
        "like_count": post.likes.count(),
        # Display-only helpers: buttons are hidden accordingly in the
        # template, but post_delete/comment_delete re-check permissions
        # themselves — the template never is the source of truth.
        "user_has_liked": user.is_authenticated
        and post.likes.filter(user=user).exists(),
        "can_delete_post": user.is_authenticated
        and _user_can_moderate_or_owns(user, post.author_id),
    }
    return render(request, "community/post_detail.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def post_create(request):
    """Create a post (with optional media); moderation depends on the author's role."""
    if request.method == "POST":
        form = CommunityPostForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            post = form.save()
            if post.status == ApprovalStatus.APPROVED:
                messages.success(request, _("Your post has been published."))
            else:
                messages.success(
                    request, _("Your post has been submitted for approval.")
                )
            return redirect("community:post_detail", slug=post.slug)
    else:
        form = CommunityPostForm(user=request.user)

    return render(request, "community/post_form.html", {"form": form})


@login_required
@require_POST
def comment_add(request, slug):
    """Add a comment (with optional media) to a post the user is allowed to see."""
    post = _visible_post_or_404(request, slug)

    form = CommunityCommentForm(
        request.POST, request.FILES, user=request.user, post=post
    )
    if form.is_valid():
        comment = form.save()
        if comment.status == ApprovalStatus.APPROVED:
            messages.success(request, _("Your comment has been published."))
        else:
            messages.success(
                request, _("Your comment has been submitted for approval.")
            )
    else:
        messages.error(
            request,
            _("Your comment could not be posted. Please check the form and try again."),
        )

    return redirect("community:post_detail", slug=post.slug)


@login_required
@require_POST
def like_toggle(request, slug):
    """
    Toggle the current user's like on an approved post.

    Idempotent in practice: a repeated request simply flips the like on or off
    using get_or_create/delete, so a double submission never raises.
    """
    post = get_object_or_404(
        CommunityPost, slug=slug, status=ApprovalStatus.APPROVED
    )

    like, created = CommunityLike.objects.get_or_create(post=post, user=request.user)
    if not created:
        like.delete()

    return redirect("community:post_detail", slug=post.slug)


@login_required
@require_POST
def post_delete(request, slug):
    """Delete a post — only its author or a staff/superuser moderator may do so."""
    post = get_object_or_404(CommunityPost, slug=slug)

    if not _user_can_moderate_or_owns(request.user, post.author_id):
        raise PermissionDenied

    post.delete()
    messages.success(request, _("The post has been deleted."))
    return redirect("community:list")


@login_required
@require_POST
def comment_delete(request, pk):
    """Delete a comment — only its author or a staff/superuser moderator may do so."""
    comment = get_object_or_404(
        CommunityComment.objects.select_related("post"), pk=pk
    )

    if not _user_can_moderate_or_owns(request.user, comment.author_id):
        raise PermissionDenied

    post_slug = comment.post.slug
    comment.delete()
    messages.success(request, _("The comment has been deleted."))
    return redirect("community:post_detail", slug=post_slug)


@login_required
def moderation_queue(request):
    """
    Staff-only page listing every post, comment, and gallery item awaiting
    approval.

    Oldest submissions first, so moderators clear the backlog in the order
    it built up. All the moderation logic itself stays on the model
    (ModeratedContent.approve()/reject()) and in the action views below —
    this view only reads and displays the pending queue.
    """
    _require_moderator(request.user)

    pending_posts = (
        CommunityPost.objects.filter(status=ApprovalStatus.PENDING)
        .select_related("author")
        .prefetch_related("media")
        .order_by("created_at")
    )
    pending_comments = (
        CommunityComment.objects.filter(status=ApprovalStatus.PENDING)
        .select_related("author", "post")
        .prefetch_related("media")
        .order_by("created_at")
    )
    pending_gallery_items = (
        GalleryItem.objects.filter(status=ApprovalStatus.PENDING)
        .select_related("uploaded_by")
        .order_by("created_at")
    )

    context = {
        "pending_posts": pending_posts,
        "pending_comments": pending_comments,
        "pending_gallery_items": pending_gallery_items,
    }
    return render(request, "community/moderation_queue.html", context)


@login_required
@require_POST
def moderation_post_approve(request, slug):
    """Approve a pending post — delegates to ModeratedContent.approve()."""
    _require_moderator(request.user)

    post = get_object_or_404(CommunityPost, slug=slug, status=ApprovalStatus.PENDING)
    post.approve(request.user)
    messages.success(request, _("The post has been approved."))
    return redirect("community:moderation_queue")


@login_required
@require_POST
def moderation_post_reject(request, slug):
    """Reject a pending post, with an optional reason — delegates to ModeratedContent.reject()."""
    _require_moderator(request.user)

    post = get_object_or_404(CommunityPost, slug=slug, status=ApprovalStatus.PENDING)
    post.reject(request.user, reason=request.POST.get("reason", "").strip())
    messages.success(request, _("The post has been rejected."))
    return redirect("community:moderation_queue")


@login_required
@require_POST
def moderation_post_delete(request, slug):
    """Delete a pending post directly from the moderation queue."""
    _require_moderator(request.user)

    post = get_object_or_404(CommunityPost, slug=slug, status=ApprovalStatus.PENDING)
    post.delete()
    messages.success(request, _("The post has been deleted."))
    return redirect("community:moderation_queue")


@login_required
@require_POST
def moderation_comment_approve(request, pk):
    """Approve a pending comment — delegates to ModeratedContent.approve()."""
    _require_moderator(request.user)

    comment = get_object_or_404(
        CommunityComment, pk=pk, status=ApprovalStatus.PENDING
    )
    comment.approve(request.user)
    messages.success(request, _("The comment has been approved."))
    return redirect("community:moderation_queue")


@login_required
@require_POST
def moderation_comment_reject(request, pk):
    """Reject a pending comment, with an optional reason — delegates to ModeratedContent.reject()."""
    _require_moderator(request.user)

    comment = get_object_or_404(
        CommunityComment, pk=pk, status=ApprovalStatus.PENDING
    )
    comment.reject(request.user, reason=request.POST.get("reason", "").strip())
    messages.success(request, _("The comment has been rejected."))
    return redirect("community:moderation_queue")


@login_required
@require_POST
def moderation_comment_delete(request, pk):
    """Delete a pending comment directly from the moderation queue."""
    _require_moderator(request.user)

    comment = get_object_or_404(
        CommunityComment, pk=pk, status=ApprovalStatus.PENDING
    )
    comment.delete()
    messages.success(request, _("The comment has been deleted."))
    return redirect("community:moderation_queue")


@login_required
@require_POST
def moderation_gallery_approve(request, pk):
    """Approve a pending gallery item — delegates to ModeratedContent.approve()."""
    _require_moderator(request.user)

    item = get_object_or_404(GalleryItem, pk=pk, status=ApprovalStatus.PENDING)
    item.approve(request.user)
    messages.success(request, _("The gallery submission has been approved."))
    return redirect("community:moderation_queue")


@login_required
@require_POST
def moderation_gallery_reject(request, pk):
    """Reject a pending gallery item, with an optional reason."""
    _require_moderator(request.user)

    item = get_object_or_404(GalleryItem, pk=pk, status=ApprovalStatus.PENDING)
    item.reject(request.user, reason=request.POST.get("reason", "").strip())
    messages.success(request, _("The gallery submission has been rejected."))
    return redirect("community:moderation_queue")


@login_required
@require_POST
def moderation_gallery_delete(request, pk):
    """Delete a pending gallery item directly from the moderation queue."""
    _require_moderator(request.user)

    item = get_object_or_404(GalleryItem, pk=pk, status=ApprovalStatus.PENDING)
    item.delete()
    messages.success(request, _("The gallery submission has been deleted."))
    return redirect("community:moderation_queue")
