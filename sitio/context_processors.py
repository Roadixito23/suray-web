from urllib.parse import urlparse

from django.conf import settings


def site_version(request):
    return {'site_version': getattr(settings, 'SITE_VERSION', '')}


def _sin_www(host):
    return host.lower().split(':')[0].removeprefix('www.')


def es_dominio_publico(request):
    """True si la peticion llega al dominio de SITE_URL (con o sin www); otros dominios no se indexan."""
    return _sin_www(request.get_host()) == _sin_www(urlparse(settings.SITE_URL).netloc)


def site_url(request):
    return {'site_url': settings.SITE_URL, 'site_indexable': es_dominio_publico(request)}
