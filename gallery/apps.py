from django.apps import AppConfig


class GalleryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "gallery"
    verbose_name = "Gallery"

    def ready(self):
        from jamsession.image_formats import register_heif_opener

        register_heif_opener()
        import gallery.signals  # noqa: F401
