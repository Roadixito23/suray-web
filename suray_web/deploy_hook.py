"""
Webhook de GitHub que dispara el despliegue de test.suray.cl al instante.

Inactivo (404) mientras WEBHOOK_SECRET este vacio. El despliegue real lo hace
deploy/auto_deploy_test.py, lanzado en un proceso separado que hereda las
variables de entorno de la app (cPanel > Setup Python App).
"""
import hashlib
import hmac
import json
import logging
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 1024 * 1024
DEPLOY_REF = 'refs/heads/main'


def _firma_valida(secret, body, header):
    if not header or not header.startswith('sha256='):
        return False
    esperada = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, header)


def _lanzar_despliegue():
    """Lanza el script de despliegue desvinculado del request. Rutas fijas desde settings."""
    try:
        with open(settings.DEPLOY_LAUNCH_LOG, 'ab') as log:
            subprocess.Popen(
                [sys.executable, settings.DEPLOY_SCRIPT],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
    except Exception:
        logger.exception('No se pudo lanzar el despliegue; se crea el marcador')
        try:
            flag = Path(settings.DEPLOY_FLAG_FILE)
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.touch()
        except OSError:
            logger.exception('No se pudo crear el marcador de despliegue')


@csrf_exempt
def webhook(request):
    secret = settings.WEBHOOK_SECRET
    if not secret:
        return HttpResponse(status=404)
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    body = request.read(MAX_BODY_BYTES + 1)
    if len(body) > MAX_BODY_BYTES:
        return HttpResponse(status=413)

    if not _firma_valida(secret, body, request.headers.get('X-Hub-Signature-256')):
        logger.warning('Webhook de despliegue con firma invalida')
        return HttpResponse(status=403)

    evento = request.headers.get('X-GitHub-Event', '')
    if evento == 'ping':
        return HttpResponse('pong', status=200)
    if evento != 'push':
        return HttpResponse(status=202)

    try:
        ref = json.loads(body).get('ref')
    except (ValueError, AttributeError):
        return HttpResponse(status=400)
    if ref != DEPLOY_REF:
        return HttpResponse(status=202)

    logger.info('Webhook push a main: lanzando despliegue')
    _lanzar_despliegue()
    return HttpResponse(status=202)
