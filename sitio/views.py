import json
from datetime import timedelta

from django.shortcuts import render
from django.utils import timezone

from .models import ConfiguracionSitio, Feriado, Horario, Oficina, Ruta

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


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
        # Hasta 3 salidas: primero las que quedan hoy, luego las de manana.
        proximas = []
        if not (feriado_hoy and feriado_hoy.sin_servicio):
            horas = Horario.objects.filter(
                ruta__origen=origen, tipo_dia=tipo_hoy, hora_salida__gte=ahora
            ).order_by("hora_salida")[:3]
            proximas += [("hoy", h.hora_salida) for h in horas]
        if len(proximas) < 3 and not (feriado_manana and feriado_manana.sin_servicio):
            horas = Horario.objects.filter(
                ruta__origen=origen, tipo_dia=tipo_manana
            ).order_by("hora_salida")[: 3 - len(proximas)]
            proximas += [("mañana", h.hora_salida) for h in horas]

        if proximas:
            dia, hora = proximas[0]
            salidas.append({
                "origen": origen,
                "hora": hora.strftime("%H:%M"),
                "dia": dia,
                "despues": [
                    f"mañana {h.strftime('%H:%M')}" if d != dia else h.strftime("%H:%M")
                    for d, h in proximas[1:]
                ],
            })
        elif feriado_hoy and feriado_hoy.sin_servicio:
            salidas.append({"origen": origen, "aviso": "Sin recorrido hoy por feriado."})
        else:
            salidas.append({"origen": origen, "aviso": "Sin salidas próximas."})

    if feriado_hoy:
        hoy_label = f"Hoy es feriado: {feriado_hoy.nombre}"
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
        "ciudades": [
            (ciudad, [o for o in oficinas if o.ciudad == ciudad])
            for ciudad in ("Puerto Aysén", "Coyhaique")
        ],
    }
    return render(request, "sitio/contacto.html", context)


def ruta(request):
    config = ConfiguracionSitio.load()
    # Coordenadas de los terminales, migradas desde paraderos_page.dart.
    # Se serializan a JSON en la vista para evitar que Django las formatee
    # con coma decimal (locale es-cl) y rompa la sintaxis del script inline.
    puerto_aysen = {"lat": -45.40111614852224, "lng": -72.68738064167634}
    coyhaique = {"lat": -45.582039, "lng": -72.078136}
    context = {
        "google_maps_api_key": config.google_maps_api_key,
        "puerto_aysen_json": json.dumps(puerto_aysen),
        "coyhaique_json": json.dumps(coyhaique),
    }
    return render(request, "sitio/ruta.html", context)
