# Hand-written migration: preferred genre becomes a multiple choice.
#
# The single CharField "preferred_genre" is replaced by the JSON list
# "preferred_genres" (same approach as User.instruments). Written manually
# so existing values are converted ("rock" -> ["rock"]) instead of lost.

from django.db import migrations, models


def convert_single_genre_to_list(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.exclude(preferred_genre=""):
        user.preferred_genres = [user.preferred_genre]
        user.save(update_fields=["preferred_genres"])


def convert_list_back_to_single(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.all():
        genres = user.preferred_genres or []
        user.preferred_genre = genres[0] if genres else ""
        user.save(update_fields=["preferred_genre"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_public_registration_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="preferred_genres",
            field=models.JSONField(
                blank=True, default=list, verbose_name="preferred music genres"
            ),
        ),
        migrations.RunPython(
            convert_single_genre_to_list,
            convert_list_back_to_single,
        ),
        migrations.RemoveField(
            model_name="user",
            name="preferred_genre",
        ),
    ]
