"""
Shared Cloudinary cleanup helpers for any file-like model field — whether a
raw CloudinaryField (cloudinary package) or a FileField/ImageField backed by
Cloudinary storage (accounts.User.profile_picture, pages.HomeCarouselSlide.image).

Two generic signal handlers, parametrised by field name:
- cleanup_old_file_on_change(): attach to pre_save to delete the previous
  file when it is genuinely replaced by a different one.
- cleanup_file_on_delete(): attach to post_delete to delete the file
  belonging to a row that has just been removed.

Comparing "is this the same underlying file" by value — not by Python object
identity — matters: cloudinary.CloudinaryResource (the value type used by a
raw CloudinaryField, e.g. gallery.GalleryItem.file) does not implement
__eq__, so re-fetching the same row twice gives two distinct-but-equal
objects that would otherwise always compare as "different", deleting a file
that is still in use. This bug was found and fixed in gallery/signals.py
during Phase 1 of PROJECT_PLAN.md; this helper preserves that exact fix
(comparison via CloudinaryResource.get_prep_value()) while making it
available to every app.
"""

from cloudinary import CloudinaryResource
from cloudinary.uploader import destroy
from django.core.files.uploadedfile import UploadedFile


def _stored_file_identity(file_value, field):
    """
    Return a comparable key for a file-like field value, or None when the
    value cannot yet be resolved to an existing stored file (no file, or a
    freshly uploaded file object) — such values are always treated as
    different from whatever was previously stored, which is the safe choice.
    """
    if not file_value or isinstance(file_value, UploadedFile):
        return None

    resolved = field.to_python(file_value)

    if isinstance(resolved, CloudinaryResource):
        # Same fix as Phase 1: CloudinaryResource has no __eq__, so compare
        # its canonical string form (the same value written to the database)
        # instead of the object itself.
        return resolved.get_prep_value()

    name = getattr(resolved, "name", None)
    if name is not None:
        return name

    return str(resolved)


def _delete_stored_file(file_value):
    """Delete a file-like field value from its storage, whatever kind it is."""
    if not file_value:
        return

    if isinstance(file_value, CloudinaryResource):
        public_id = getattr(file_value, "public_id", None)
        if not public_id:
            return
        resource_type = getattr(file_value, "resource_type", "image")
        destroy(public_id, resource_type=resource_type, invalidate=True)
        return

    if hasattr(file_value, "delete"):
        file_value.delete(save=False)


def cleanup_old_file_on_change(sender, instance, field_name, **kwargs):
    """
    pre_save handler: delete the previously stored file when the named field
    is replaced by a genuinely different file.

    Compares by value, not by Python object identity (see module docstring),
    so re-saving a row without touching the file field never deletes a file
    that is still in use.
    """
    if instance.pk is None:
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    old_file = getattr(old_instance, field_name)
    if not old_file:
        return

    field = sender._meta.get_field(field_name)
    new_file = getattr(instance, field_name)

    if _stored_file_identity(old_file, field) != _stored_file_identity(new_file, field):
        _delete_stored_file(old_file)


def cleanup_file_on_delete(sender, instance, field_name, **kwargs):
    """post_delete handler: delete the file belonging to a just-deleted row."""
    _delete_stored_file(getattr(instance, field_name, None))
