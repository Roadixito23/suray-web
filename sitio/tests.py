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


LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
STORAGES_SIMPLES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


@override_settings(CACHES=LOCMEM, STORAGES=STORAGES_SIMPLES)
class EditPanelTests(TestCase):
    def setUp(self):
        from datetime import time

        from django.contrib.auth.models import User
        from django.core.cache import cache

        from .models import Horario, Ruta

        cache.clear()
        self.Horario = Horario
        self.time = time
        self.aysen = Ruta.objects.create(origen='Puerto Aysén', destino='Coyhaique')
        self.coy = Ruta.objects.create(origen='Coyhaique', destino='Puerto Aysén')
        self.staff = User.objects.create_user('staff', password='clave-segura-1', is_staff=True)
        self.normal = User.objects.create_user('normal', password='clave-segura-1')
        self.url = '/edit/horarios/lv/'

    def tipo(self):
        return self.Horario.TipoDia.LUNES_VIERNES

    def entrar(self):
        self.client.force_login(self.staff)

    def horas(self, ruta):
        return [
            h.hora_salida.strftime('%H:%M')
            for h in self.Horario.objects.filter(ruta=ruta, tipo_dia=self.tipo()).order_by('hora_salida')
        ]

    def test_anonimo_va_al_login(self):
        r = self.client.get(self.url)
        self.assertRedirects(r, '/edit/login/?next=/edit/horarios/lv/', fetch_redirect_response=False)

    def test_no_staff_no_puede_entrar(self):
        r = self.client.post('/edit/login/', {'username': 'normal', 'password': 'clave-segura-1'})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.client.force_login(self.normal)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_staff_inicia_sesion(self):
        r = self.client.post('/edit/login/', {'username': 'staff', 'password': 'clave-segura-1'})
        self.assertRedirects(r, '/edit/', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/edit/').status_code, 302)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_next_externo_se_ignora(self):
        r = self.client.post(
            '/edit/login/?next=https://malo.example/',
            {'username': 'staff', 'password': 'clave-segura-1', 'next': 'https://malo.example/'},
        )
        self.assertRedirects(r, '/edit/', fetch_redirect_response=False)

    def test_respuestas_no_indexables(self):
        r = self.client.get('/edit/login/')
        self.assertIn('noindex', r['X-Robots-Tag'])
        self.assertIn('noindex', r.content.decode())
        self.entrar()
        r = self.client.get(self.url)
        self.assertIn('noindex', r['X-Robots-Tag'])
        self.assertIn('no-store', r['Cache-Control'])

    def test_bloqueo_tras_5_fallos(self):
        for _ in range(5):
            r = self.client.post('/edit/login/', {'username': 'staff', 'password': 'mala'})
            self.assertEqual(r.status_code, 200)
        r = self.client.post('/edit/login/', {'username': 'staff', 'password': 'clave-segura-1'})
        self.assertEqual(r.status_code, 429)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_guardar_crea_y_quita_horarios(self):
        self.Horario.objects.create(ruta=self.aysen, tipo_dia=self.tipo(), hora_salida=self.time(6, 0))
        self.Horario.objects.create(ruta=self.aysen, tipo_dia=self.tipo(), hora_salida=self.time(7, 0))
        self.entrar()
        r = self.client.post(self.url, {
            f'horas_{self.aysen.id}': ['07:00', '8:15', '', '07:00'],
            f'horas_{self.coy.id}': ['09:30'],
        })
        self.assertRedirects(r, self.url, fetch_redirect_response=False)
        self.assertEqual(self.horas(self.aysen), ['07:00', '08:15'])
        self.assertEqual(self.horas(self.coy), ['09:30'])

    def test_hora_invalida_no_guarda_nada(self):
        self.Horario.objects.create(ruta=self.aysen, tipo_dia=self.tipo(), hora_salida=self.time(6, 0))
        self.entrar()
        r = self.client.post(self.url, {
            f'horas_{self.aysen.id}': ['25:99'],
            f'horas_{self.coy.id}': ['09:30'],
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Usa el formato HH:MM')
        self.assertEqual(self.horas(self.aysen), ['06:00'])
        self.assertEqual(self.horas(self.coy), [])

    def test_marca_horario_especial_solo_en_su_tipo(self):
        sab = self.Horario.TipoDia.SABADO
        self.Horario.objects.create(ruta=self.aysen, tipo_dia=sab, hora_salida=self.time(10, 0))
        self.entrar()
        self.client.post(self.url, {f'horas_{self.aysen.id}': ['06:00'], 'especial': 'on'})
        self.assertTrue(self.Horario.objects.get(tipo_dia=self.tipo()).es_horario_especial)
        self.assertFalse(self.Horario.objects.get(tipo_dia=sab).es_horario_especial)

    def test_tipo_desconocido_da_404(self):
        self.entrar()
        self.assertEqual(self.client.get('/edit/horarios/xx/').status_code, 404)

    def test_cerrar_sesion_requiere_post(self):
        self.entrar()
        self.assertEqual(self.client.get('/edit/logout/').status_code, 405)
        r = self.client.post('/edit/logout/')
        self.assertRedirects(r, '/edit/login/', fetch_redirect_response=False)


class ClimaTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.delete('clima_actual')
        self.addCleanup(cache.delete, 'clima_actual')

    @staticmethod
    def _respuesta():
        datos = [
            {'current': {'temperature_2m': 9.6, 'weather_code': 63, 'is_day': 1}},
            {'current': {'temperature_2m': 7.2, 'weather_code': 0, 'is_day': 0}},
        ]
        resp = mock.MagicMock()
        resp.__enter__.return_value = resp
        resp.read.return_value = json.dumps(datos).encode()
        return resp

    def test_parsea_y_cachea(self):
        from sitio import clima
        with mock.patch('sitio.clima.urlopen', return_value=self._respuesta()) as m:
            datos = clima.clima_actual()
            clima.clima_actual()
        self.assertEqual(m.call_count, 1)
        self.assertEqual(datos['Puerto Aysén']['temperatura'], 10)
        self.assertEqual(datos['Puerto Aysén']['descripcion'], 'Lluvia')
        self.assertEqual(datos['Coyhaique']['icono'], '🌙')

    def test_falla_de_api_devuelve_vacio(self):
        from sitio import clima
        with mock.patch('sitio.clima.urlopen', side_effect=OSError('sin red')):
            self.assertEqual(clima.clima_actual(), {})

    @override_settings(STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    })
    def test_inicio_no_se_rompe_sin_clima(self):
        with mock.patch('sitio.clima.urlopen', side_effect=OSError('sin red')):
            self.assertEqual(self.client.get('/').status_code, 200)


class RutaMapaTests(TestCase):
    @override_settings(STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    })
    def test_mapa_se_muestra_sin_api_key(self):
        resp = self.client.get('/ruta/')
        self.assertContains(resp, 'id="rutaMap"')
        self.assertContains(resp, 'vendor/leaflet/leaflet.js')
        self.assertNotContains(resp, 'maps.googleapis.com')
