from django.apps import AppConfig


class PagesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pages"
    verbose_name = "Home"

    def ready(self):
        from jamsession.image_formats import register_heif_opener

        register_heif_opener()
        import pages.signals  # noqa: F401
