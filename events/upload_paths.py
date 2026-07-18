import os


def event_poster_upload_path(instance, filename):
    """Cloudinary folder: JamSession Lab/events/posters/"""
    safe_filename = os.path.basename(filename)
    return f"JamSession Lab/events/posters/{safe_filename}"
