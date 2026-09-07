import datetime
import json

from django.core.management.base import BaseCommand, CommandError

from sitio.models import Feriado, Horario, Ruta

ORIGEN_POR_REGION = {
    "aysen": "Puerto Aysén",
    "coyhaique": "Coyhaique",
}

TIPO_DIA_POR_COLECCION = {
    "lunesViernes": Horario.TipoDia.LUNES_VIERNES,
    "sabados": Horario.TipoDia.SABADO,
    "domingosFeriados": Horario.TipoDia.DOMINGO_FERIADO,
}


class Command(BaseCommand):
    help = "Carga horarios y feriados reales desde un export JSON de Firestore (suray_firestore_export.json)."

    def add_arguments(self, parser):
        parser.add_argument("json_path", type=str, help="Ruta al archivo de export JSON de Firestore.")
        parser.add_argument(
            "--reemplazar",
            action="store_true",
            help="Borra los Horario y Feriado existentes antes de cargar los nuevos.",
        )

    def handle(self, *args, **options):
        json_path = options["json_path"]
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"No se encontró el archivo: {json_path}")

        if options["reemplazar"]:
            borrados_h = Horario.objects.all().delete()[0]
            borrados_f = Feriado.objects.all().delete()[0]
            self.stdout.write(f"Borrados {borrados_h} horarios y {borrados_f} feriados existentes.")

        colecciones = data.get("colecciones", {})

        # --- Horarios ---
        creados = 0
        omitidos_sabados = 0
        horarios_data = colecciones.get("horarios", {})
        for region, tipos in horarios_data.items():
            origen = ORIGEN_POR_REGION.get(region)
            if not origen:
                self.stdout.write(self.style.WARNING(f"Región desconocida '{region}', se omite."))
                continue
            ruta, _ = Ruta.objects.get_or_create(origen=origen, destino=self._destino_para(origen))

            for coleccion, entradas in tipos.items():
                tipo_dia = TIPO_DIA_POR_COLECCION.get(coleccion)
                if not tipo_dia:
                    self.stdout.write(self.style.WARNING(f"Colección desconocida '{coleccion}', se omite."))
                    continue
                for entrada in entradas:
                    hora_str = entrada["time"]
                    hora = datetime.datetime.strptime(hora_str, "%H:%M").time()
                    _, created = Horario.objects.get_or_create(
                        ruta=ruta, tipo_dia=tipo_dia, hora_salida=hora
                    )
                    if created:
                        creados += 1

        if "sabados" not in {c for tipos in horarios_data.values() for c in tipos}:
            self.stdout.write(self.style.WARNING(
                "El export no trae colección 'sabados' para ninguna región — "
                "no se cargó ningún horario de Sábado (coincide con el estado real de producción)."
            ))

        # --- Feriados ---
        feriados_creados = 0
        feriados_data = colecciones.get("feriados", {})
        for anio, fechas in feriados_data.items():
            for mmdd, info in fechas.items():
                mes, dia = mmdd.split("-")
                if not info.get("activo", True):
                    continue
                fecha = datetime.date(int(anio), int(mes), int(dia))
                _, created = Feriado.objects.update_or_create(
                    fecha=fecha,
                    defaults={
                        "nombre": info.get("nombre", ""),
                        "sin_servicio": info.get("tipoHorario") == "sinServicio",
                    },
                )
                if created:
                    feriados_creados += 1

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {creados} horarios nuevos, {feriados_creados} feriados nuevos."
        ))

    @staticmethod
    def _destino_para(origen):
        return "Coyhaique" if origen == "Puerto Aysén" else "Puerto Aysén"
