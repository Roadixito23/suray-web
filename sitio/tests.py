import hashlib
import hmac
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

SECRET = 'secreto-de-prueba'
URL = '/deploy/webhook/'


def firmar(body, secret=SECRET):
    return 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class WebhookDeployTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.flag = self.tmp / 'deploy.flag'
        override = override_settings(
            WEBHOOK_SECRET=SECRET,
            DEPLOY_SCRIPT='/ruta/fija/auto_deploy_test.py',
            DEPLOY_FLAG_FILE=str(self.flag),
            DEPLOY_LAUNCH_LOG=str(self.tmp / 'launch.log'),
        )
        override.enable()
        self.addCleanup(override.disable)

    def post(self, evento, payload, firma=None, secret=SECRET):
        body = json.dumps(payload).encode()
        headers = {'HTTP_X_GITHUB_EVENT': evento}
        if firma is None:
            firma = firmar(body, secret)
        if firma:
            headers['HTTP_X_HUB_SIGNATURE_256'] = firma
        return self.client.post(URL, body, content_type='application/json', **headers)

    def test_sin_secreto_responde_404(self):
        with override_settings(WEBHOOK_SECRET=''):
            self.assertEqual(self.client.post(URL).status_code, 404)

    def test_get_responde_405(self):
        self.assertEqual(self.client.get(URL).status_code, 405)

    def test_firma_invalida_responde_403(self):
        with mock.patch('subprocess.Popen') as popen:
            r = self.post('push', {'ref': 'refs/heads/main'}, secret='otro')
            self.assertEqual(r.status_code, 403)
            popen.assert_not_called()

    def test_firma_ausente_responde_403(self):
        r = self.post('push', {'ref': 'refs/heads/main'}, firma='')
        self.assertEqual(r.status_code, 403)

    def test_cuerpo_demasiado_grande_responde_413(self):
        body = b'x' * (1024 * 1024 + 1)
        r = self.client.post(URL, body, content_type='application/json',
                             HTTP_X_HUB_SIGNATURE_256=firmar(body))
        self.assertEqual(r.status_code, 413)

    def test_ping_responde_200(self):
        self.assertEqual(self.post('ping', {'zen': 'x'}).status_code, 200)

    def test_push_a_main_lanza_despliegue(self):
        with mock.patch('subprocess.Popen') as popen:
            r = self.post('push', {'ref': 'refs/heads/main'})
        self.assertEqual(r.status_code, 202)
        popen.assert_called_once()
        cmd = popen.call_args.args[0]
        self.assertEqual(cmd[1], '/ruta/fija/auto_deploy_test.py')
        self.assertTrue(popen.call_args.kwargs['start_new_session'])

    def test_push_a_otra_rama_no_lanza(self):
        with mock.patch('subprocess.Popen') as popen:
            r = self.post('push', {'ref': 'refs/heads/otra'})
        self.assertEqual(r.status_code, 202)
        popen.assert_not_called()

    def test_otro_evento_no_lanza(self):
        with mock.patch('subprocess.Popen') as popen:
            r = self.post('issues', {'ref': 'refs/heads/main'})
        self.assertEqual(r.status_code, 202)
        popen.assert_not_called()

    def test_fallo_de_popen_crea_marcador(self):
        with mock.patch('subprocess.Popen', side_effect=OSError('boom')):
            r = self.post('push', {'ref': 'refs/heads/main'})
        self.assertEqual(r.status_code, 202)
        self.assertTrue(self.flag.exists())
