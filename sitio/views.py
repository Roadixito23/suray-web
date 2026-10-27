import json
from datetime import timedelta

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseNotModified, JsonResponse
from django.db.models import Q
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from . import vivo
from .context_processors import es_dominio_publico
from .clima import clima_actual
from .models import Aviso, Feriado, Horario, Oficina, Ruta

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


def _contexto_inicio():
    hoy = timezone.localdate()
    ahora = timezone.localtime().time()
    manana = hoy + timedelta(days=1)

    feriado_hoy = Feriado.objects.filter(fecha=hoy).first()
    feriado_manana = Feriado.objects.filter(fecha=manana).first()

    tipo_hoy = _tipo_dia_para(hoy, feriado_hoy is not None)
    tipo_manana = _tipo_dia_para(manana, feriado_manana is not None)

    clima = clima_actual()
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
        salidas[-1]["clima"] = clima.get(origen)

    if feriado_hoy:
        hoy_label = f"Hoy es feriado: {feriado_hoy.nombre}"
    else:
        hoy_label = f"Hoy es {DIAS[hoy.weekday()]} {hoy.day} de {MESES[hoy.month - 1]}"

    avisos = (
        Aviso.objects.filter(activo=True)
        .filter(Q(desde__isnull=True) | Q(desde__lte=hoy))
        .filter(Q(hasta__isnull=True) | Q(hasta__gte=hoy))
    )
    orden = {Aviso.Tipo.SUSPENSION: 0, Aviso.Tipo.OFERTA: 1, Aviso.Tipo.INFO: 2}
    avisos = sorted(avisos, key=lambda a: orden[a.tipo])  # estable: dentro del tipo, el mas nuevo primero
    zonas = {p: [] for p in Aviso.Posicion.values}
    for a in avisos:
        zonas[a.posicion].append(a)

    return {
        "hoy_label": hoy_label, "salidas": salidas,
        "avisos_arriba": zonas["arriba"], "avisos_medio": zonas["medio"], "avisos_boton": zonas["boton"],
    }


def _contexto_horarios():
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

    return {"tarjetas": tarjetas}


def inicio(request):
    html, etag = vivo.construir("inicio")
    return render(request, "sitio/inicio.html", {"vivo_html": html, "vivo_etag": etag})


def horarios(request):
    html, etag = vivo.construir("horarios")
    return render(request, "sitio/horarios.html", {
        "vivo_html": html, "vivo_etag": etag,
        "meta_descripcion": "Horarios de salida de Buses Suray entre Puerto Aysén y Coyhaique: lunes a viernes, sábado, domingo y feriados.",
    })


@require_GET
def vivo_fragmento(request, nombre):
    if nombre not in vivo.PARCIALES:
        raise Http404
    html, etag = vivo.fragmento(nombre)
    if request.headers.get("If-None-Match") == etag:
        respuesta = HttpResponseNotModified()
    else:
        respuesta = HttpResponse(html)
    respuesta["ETag"] = etag
    respuesta["Cache-Control"] = "no-cache"
    respuesta["X-Robots-Tag"] = "noindex"
    respuesta["X-Site-Version"] = settings.SITE_VERSION
    return respuesta


@require_GET
def favicon(request):
    # Los navegadores piden /favicon.ico aunque la pagina declare otro icono.
    return redirect(static("icons/favicon.ico"), permanent=True)


@require_GET
def robots(request):
    if not es_dominio_publico(request):
        return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain; charset=utf-8")
    lineas = [
        "User-agent: *",
        "Disallow: /edit/",
        "Disallow: /admin/",
        "Disallow: /vivo/",
        "Disallow: /deploy/",
        "",
        f"Sitemap: {settings.SITE_URL}/sitemap.xml",
        "",
    ]
    return HttpResponse("\n".join(lineas), content_type="text/plain; charset=utf-8")


@require_GET
def sitemap(request):
    urls = "".join(
        f"<url><loc>{settings.SITE_URL}{reverse('sitio:' + nombre)}</loc></url>"
        for nombre in ("inicio", "horarios", "ruta", "contacto")
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    )
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")


@require_GET
def manifest(request):
    datos = {
        "name": "Buses Suray | Suray Cargo",
        "short_name": "Buses Suray",
        "description": "Horarios, rutas y contacto de Buses Suray entre Puerto Aysén y Coyhaique.",
        "lang": "es-CL",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#001959",
        "theme_color": "#001959",
        "icons": [
            {"src": static("icons/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": static("icons/icon-512.png"), "sizes": "512x512", "type": "image/png"},
            {"src": static("icons/icon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    return JsonResponse(datos, content_type="application/manifest+json")


def _jsonld_contacto(oficinas):
    """Datos estructurados de las oficinas (telefono y direccion) como <script> JSON-LD."""
    datos = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "BusStation",
                "name": f"Buses Suray - {o.get_tipo_display()} ({o.ciudad})",
                "telephone": o.telefono,
                "url": f"{settings.SITE_URL}{reverse('sitio:contacto')}",
                **({"hasMap": o.mapa_url} if o.mapa_url else {}),
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": o.direccion,
                    "addressLocality": o.ciudad,
                    "addressRegion": "Aysén",
                    "addressCountry": "CL",
                },
            }
            for o in oficinas
        ],
    }
    # "<" escapado para que ningun texto editable en /edit/ pueda cerrar el <script>.
    cuerpo = json.dumps(datos, ensure_ascii=False).replace("<", "\\u003c")
    return f'<script type="application/ld+json">{cuerpo}</script>'


def contacto(request):
    oficinas = Oficina.objects.prefetch_related("horarios")
    context = {
        "jsonld_contacto": _jsonld_contacto(oficinas),
        "meta_descripcion": "Teléfonos, direcciones y horarios de atención de las oficinas de Buses Suray en Puerto Aysén y Coyhaique.",
        "ciudades": [
            (ciudad, [o for o in oficinas if o.ciudad == ciudad])
            for ciudad in ("Puerto Aysén", "Coyhaique")
        ],
    }
    return render(request, "sitio/contacto.html", context)


def ruta(request):
    # Coordenadas de los terminales, migradas desde paraderos_page.dart.
    # Se serializan a JSON en la vista para evitar que Django las formatee
    # con coma decimal (locale es-cl) y rompa la sintaxis del script inline.
    puerto_aysen = {"lat": -45.40111614852224, "lng": -72.68738064167634}
    coyhaique = {"lat": -45.582039, "lng": -72.078136}
    context = {
        "meta_descripcion": "Mapa de la ruta 240 entre Puerto Aysén y Coyhaique, con la ubicación de los terminales de Buses Suray.",
        "puerto_aysen_json": json.dumps(puerto_aysen),
        "coyhaique_json": json.dumps(coyhaique),
    }
    return render(request, "sitio/ruta.html", context)
