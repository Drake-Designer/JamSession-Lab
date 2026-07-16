from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Accounts"

    def ready(self):
        from jamsession.image_formats import register_heif_opener

        register_heif_opener()
        import accounts.signals  # noqa: F401
