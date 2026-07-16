from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from jamsession.cloudinary_cleanup import (
    cleanup_file_on_delete,
    cleanup_old_file_on_change,
)


@receiver(pre_save, sender="community.CommunityPost")
def delete_old_community_cover_image(sender, instance, **kwargs):
    cleanup_old_file_on_change(sender, instance, "cover_image")


@receiver(post_delete, sender="community.CommunityPost")
def delete_community_cover_image_on_remove(sender, instance, **kwargs):
    cleanup_file_on_delete(sender, instance, "cover_image")


@receiver(pre_save, sender="community.CommunityPostMedia")
def delete_old_community_post_media_file(sender, instance, **kwargs):
    cleanup_old_file_on_change(sender, instance, "file")


@receiver(post_delete, sender="community.CommunityPostMedia")
def delete_community_post_media_file_on_remove(sender, instance, **kwargs):
    cleanup_file_on_delete(sender, instance, "file")


@receiver(pre_save, sender="community.CommunityCommentMedia")
def delete_old_community_comment_media_file(sender, instance, **kwargs):
    cleanup_old_file_on_change(sender, instance, "file")


@receiver(post_delete, sender="community.CommunityCommentMedia")
def delete_community_comment_media_file_on_remove(sender, instance, **kwargs):
    cleanup_file_on_delete(sender, instance, "file")
