from django.db import migrations


def seed_rutas(apps, schema_editor):
    Ruta = apps.get_model("sitio", "Ruta")
    Ruta.objects.get_or_create(origen="Puerto Aysén", destino="Coyhaique")
    Ruta.objects.get_or_create(origen="Coyhaique", destino="Puerto Aysén")


def unseed_rutas(apps, schema_editor):
    Ruta = apps.get_model("sitio", "Ruta")
    Ruta.objects.filter(origen__in=["Puerto Aysén", "Coyhaique"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sitio", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_rutas, unseed_rutas),
    ]
