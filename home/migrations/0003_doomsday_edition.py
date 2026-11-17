from datetime import date

from django.db import migrations, models


def create_doomsday(apps, schema_editor):
    """Crée l'édition Doomsday, programmée autour de la sortie française (16/12/2026)."""
    SeasonalEvent = apps.get_model("home", "SeasonalEvent")
    SeasonalEvent.objects.get_or_create(
        key="doomsday",
        defaults={
            "mode": "auto",
            "start_date": date(2026, 12, 9),
            "end_date": date(2027, 1, 4),
            "repeat_yearly": False,
        },
    )


def remove_doomsday(apps, schema_editor):
    apps.get_model("home", "SeasonalEvent").objects.filter(key="doomsday").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0002_seasonal_events'),
    ]

    operations = [
        migrations.AlterField(
            model_name='seasonalevent',
            name='key',
            field=models.CharField(choices=[('christmas', 'Décor de Noël'), ('vicecity', 'Édition spéciale Vice City'), ('doomsday', 'Édition spéciale Doomsday')], max_length=30, unique=True, verbose_name='Décor'),
        ),
        migrations.RunPython(create_doomsday, remove_doomsday),
    ]
