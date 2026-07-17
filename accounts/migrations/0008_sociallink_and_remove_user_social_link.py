from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def forwards_migrate_social_link(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    SocialLink = apps.get_model("accounts", "SocialLink")
    for user in User.objects.exclude(social_link="").iterator():
        url = (user.social_link or "").strip()
        if not url:
            continue
        SocialLink.objects.create(user=user, url=url, order=0)


def backwards_migrate_social_link(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    SocialLink = apps.get_model("accounts", "SocialLink")
    for user in User.objects.iterator():
        first = (
            SocialLink.objects.filter(user=user).order_by("order", "pk").first()
        )
        if first is not None:
            user.social_link = first.url
            user.save(update_fields=["social_link"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_profile_edit_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="SocialLink",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("url", models.URLField(max_length=200, verbose_name="URL")),
                (
                    "order",
                    models.PositiveSmallIntegerField(
                        db_index=True, default=0, verbose_name="order"
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="social_links",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="user",
                    ),
                ),
            ],
            options={
                "verbose_name": "social / music link",
                "verbose_name_plural": "social / music links",
                "ordering": ["order", "pk"],
            },
        ),
        migrations.AddConstraint(
            model_name="sociallink",
            constraint=models.UniqueConstraint(
                fields=("user", "url"),
                name="accounts_sociallink_user_url_uniq",
            ),
        ),
        migrations.RunPython(forwards_migrate_social_link, backwards_migrate_social_link),
        migrations.RemoveField(
            model_name="user",
            name="social_link",
        ),
    ]
