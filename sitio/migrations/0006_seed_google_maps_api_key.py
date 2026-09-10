from django.db import migrations

# Key migrada desde la app Flutter original (_legacy_reference/web/index.html).
# Restringila por dominio (HTTP referrer) en Google Cloud Console cuanto antes.
GOOGLE_MAPS_API_KEY = "AIzaSyCSNlH9e84Orco1EAXnB-Iq9TYLBCLynFo"


def seed_api_key(apps, schema_editor):
    ConfiguracionSitio = apps.get_model("sitio", "ConfiguracionSitio")
    ConfiguracionSitio.objects.get_or_create(
        pk=1, defaults={"google_maps_api_key": GOOGLE_MAPS_API_KEY}
    )


def unseed_api_key(apps, schema_editor):
    ConfiguracionSitio = apps.get_model("sitio", "ConfiguracionSitio")
    ConfiguracionSitio.objects.filter(pk=1, google_maps_api_key=GOOGLE_MAPS_API_KEY).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sitio", "0005_configuracionsitio"),
    ]

    operations = [
        migrations.RunPython(seed_api_key, unseed_api_key),
    ]
