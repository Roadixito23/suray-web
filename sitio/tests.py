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

    def test_pagina_de_horarios_carga_el_formato_automatico_hh_mm(self):
        self.entrar()
        r = self.client.get(self.url)
        self.assertContains(r, 'js/formato-hora.js')
        self.assertContains(r, 'name="horas_%d"' % self.aysen.id)
        self.assertContains(r, 'maxlength="5"')

    def test_guardar_acepta_las_horas_tal_como_las_deja_el_formato_automatico(self):
        self.entrar()
        self.client.post(self.url, {f'horas_{self.aysen.id}': ['07:30', '18:45', '00:00', '23:59']})
        self.assertEqual(self.horas(self.aysen), ['00:00', '07:30', '18:45', '23:59'])

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


@override_settings(CACHES=LOCMEM, STORAGES=STORAGES_SIMPLES)
class EditAdministracionTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        from .models import Feriado, HorarioOficina, Oficina

        self.Feriado, self.HorarioOficina = Feriado, HorarioOficina
        self.staff = User.objects.create_user('staff', password='clave-segura-1', is_staff=True)
        self.oficina = Oficina.objects.create(
            ciudad='Coyhaique', tipo='PJ', direccion='Calle 1', telefono='+56 1', orden=1)
        self.h1 = HorarioOficina.objects.create(oficina=self.oficina, dia='Lun-Vie', horario='06:30–19:00', orden=1)
        self.h2 = HorarioOficina.objects.create(oficina=self.oficina, dia='Domingo', horario='Cerrado', orden=2)

    def entrar(self):
        self.client.force_login(self.staff)

    def test_secciones_exigen_login(self):
        for url in ('/edit/oficinas/', '/edit/feriados/', '/edit/avisos/', '/edit/cuenta/'):
            self.assertEqual(self.client.get(url).status_code, 302, url)
        self.assertEqual(self.client.post(f'/edit/oficinas/{self.oficina.pk}/', {}).status_code, 302)

    def datos_oficina(self, **extra):
        p, o = f'h{self.oficina.pk}', f'of{self.oficina.pk}'
        datos = {
            f'{o}-direccion': 'Calle 2', f'{o}-telefono': '+56 2', f'{o}-mapa_url': '',
            f'{p}-TOTAL_FORMS': '3', f'{p}-INITIAL_FORMS': '2', f'{p}-MIN_NUM_FORMS': '0', f'{p}-MAX_NUM_FORMS': '1000',
            f'{p}-0-id': self.h1.pk, f'{p}-0-oficina': self.oficina.pk, f'{p}-0-dia': 'Lun-Vie', f'{p}-0-horario': '07:00–20:00',
            f'{p}-1-id': self.h2.pk, f'{p}-1-oficina': self.oficina.pk, f'{p}-1-dia': 'Domingo', f'{p}-1-horario': 'Cerrado',
            f'{p}-1-DELETE': 'on',
            f'{p}-2-id': '', f'{p}-2-oficina': self.oficina.pk, f'{p}-2-dia': 'Sábado', f'{p}-2-horario': '09:00–13:00',
        }
        datos.update(extra)
        return datos

    def test_pagina_oficinas_muestra_horarios(self):
        self.entrar()
        r = self.client.get('/edit/oficinas/')
        self.assertContains(r, 'Calle 1')
        self.assertContains(r, '06:30–19:00')

    def test_guardar_oficina_edita_agrega_y_quita_horarios(self):
        self.entrar()
        r = self.client.post(f'/edit/oficinas/{self.oficina.pk}/', self.datos_oficina())
        self.assertRedirects(r, f'/edit/oficinas/#oficina-{self.oficina.pk}', fetch_redirect_response=False)
        self.oficina.refresh_from_db()
        self.assertEqual(self.oficina.direccion, 'Calle 2')
        filas = [(h.dia, h.horario) for h in self.oficina.horarios.all()]
        self.assertEqual(filas, [('Lun-Vie', '07:00–20:00'), ('Sábado', '09:00–13:00')])

    def test_oficina_invalida_no_guarda(self):
        self.entrar()
        datos = self.datos_oficina(**{f'h{self.oficina.pk}-0-horario': '', f'of{self.oficina.pk}-mapa_url': 'no-es-url'})
        r = self.client.post(f'/edit/oficinas/{self.oficina.pk}/', datos)
        self.assertEqual(r.status_code, 200)
        self.oficina.refresh_from_db()
        self.assertEqual(self.oficina.direccion, 'Calle 1')
        self.assertEqual(self.oficina.horarios.count(), 2)

    def test_feriados_agregar_duplicado_y_eliminar(self):
        self.entrar()
        r = self.client.post('/edit/feriados/', {'fecha': '2099-05-01', 'nombre': 'Día del Trabajo', 'sin_servicio': 'on'})
        self.assertRedirects(r, '/edit/feriados/', fetch_redirect_response=False)
        f = self.Feriado.objects.get(fecha='2099-05-01')
        self.assertTrue(f.sin_servicio)
        r = self.client.post('/edit/feriados/', {'fecha': '2099-05-01', 'nombre': 'Otro'})
        self.assertContains(r, 'Ya hay un feriado en esa fecha.')
        self.client.post('/edit/feriados/', {'accion': 'eliminar', 'feriado': f.pk})
        self.assertFalse(self.Feriado.objects.exists())

    def test_cuenta_cambia_usuario_y_clave_sin_cerrar_sesion(self):
        self.entrar()
        r = self.client.post('/edit/cuenta/', {
            'username': 'nuevo', 'password_actual': 'mala', 'password1': '', 'password2': ''})
        self.assertContains(r, 'La contraseña actual no es correcta.')
        r = self.client.post('/edit/cuenta/', {
            'username': 'nuevo', 'password_actual': 'clave-segura-1',
            'password1': 'otra-clave-larga-9', 'password2': 'otra-clave-larga-9'})
        self.assertRedirects(r, '/edit/cuenta/', fetch_redirect_response=False)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.username, 'nuevo')
        self.assertTrue(self.staff.check_password('otra-clave-larga-9'))
        self.assertEqual(self.client.get('/edit/cuenta/').status_code, 200)

    def test_cuenta_rechaza_clave_debil_y_usuario_repetido(self):
        from django.contrib.auth.models import User
        User.objects.create_user('otro')
        self.entrar()
        r = self.client.post('/edit/cuenta/', {
            'username': 'otro', 'password_actual': 'clave-segura-1', 'password1': '123', 'password2': '123'})
        self.assertContains(r, 'Ese nombre de usuario ya existe.')
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.username, 'staff')
        self.assertTrue(self.staff.check_password('clave-segura-1'))


class WebhookRamaTests(TestCase):
    """En suray.cl el webhook solo reacciona a produccion, en test.suray.cl solo a main."""

    def post_push(self, ref):
        body = json.dumps({'ref': ref}).encode()
        with mock.patch('subprocess.Popen') as popen:
            r = self.client.post(URL, body, content_type='application/json',
                                 HTTP_X_GITHUB_EVENT='push', HTTP_X_HUB_SIGNATURE_256=firmar(body))
        return r, popen

    @override_settings(WEBHOOK_SECRET=SECRET, DEPLOY_BRANCH='produccion',
                       DEPLOY_LAUNCH_LOG=tempfile.gettempdir() + '/launch-test.log')
    def test_produccion_solo_despliega_su_rama(self):
        r, popen = self.post_push('refs/heads/produccion')
        self.assertEqual(r.status_code, 202)
        popen.assert_called_once()
        r, popen = self.post_push('refs/heads/main')
        self.assertEqual(r.status_code, 202)
        popen.assert_not_called()

    @override_settings(WEBHOOK_SECRET=SECRET, DEPLOY_BRANCH='main')
    def test_test_ignora_produccion(self):
        _, popen = self.post_push('refs/heads/produccion')
        popen.assert_not_called()


class ScriptDespliegueTests(TestCase):
    """El script se configura por entorno: test conserva sus nombres, produccion usa los suyos."""

    def cargar(self, **entorno):
        import importlib.util
        ruta = Path(__file__).resolve().parent.parent / 'deploy' / 'auto_deploy_test.py'
        spec = importlib.util.spec_from_file_location('auto_deploy_probe', ruta)
        modulo = importlib.util.module_from_spec(spec)
        base = {k: v for k, v in __import__('os').environ.items() if not k.startswith('DEPLOY_')}
        with mock.patch.dict('os.environ', {**base, **entorno}, clear=True):
            spec.loader.exec_module(modulo)
        return modulo

    def test_valores_por_defecto_son_los_de_test(self):
        m = self.cargar()
        self.assertEqual(m.BRANCH, 'main')
        self.assertTrue(m.DEPLOY_TARGET.endswith('/public_html/test.suray.cl'))
        self.assertTrue(m.LOG_FILE.endswith('/test_deploy.log'))
        self.assertTrue(m.LOCK_FILE.endswith('/deploy.lock'))
        self.assertTrue(m.FLAG_FILE.endswith('/deploy.flag'))
        self.assertTrue(m.ENV_FILE.endswith('/deploy.env'))

    def test_produccion_usa_su_rama_destino_y_archivos(self):
        m = self.cargar(DEPLOY_NAME='produccion', DEPLOY_BRANCH='produccion',
                        DEPLOY_TARGET='/home/x/public_html/suray.cl', DEPLOY_DIR='/home/x/d')
        self.assertEqual(m.BRANCH, 'produccion')
        self.assertTrue(m.API_COMMIT_URL.endswith('/commits/produccion'))
        self.assertTrue(m.TARBALL_URL.endswith('/tarball/produccion'))
        self.assertEqual(m.DEPLOY_TARGET, '/home/x/public_html/suray.cl')
        self.assertEqual(m.STATE_FILE, '/home/x/d/produccion_deploy_state.json')
        self.assertEqual(m.LOG_FILE, '/home/x/d/produccion_deploy.log')
        self.assertEqual(m.LOCK_FILE, '/home/x/d/produccion_deploy.lock')
        self.assertEqual(m.FLAG_FILE, '/home/x/d/produccion_deploy.flag')
        self.assertEqual(m.ENV_FILE, '/home/x/d/produccion_deploy.env')


class VivoTests(TestCase):
    """Fragmentos de Inicio y Horarios que la pagina vuelve a pedir sola."""

    def setUp(self):
        from datetime import time

        from django.contrib.auth.models import User
        from django.core.cache import cache

        from .models import Feriado, Horario, Ruta

        cache.clear()
        self.addCleanup(cache.clear)
        self.Horario, self.Feriado, self.time = Horario, Feriado, time
        from .models import Aviso
        self.Aviso = Aviso
        self.ruta = Ruta.objects.create(origen='Coyhaique', destino='Puerto Aysén')
        self.staff = User.objects.create_user('staff', password='clave-segura-1', is_staff=True)
        patcher = mock.patch('sitio.views.clima_actual', return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)

    def hora_local(self, y, m, d, hh, mm):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        return datetime(y, m, d, hh, mm, tzinfo=ZoneInfo('America/Santiago'))

    def crear(self, hh, mm, tipo=None):
        return self.Horario.objects.create(
            ruta=self.ruta, tipo_dia=tipo or self.Horario.TipoDia.LUNES_VIERNES, hora_salida=self.time(hh, mm))

    def test_fragmentos_con_etag_y_cabeceras(self):
        for nombre in ('inicio', 'horarios'):
            r = self.client.get(f'/vivo/{nombre}/')
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r['ETag'])
            self.assertEqual(r['Cache-Control'], 'no-cache')
            self.assertEqual(r['X-Robots-Tag'], 'noindex')

    def test_nombre_desconocido_y_metodo_no_permitido(self):
        self.assertEqual(self.client.get('/vivo/otro/').status_code, 404)
        self.assertEqual(self.client.post('/vivo/inicio/').status_code, 405)

    def test_if_none_match_devuelve_304(self):
        etag = self.client.get('/vivo/horarios/')['ETag']
        r = self.client.get('/vivo/horarios/', headers={'If-None-Match': etag})
        self.assertEqual(r.status_code, 304)
        self.assertEqual(r.content, b'')

    def test_la_pagina_completa_trae_el_mismo_etag_que_el_fragmento(self):
        self.crear(8, 0)
        from django.utils.html import escape

        for url, nombre in (('/', 'inicio'), ('/horarios/', 'horarios')):
            pagina = self.client.get(url)
            etag = self.client.get(f'/vivo/{nombre}/')['ETag']
            self.assertContains(pagina, 'data-live-etag="%s"' % escape(etag))
            self.assertContains(pagina, '/static/js/tiempo-real.')

    def test_crear_un_horario_cambia_el_fragmento_al_instante(self):
        antes = self.client.get('/vivo/horarios/')
        self.crear(6, 45)
        despues = self.client.get('/vivo/horarios/')
        self.assertNotEqual(antes['ETag'], despues['ETag'])
        self.assertContains(despues, '06:45')

    def test_guardar_desde_el_panel_invalida_sin_esperar_el_ttl(self):
        self.client.force_login(self.staff)
        antes = self.client.get('/vivo/horarios/')['ETag']
        r = self.client.post('/edit/horarios/lv/', {f'horas_{self.ruta.id}': ['07:10']})
        self.assertEqual(r.status_code, 302)
        r = self.client.get('/vivo/horarios/')
        self.assertNotEqual(r['ETag'], antes)
        self.assertContains(r, '07:10')

    def test_marcar_horario_especial_tambien_se_ve(self):
        self.crear(8, 0)
        self.client.force_login(self.staff)
        self.assertNotContains(self.client.get('/vivo/horarios/'), 'Horario especial')
        self.client.post('/edit/horarios/lv/', {f'horas_{self.ruta.id}': ['08:00'], 'especial': 'on'})
        self.assertContains(self.client.get('/vivo/horarios/'), 'Horario especial')

    def test_feriado_del_panel_cambia_inicio(self):
        self.crear(23, 0)
        self.client.force_login(self.staff)
        hoy = self.hora_local(2026, 10, 21, 10, 0)  # miercoles
        with mock.patch('django.utils.timezone.now', return_value=hoy):
            antes = self.client.get('/vivo/inicio/')
            self.assertContains(antes, 'Hoy es miércoles')
            self.client.post('/edit/feriados/', {'fecha': '2026-10-21', 'nombre': 'Dia de prueba', 'sin_servicio': 'on'})
            despues = self.client.get('/vivo/inicio/')
        self.assertNotEqual(antes['ETag'], despues['ETag'])
        self.assertContains(despues, 'Hoy es feriado: Dia de prueba')

    def datos_aviso(self, **extra):
        datos = {
            'tipo': 'info', 'titulo': 'Aviso', 'posicion': 'arriba', 'formato': 'simple',
            'direccion': 'izq_der', 'velocidad': 'normal',
            'estilo_color': 'borde', 'color_principal': '#F47200', 'color_secundario': '#001959', 'activo': 'on',
        }
        datos.update(extra)
        return datos

    def test_aviso_aparece_en_la_zona_elegida(self):
        self.crear(23, 0)
        for posicion in ('arriba', 'medio', 'boton'):
            self.Aviso.objects.create(titulo=f'En {posicion}', posicion=posicion)
        html = self.client.get('/vivo/inicio/').content.decode()
        pos = {p: html.index(f'En {p}') for p in ('arriba', 'medio', 'boton')}
        self.assertLess(pos['arriba'], html.index('Próximas salidas'))
        self.assertLess(html.index('Próximas salidas'), pos['medio'])
        self.assertLess(pos['medio'], html.index('Todos los horarios'))
        self.assertGreater(pos['boton'], html.index('Todos los horarios'))

    def test_boton_todos_los_horarios_sigue_en_la_portada(self):
        self.assertContains(self.client.get('/'), 'Todos los horarios')

    def test_carrusel_es_un_noticiero_con_texto_corrido(self):
        self.Aviso.objects.create(titulo='Noticia', mensaje='Linea uno\nLinea dos', formato='carrusel')
        html = self.client.get('/vivo/inicio/').content.decode()
        self.assertIn('data-ticker', html)
        self.assertIn('Linea uno · Linea dos', html)
        self.assertEqual(html.count('Linea uno · Linea dos'), 2)  # copia para el bucle continuo
        self.assertEqual(html.count('aria-hidden="true">Linea'), 1)

    def test_fechas_en_formato_chile_se_guardan_y_se_muestran_asi(self):
        self.client.force_login(self.staff)
        self.client.post('/edit/avisos/', self.datos_aviso(titulo='Chile', desde='25-12-2026', hasta='31/12/2026'))
        aviso = self.Aviso.objects.get(titulo='Chile')
        self.assertEqual((str(aviso.desde), str(aviso.hasta)), ('2026-12-25', '2026-12-31'))
        self.assertContains(self.client.get(f'/edit/avisos/{aviso.pk}/'), 'value="25-12-2026"')
        r = self.client.post('/edit/feriados/', {'fecha': '01-05-2099', 'nombre': 'Trabajo'})
        self.assertEqual(str(self.Feriado.objects.get(nombre='Trabajo').fecha), '2099-05-01')

    def test_fecha_invalida_pide_formato_chile(self):
        self.client.force_login(self.staff)
        r = self.client.post('/edit/avisos/', self.datos_aviso(desde='31-02-2026'))
        self.assertContains(r, 'DD-MM-AAAA')
        self.assertFalse(self.Aviso.objects.exists())

    def test_direccion_y_velocidad_del_noticiero(self):
        self.Aviso.objects.create(titulo='A', mensaje='x' * 100, formato='carrusel', direccion='der_izq', velocidad='lenta')
        self.Aviso.objects.create(titulo='B', mensaje='x' * 100, formato='carrusel', velocidad='rapida')
        html = self.client.get('/vivo/inicio/').content.decode()
        self.assertEqual(html.count('ticker--der_izq'), 1)
        self.assertEqual(html.count('ticker--izq_der'), 1)
        self.assertIn('animation-duration: 30s', html)  # 1200 px / 40 px/s
        self.assertIn('animation-duration: 9s', html)   # 1200 px / 140 px/s

    def test_direccion_y_velocidad_se_guardan_desde_el_panel(self):
        self.client.force_login(self.staff)
        self.client.post('/edit/avisos/', self.datos_aviso(
            titulo='Cinta', formato='carrusel', direccion='der_izq', velocidad='rapida'))
        a = self.Aviso.objects.get(titulo='Cinta')
        self.assertEqual((a.direccion, a.velocidad), ('der_izq', 'rapida'))

    def test_carrusel_sin_mensaje_solo_muestra_el_titulo(self):
        self.Aviso.objects.create(titulo='Solo titulo', formato='carrusel')
        html = self.client.get('/vivo/inicio/').content.decode()
        self.assertIn('Solo titulo', html)
        self.assertNotIn('data-ticker', html)

    def test_colores_propios_llegan_como_variables_css_con_contraste(self):
        self.Aviso.objects.create(
            titulo='Claro', estilo_color='solido', color_principal='#FFEE00', color_secundario='#001959')
        self.Aviso.objects.create(titulo='Oscuro', estilo_color='solido', color_principal='#001959')
        html = self.client.get('/vivo/inicio/').content.decode()
        self.assertIn('--n-main:#FFEE00;--n-alt:#001959;--n-ink:#000000', html)
        self.assertIn('--n-main:#001959;--n-alt:#001959;--n-ink:#FFFFFF', html)

    def test_sin_colores_propios_no_hay_estilo_en_linea(self):
        self.client.force_login(self.staff)
        self.client.post('/edit/avisos/', self.datos_aviso(titulo='Por defecto'))  # sin colores_propios
        aviso = self.Aviso.objects.get(titulo='Por defecto')
        self.assertEqual((aviso.color_principal, aviso.color_secundario, aviso.estilo_css), ('', '', ''))

    def test_sin_colores_propios_el_estilo_vuelve_a_borde(self):
        self.client.force_login(self.staff)
        self.client.post('/edit/avisos/', self.datos_aviso(titulo='Sin propios', estilo_color='solido'))
        self.assertEqual(self.Aviso.objects.get(titulo='Sin propios').estilo_color, 'borde')

    def test_texto_elige_el_mayor_contraste(self):
        verde = self.Aviso(color_principal='#05B287', estilo_color='solido')
        azul = self.Aviso(color_principal='#001959', estilo_color='solido')
        self.assertEqual((verde.color_texto, azul.color_texto), ('#000000', '#FFFFFF'))

    def test_fragmento_informa_la_version_y_la_pagina_la_declara(self):
        from django.conf import settings
        self.assertEqual(self.client.get('/vivo/inicio/')['X-Site-Version'], settings.SITE_VERSION)
        self.assertContains(self.client.get('/'), f'data-live-version="{settings.SITE_VERSION}"')
        self.assertContains(self.client.get('/horarios/'), f'data-live-version="{settings.SITE_VERSION}"')

    def test_colores_propios_se_guardan_desde_el_panel(self):
        self.client.force_login(self.staff)
        self.client.post('/edit/avisos/', self.datos_aviso(titulo='Mio', colores_propios='on', color_principal='#112233'))
        self.assertEqual(self.Aviso.objects.get(titulo='Mio').color_principal, '#112233')

    def test_color_invalido_no_se_guarda(self):
        self.client.force_login(self.staff)
        r = self.client.post('/edit/avisos/', self.datos_aviso(colores_propios='on', color_principal='red;x'))
        self.assertFalse(self.Aviso.objects.exists())
        self.assertContains(r, 'Revisa los campos marcados')

    def test_imagen_solo_https(self):
        self.client.force_login(self.staff)
        self.client.post('/edit/avisos/', self.datos_aviso(imagen_url='http://ejemplo.cl/a.jpg'))
        self.assertFalse(self.Aviso.objects.exists())
        self.client.post('/edit/avisos/', self.datos_aviso(imagen_url='javascript:alert(1)'))
        self.assertFalse(self.Aviso.objects.exists())
        self.client.post('/edit/avisos/', self.datos_aviso(imagen_url='https://ejemplo.cl/a.jpg', formato='cartel'))
        self.assertContains(self.client.get('/vivo/inicio/'), 'src="https://ejemplo.cl/a.jpg"')

    def test_cambiar_la_posicion_desde_el_panel_cambia_inicio(self):
        aviso = self.Aviso.objects.create(titulo='Se mueve')
        self.client.force_login(self.staff)
        antes = self.client.get('/vivo/inicio/')
        self.client.post(f'/edit/avisos/{aviso.pk}/', self.datos_aviso(titulo='Se mueve', posicion='boton'))
        self.assertNotEqual(antes['ETag'], self.client.get('/vivo/inicio/')['ETag'])

    def test_aviso_del_panel_aparece_en_inicio_y_respeta_fechas(self):
        self.crear(23, 0)
        self.client.force_login(self.staff)
        hoy = self.hora_local(2026, 10, 21, 10, 0)
        with mock.patch('django.utils.timezone.now', return_value=hoy):
            antes = self.client.get('/vivo/inicio/')
            self.assertNotContains(antes, 'class="notices"')
            self.client.post('/edit/avisos/', self.datos_aviso(
                tipo='suspension', titulo='Sin recorrido a Cerro', mensaje='Por nieve',
                desde='2026-10-21', hasta='2026-10-22',
            ))
            despues = self.client.get('/vivo/inicio/')
            self.client.post('/edit/avisos/', self.datos_aviso(tipo='oferta', titulo='Futuro', desde='2026-11-01'))
            futuro = self.client.get('/vivo/inicio/')
        self.assertNotEqual(antes['ETag'], despues['ETag'])
        self.assertContains(despues, 'Sin recorrido a Cerro')
        self.assertContains(despues, 'role="alert"')
        self.assertNotContains(futuro, 'Futuro')

    def test_aviso_con_fechas_invertidas_no_se_guarda(self):
        self.client.force_login(self.staff)
        r = self.client.post('/edit/avisos/', self.datos_aviso(desde='2026-10-22', hasta='2026-10-21'))
        self.assertContains(r, 'La fecha final no puede ser anterior')

    def test_eliminar_aviso_del_panel_invalida(self):
        aviso = self.Aviso.objects.create(titulo='Oferta de prueba', tipo='oferta')
        self.client.force_login(self.staff)
        self.assertContains(self.client.get('/vivo/inicio/'), 'Oferta de prueba')
        self.client.post('/edit/avisos/', {'accion': 'eliminar', 'aviso': aviso.pk})
        self.assertNotContains(self.client.get('/vivo/inicio/'), 'Oferta de prueba')

    def test_eliminar_feriado_del_panel_invalida(self):
        feriado = self.Feriado.objects.create(fecha='2026-10-21', nombre='Dia de prueba')
        self.client.force_login(self.staff)
        hoy = self.hora_local(2026, 10, 21, 10, 0)
        with mock.patch('django.utils.timezone.now', return_value=hoy):
            self.assertContains(self.client.get('/vivo/inicio/'), 'Hoy es feriado')
            self.client.post('/edit/feriados/', {'accion': 'eliminar', 'feriado': feriado.pk})
            self.assertContains(self.client.get('/vivo/inicio/'), 'Hoy es miércoles')

    def test_inicio_avanza_con_el_reloj_cuando_vence_el_cache(self):
        from django.core.cache import cache

        self.crear(8, 0)
        self.crear(9, 0)
        with mock.patch('django.utils.timezone.now', return_value=self.hora_local(2026, 10, 21, 7, 30)):
            self.assertContains(self.client.get('/vivo/inicio/'), '<time class="departure__time">08:00</time>')
        cache.clear()  # equivale a que pasen los 15 s del TTL
        with mock.patch('django.utils.timezone.now', return_value=self.hora_local(2026, 10, 21, 8, 30)):
            r = self.client.get('/vivo/inicio/')
        self.assertContains(r, '<time class="departure__time">09:00</time>')
        self.assertNotContains(r, '<time class="departure__time">08:00</time>')

    def test_cache_cambia_al_cambiar_el_minuto(self):
        self.crear(8, 0)
        self.crear(9, 0)
        with mock.patch('django.utils.timezone.now', return_value=self.hora_local(2026, 10, 21, 7, 59)):
            self.assertContains(self.client.get('/vivo/inicio/'), 'data-hora="08:00"')
        # Un minuto despues, sin vaciar la cache: la clave nueva fuerza el recalculo.
        with mock.patch('django.utils.timezone.now', return_value=self.hora_local(2026, 10, 21, 8, 1)):
            r = self.client.get('/vivo/inicio/')
        self.assertContains(r, 'data-hora="09:00"')
        self.assertNotContains(r, 'data-hora="08:00"')

    def test_invalidar_borra_minuto_actual_y_anterior(self):
        from django.core.cache import cache

        from . import vivo

        with mock.patch('django.utils.timezone.now', return_value=self.hora_local(2026, 10, 21, 8, 0)):
            vivo.fragmento('inicio')
        with mock.patch('django.utils.timezone.now', return_value=self.hora_local(2026, 10, 21, 8, 1)):
            vivo.invalidar()
            self.assertIsNone(cache.get('vivo:inicio:08:00'))

    def test_guardar_horarios_enlaza_al_sitio(self):
        self.client.force_login(self.staff)
        r = self.client.post('/edit/horarios/lv/', {f'horas_{self.ruta.pk}': '08:00'}, follow=True)
        self.assertContains(r, 'Horarios guardados.')
        self.assertContains(r, 'href="/"')
        self.assertContains(r, 'href="/horarios/"')

    def test_feriado_agregado_enlaza_al_sitio(self):
        self.client.force_login(self.staff)
        r = self.client.post('/edit/feriados/', {'fecha': '2026-12-25', 'nombre': 'Navidad'}, follow=True)
        self.assertContains(r, 'Feriado agregado.')
        self.assertContains(r, 'href="/horarios/"')
