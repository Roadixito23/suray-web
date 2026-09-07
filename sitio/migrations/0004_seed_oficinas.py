from django.db import migrations

# Contenido real extraido de contact_page.dart (ver inventario_contenido.md, seccion 2.4).
OFICINAS = [
    {
        "ciudad": "Puerto Aysén",
        "tipo": "PJ",
        "direccion": "Eusebio Ibar 630",
        "telefono": "672 336222",
        "mapa_url": "https://maps.app.goo.gl/1nv7mAcGRpFVPMacA",
        "orden": 0,
        "horarios": [
            ("Lun-Vie", "06:30–19:00"),
            ("Sábado", "08:00–19:00"),
            ("Domingo", "08:00–13:30 / 16:30–18:00"),
        ],
    },
    {
        "ciudad": "Puerto Aysén",
        "tipo": "CO",
        "direccion": "Eusebio Ibar 630 (interior)",
        "telefono": "672 336231",
        "mapa_url": "https://maps.app.goo.gl/1nv7mAcGRpFVPMacA",
        "orden": 1,
        "horarios": [
            ("Lun-Vie", "09:00–13:30 / 15:18–19:00"),
            ("Sábado", "10:00–13:00"),
            ("Domingo", "Cerrado"),
        ],
    },
    {
        "ciudad": "Coyhaique",
        "tipo": "PJ",
        "direccion": "Av. Norte Sur/Las Violetas, Terminal de Coyhaique, Of. N°2",
        "telefono": "672 212639",
        "mapa_url": "https://maps.app.goo.gl/9AJMknQmkmf3tHSo8",
        "orden": 0,
        "horarios": [
            ("Lun-Vie", "06:30–19:00"),
            ("Sábado", "08:00–19:00"),
            ("Domingo", "10:00–15:30 / 18:00–19:30"),
        ],
    },
    {
        "ciudad": "Coyhaique",
        "tipo": "CO",
        "direccion": "Arturo Prat 265 (interior)",
        "telefono": "672 234085",
        "mapa_url": "https://maps.app.goo.gl/pMdzjb5y1Mg1iNQd9",
        "orden": 1,
        "horarios": [
            ("Lun-Vie", "09:00–13:30 / 15:18–19:00"),
            ("Sábado", "10:00–13:00"),
            ("Domingo", "Cerrado"),
        ],
    },
]


def seed_oficinas(apps, schema_editor):
    Oficina = apps.get_model("sitio", "Oficina")
    HorarioOficina = apps.get_model("sitio", "HorarioOficina")

    for data in OFICINAS:
        horarios = data.pop("horarios")
        oficina, _ = Oficina.objects.get_or_create(
            ciudad=data["ciudad"], tipo=data["tipo"], defaults=data
        )
        for orden, (dia, horario) in enumerate(horarios):
            HorarioOficina.objects.get_or_create(
                oficina=oficina, dia=dia, defaults={"horario": horario, "orden": orden}
            )


def unseed_oficinas(apps, schema_editor):
    Oficina = apps.get_model("sitio", "Oficina")
    Oficina.objects.filter(ciudad__in=["Puerto Aysén", "Coyhaique"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sitio", "0003_oficina_horariooficina"),
    ]

    operations = [
        migrations.RunPython(seed_oficinas, unseed_oficinas),
    ]
