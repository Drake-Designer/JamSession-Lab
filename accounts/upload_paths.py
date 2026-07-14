import os


def _username_folder(instance):
    """
    Return the folder segment for Cloudinary paths.

    Uses username (not pk) so folders are human-readable in the Cloudinary
    dashboard (e.g. "JamSession Lab/alice/profile_pictures/"). If a user
    changes their username, new uploads go to the new folder; existing
    Cloudinary assets stay in the old folder until re-uploaded or migrated.
    """
    if hasattr(instance, "username"):
        return instance.username
    if hasattr(instance, "user") and instance.user_id:
        return instance.user.username
    return f"user_{instance.pk or 'unsaved'}"


def profile_picture_upload_path(instance, filename):
    """Cloudinary folder: JamSession Lab/{username}/profile_pictures/"""
    safe_filename = os.path.basename(filename)
    return f"JamSession Lab/{_username_folder(instance)}/profile_pictures/{safe_filename}"
