from datetime import timedelta

from django.shortcuts import render
from django.utils import timezone

from .models import Feriado, Horario, Oficina, Ruta

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


def _tipo_dia_para(fecha, es_feriado):
    if es_feriado:
        return Horario.TipoDia.DOMINGO_FERIADO
    dia_semana = fecha.weekday()  # 0 = lunes ... 6 = domingo
    if dia_semana == 5:
        return Horario.TipoDia.SABADO
    if dia_semana == 6:
        return Horario.TipoDia.DOMINGO_FERIADO
    return Horario.TipoDia.LUNES_VIERNES


def inicio(request):
    hoy = timezone.localdate()
    ahora = timezone.localtime().time()
    manana = hoy + timedelta(days=1)

    feriado_hoy = Feriado.objects.filter(fecha=hoy).first()
    feriado_manana = Feriado.objects.filter(fecha=manana).first()

    tipo_hoy = _tipo_dia_para(hoy, feriado_hoy is not None)
    tipo_manana = _tipo_dia_para(manana, feriado_manana is not None)

    salidas = []
    for origen in Ruta.objects.order_by("id").values_list("origen", flat=True).distinct():
        proximo_hoy = None
        if not (feriado_hoy and feriado_hoy.sin_servicio):
            proximo_hoy = (
                Horario.objects.filter(ruta__origen=origen, tipo_dia=tipo_hoy, hora_salida__gte=ahora)
                .order_by("hora_salida")
                .first()
            )

        if proximo_hoy:
            salidas.append({
                "origen": origen,
                "estado": f"Hoy a las {proximo_hoy.hora_salida.strftime('%H:%M')} hrs.",
                "chip": "HOY",
            })
            continue

        proximo_manana = None
        if not (feriado_manana and feriado_manana.sin_servicio):
            proximo_manana = (
                Horario.objects.filter(ruta__origen=origen, tipo_dia=tipo_manana)
                .order_by("hora_salida")
                .first()
            )

        if proximo_manana:
            salidas.append({
                "origen": origen,
                "estado": f"Mañana a las {proximo_manana.hora_salida.strftime('%H:%M')} a.m.",
                "chip": "MAÑANA",
            })
        elif feriado_hoy and feriado_hoy.sin_servicio:
            salidas.append({"origen": origen, "estado": "Sin recorrido", "chip": None})
        else:
            salidas.append({"origen": origen, "estado": "Sin salidas próximas", "chip": None})

    if feriado_hoy:
        hoy_label = f"Hoy es Feriado: {feriado_hoy.nombre}"
    else:
        hoy_label = f"Hoy es {DIAS[hoy.weekday()]} {hoy.day} de {MESES[hoy.month - 1]}"

    return render(request, "sitio/inicio.html", {"hoy_label": hoy_label, "salidas": salidas})


def horarios(request):
    origenes = list(Ruta.objects.order_by("id").values_list("origen", flat=True).distinct())

    tarjetas = []
    for valor, etiqueta in Horario.TipoDia.choices:
        qs = Horario.objects.filter(tipo_dia=valor).select_related("ruta").order_by("ruta__id", "hora_salida")
        por_origen = {origen: [] for origen in origenes}
        especial = False
        for h in qs:
            por_origen.setdefault(h.ruta.origen, []).append(h.hora_salida.strftime("%H:%M"))
            if h.es_horario_especial:
                especial = True

        ciudades = [{"nombre": origen, "horas": horas} for origen, horas in por_origen.items()]
        tarjetas.append({
            "valor": valor,
            "etiqueta": etiqueta,
            "ciudades": ciudades,
            "especial": especial,
        })

    return render(request, "sitio/horarios.html", {"tarjetas": tarjetas})


def contacto(request):
    oficinas = Oficina.objects.prefetch_related("horarios")
    context = {
        "oficinas_aysen": [o for o in oficinas if o.ciudad == "Puerto Aysén"],
        "oficinas_coyhaique": [o for o in oficinas if o.ciudad == "Coyhaique"],
    }
    return render(request, "sitio/contacto.html", context)


def ruta(request):
    return render(request, "sitio/ruta.html")
