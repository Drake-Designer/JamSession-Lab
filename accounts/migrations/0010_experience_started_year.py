import django.core.validators
from django.db import migrations, models
from django.utils import timezone


def copy_years_to_started_year(apps, schema_editor):
    """Preserve existing experience by converting years → start calendar year."""
    User = apps.get_model("accounts", "User")
    current_year = timezone.localdate().year
    for user in User.objects.exclude(years_of_experience=None).iterator():
        user.experience_started_year = current_year - user.years_of_experience
        user.save(update_fields=["experience_started_year"])


def copy_started_year_to_years(apps, schema_editor):
    """Reverse: recompute static years from the stored start year."""
    User = apps.get_model("accounts", "User")
    current_year = timezone.localdate().year
    for user in User.objects.exclude(experience_started_year=None).iterator():
        user.years_of_experience = max(0, current_year - user.experience_started_year)
        user.save(update_fields=["years_of_experience"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_force_member_badge"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="experience_started_year",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text=(
                    "Calendar year the musician started playing. Years of "
                    "experience are calculated from this value and increase "
                    "each 1 January."
                ),
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(1900),
                    django.core.validators.MaxValueValidator(2100),
                ],
                verbose_name="experience started year",
            ),
        ),
        migrations.RunPython(copy_years_to_started_year, copy_started_year_to_years),
        migrations.RemoveField(
            model_name="user",
            name="years_of_experience",
        ),
    ]
