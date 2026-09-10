from django.conf import settings


def site_version(request):
    return {'site_version': getattr(settings, 'SITE_VERSION', '')}
