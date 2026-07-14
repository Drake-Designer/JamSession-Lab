import os


def home_carousel_upload_path(instance, filename):
    """Cloudinary folder: JamSession Lab/site/home_carousel/"""
    safe_filename = os.path.basename(filename)
    return f"JamSession Lab/site/home_carousel/{safe_filename}"
