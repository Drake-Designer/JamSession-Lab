from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from gallery.fields import DynamicCloudinaryField
from gallery.models import MediaType
from gallery.validators import validate_gallery_file_size, validate_gallery_file_type
from jamsession.cloudinary_delivery import web_image_url
from jamsession.moderation import ModeratedContent


def community_media_display_url(file_field, media_type):
    """
    Browser-friendly delivery URL for a community attachment.

    Images go through web_image_url (f_auto) so HEIC/HEIF uploads render in
    <img> tags — the same approach GalleryItem.display_media_url uses.
    Videos keep the raw Cloudinary URL.
    """
    if not file_field:
        return ""

    if media_type == MediaType.VIDEO:
        return file_field.url

    return web_image_url(
        file_field,
        width=1920,
        crop="limit",
        quality="auto:best",
    )


def generate_unique_post_slug(title):
    """
    Build a URL slug from a post title.

    Mirrors generate_unique_username() in accounts/forms.py: slugify the
    title, then add a numeric suffix if that slug is already taken.
    """
    base = slugify(title)[:200] or "post"
    slug = base
    counter = 2
    while CommunityPost.objects.filter(slug=slug).exists():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


class CommunityPost(ModeratedContent):
    # CASCADE removes the post (and its media via related CASCADE) when the
    # author permanently deletes their account — required for privacy erasure.
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="community_posts",
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    # Optional hero image for list cards and the post detail header —
    # distinct from CommunityPostMedia attachments in the body gallery.
    cover_image = DynamicCloudinaryField(
        _("cover image"),
        resource_type="image",
        blank=True,
        null=True,
        validators=[validate_gallery_file_size, validate_gallery_file_type],
    )
    # Percentages (0–100) for CSS object-position when the cover is cropped
    # to a fixed frame — so authors can keep faces in view.
    cover_focus_x = models.FloatField(
        _("cover focus X"),
        default=50,
        help_text=_("Horizontal focal point as a percentage (0 = left, 100 = right)."),
    )
    cover_focus_y = models.FloatField(
        _("cover focus Y"),
        default=50,
        help_text=_("Vertical focal point as a percentage (0 = top, 100 = bottom)."),
    )
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("community post")
        verbose_name_plural = _("community posts")

    def __str__(self):
        if self.author:
            return f"{self.title} — @{self.author.username}"
        return f"{self.title} — (deleted account)"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_post_slug(self.title)
        super().save(*args, **kwargs)

    def upload_options(self):
        """Cloudinary folder for the optional cover_image field."""
        if self.author_id and self.author:
            username = self.author.username
        elif self.author:
            username = self.author.username
        else:
            username = "unknown"

        return {
            "folder": f"JamSession Lab/{username}/community/covers",
            "use_filename": True,
            "unique_filename": True,
        }

    def purge_media_after_rejection(self):
        """Delete cover + attachments from DB/Cloudinary when a post is rejected."""
        self.media.all().delete()
        if self.cover_image:
            self.cover_image = None
            self.save(update_fields=["cover_image", "updated_at"])

    @property
    def cover_display_url(self):
        """
        Card thumbnail URL — scaled, not hard-cropped.

        Cropping is done in CSS with object-fit/object-position so the
        author's cover_focus_x/y still apply on list cards.
        """
        if not self.cover_image:
            return ""
        return web_image_url(
            self.cover_image,
            width=900,
            crop="limit",
            quality="auto",
        )

    @property
    def cover_detail_url(self):
        """Larger header URL for the post detail page."""
        if not self.cover_image:
            return ""
        return web_image_url(
            self.cover_image,
            width=1920,
            crop="limit",
            quality="auto:best",
        )

    @property
    def cover_focus_style(self):
        """CSS object-position value derived from the stored focal point."""
        return f"{self.cover_focus_x:g}% {self.cover_focus_y:g}%"


class CommunityPostMedia(models.Model):
    post = models.ForeignKey(
        CommunityPost,
        on_delete=models.CASCADE,
        related_name="media",
    )
    file = DynamicCloudinaryField(
        _("file"),
        resource_type="auto",
        validators=[validate_gallery_file_size, validate_gallery_file_type],
    )
    media_type = models.CharField(
        max_length=10,
        choices=MediaType.choices,
        blank=True,
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = _("community post attachment")
        verbose_name_plural = _("community post attachments")

    def __str__(self):
        return f"Attachment for post {self.post_id}"

    @property
    def display_url(self):
        """URL safe to put in <img>/<video> src on the public site and queue."""
        return community_media_display_url(self.file, self.media_type)

    def upload_options(self):
        """Per-instance Cloudinary upload options, mirroring GalleryItem."""
        if self.post_id and self.post.author:
            username = self.post.author.username
        else:
            username = "unknown"

        return {
            "folder": f"JamSession Lab/{username}/community/posts",
            "use_filename": True,
            "unique_filename": True,
        }


class CommunityComment(ModeratedContent):
    post = models.ForeignKey(
        CommunityPost,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    # CASCADE removes the comment (and its media) when the author deletes
    # their account — required for privacy erasure.
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="community_comments",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("community comment")
        verbose_name_plural = _("community comments")

    def __str__(self):
        if self.author:
            return f"Comment by @{self.author.username} on post {self.post_id}"
        return f"Comment by (deleted account) on post {self.post_id}"

    def purge_media_after_rejection(self):
        """Delete comment attachments from DB/Cloudinary when rejected."""
        self.media.all().delete()


class CommunityCommentMedia(models.Model):
    comment = models.ForeignKey(
        CommunityComment,
        on_delete=models.CASCADE,
        related_name="media",
    )
    file = DynamicCloudinaryField(
        _("file"),
        resource_type="auto",
        validators=[validate_gallery_file_size, validate_gallery_file_type],
    )
    media_type = models.CharField(
        max_length=10,
        choices=MediaType.choices,
        blank=True,
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = _("community comment attachment")
        verbose_name_plural = _("community comment attachments")

    def __str__(self):
        return f"Attachment for comment {self.comment_id}"

    @property
    def display_url(self):
        """URL safe to put in <img>/<video> src on the public site and queue."""
        return community_media_display_url(self.file, self.media_type)

    def upload_options(self):
        """Per-instance Cloudinary upload options, mirroring GalleryItem."""
        if self.comment_id and self.comment.author:
            username = self.comment.author.username
        else:
            username = "unknown"

        return {
            "folder": f"JamSession Lab/{username}/community/comments",
            "use_filename": True,
            "unique_filename": True,
        }


class CommunityLike(models.Model):
    post = models.ForeignKey(
        CommunityPost,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    # CASCADE (unlike author/uploaded_by elsewhere in the project): a like
    # row with no user has no value as public content, unlike posts/comments
    # which are intentionally preserved when their author's account is gone.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user"], name="unique_community_like_per_user"
            ),
        ]
        verbose_name = _("community like")
        verbose_name_plural = _("community likes")

    def __str__(self):
        return f"@{self.user.username} likes post {self.post_id}"
