"""Fragmentos de Inicio y Horarios que la pagina vuelve a pedir sola (ver static/js/tiempo-real.js)."""
import hashlib

from django.core.cache import cache
from django.template.loader import render_to_string

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


def fragmento(nombre):
    """Como construir(), pero cacheado: cada sondeo es una lectura de cache, no ~10 consultas."""
    clave = f"vivo:{nombre}"
    resultado = cache.get(clave)
    if resultado is None:
        resultado = construir(nombre)
        cache.set(clave, resultado, TTL)
    return resultado


def invalidar():
    cache.delete_many([f"vivo:{nombre}" for nombre in PARCIALES])
