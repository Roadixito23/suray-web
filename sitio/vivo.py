"""Fragmentos de Inicio y Horarios que la pagina vuelve a pedir sola (ver static/js/tiempo-real.js)."""
import hashlib

from datetime import timedelta

from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils import timezone

TTL = 15  # segundos: cota maxima de retraso para cambios hechos fuera del panel

PARCIALES = {
    "inicio": "sitio/_inicio_vivo.html",
    "horarios": "sitio/_horarios_vivo.html",
}


def _contexto(nombre):
    from . import views  # import tardio: views importa este modulo
    return views._contexto_inicio() if nombre == "inicio" else views._contexto_horarios()


def construir(nombre):
    """Renderiza el fragmento sin cache. Devuelve (html, etag)."""
    html = render_to_string(PARCIALES[nombre], _contexto(nombre))
    return html, '"%s"' % hashlib.md5(html.encode()).hexdigest()


def _clave(nombre, momento):
    # El minuto va en la clave: "proxima salida" depende del reloj, asi que al cambiar el minuto
    # el fragmento se recalcula aunque no hayan pasado los TTL segundos.
    return f"vivo:{nombre}:{momento:%H:%M}"


def fragmento(nombre):
    """Como construir(), pero cacheado: cada sondeo es una lectura de cache, no ~10 consultas."""
    clave = _clave(nombre, timezone.localtime())
    resultado = cache.get(clave)
    if resultado is None:
        resultado = construir(nombre)
        cache.set(clave, resultado, TTL)
    return resultado


def invalidar():
    ahora = timezone.localtime()
    # Minuto actual y el anterior, por si el fragmento se cacheo justo antes de cruzar el minuto.
    claves = [_clave(nombre, m) for nombre in PARCIALES for m in (ahora, ahora - timedelta(minutes=1))]
    cache.delete_many(claves)
