# Despliegue en cPanel — suray.cl

Pasos manuales para desplegar `suray_web` en el hosting cPanel (tema Jupiter, Python App
vía Passenger/WSGI). No automatizables desde el código — se ejecutan directamente en el
panel o por SSH/Terminal de cPanel.

## 0. Subir el código con Git

El repo local ya existe (`git log` tiene el commit inicial). Como el DNS de `suray.cl`
aún no apunta a este hosting, cPanel debería ser accesible igual por su URL temporal
(algo como `https://<servidor>.tuhosting.cl:2083` o la que te haya dado el proveedor) —
usa esa para entrar mientras tanto.

1. **Generar y agregar una llave SSH** (si no tienes una ya asociada a la cuenta de cPanel):
   - cPanel → **SSH Access** → "Manage SSH Keys" → "Generate a New Key" (o importa una que
     ya tengas localmente). Autoriza la llave ("Manage Keys" → Authorize).
   - Si la generas ahí, descarga la privada o copia la pública a tu máquina local para
     poder hacer `git push` desde acá.
2. **Crear el repositorio en cPanel**: cPanel → **Git Version Control** → "Create":
   - Clone URL: déjalo vacío (repo nuevo, no clonado de otro lado).
   - Repository Path: la ruta donde luego vivirá la app, ej. `/home/<usuario>/suray_web`.
   - Repository Name: `suray_web`.
3. cPanel te muestra una **Clone URL** tipo `ssh://<usuario>@<servidor>:<puerto>/home/<usuario>/suray_web.git`.
   Agrégala como remoto local y sube el código:
   ```
   git remote add cpanel ssh://<usuario>@<servidor>:<puerto>/home/<usuario>/suray_web.git
   git push cpanel master
   ```
4. En cPanel → Git Version Control → tu repo → **"Manage"** → pestaña **"Pull or Deploy"**
   → "Update from Remote" (si hiciste el push) o simplemente ya queda desplegado el working
   copy en la Repository Path, según la versión de cPanel.

Si tu plan de hosting no incluye SSH Access ni Git Version Control (algunos planes
compartidos básicos no lo traen), usa en su lugar **File Manager**: comprime el proyecto
local en un `.zip` (excluyendo `venv/`, `_legacy_reference/`, `db.sqlite3`, `staticfiles/`
— ya están en `.gitignore`, así que `git archive` es la forma más limpia de generarlo:
`git archive -o suray_web.zip HEAD`), súbelo por File Manager a la ruta de la app, y
descomprímelo ahí. Pierdes el `git pull` para actualizaciones futuras, pero funciona igual.

## 1. Crear la app Python en cPanel

1. cPanel → **Setup Python App** → Create Application.
2. Python version: 3.12 (la más cercana disponible a la usada en desarrollo).
3. Application root: la misma Repository Path del paso 0 (ej. `suray_web`).
4. Application URL: `suray.cl` (dominio raíz). El dominio debe existir en la cuenta de
   cPanel (como principal, addon o parked) aunque el DNS público todavía no apunte acá —
   mientras tanto, prueba con la URL temporal que cPanel asigna a la app, o agrega una
   entrada en el archivo `hosts` de tu máquina apuntando `suray.cl` a la IP del servidor
   solo para probar antes de cambiar el DNS real.
5. Application startup file: `passenger_wsgi.py` (ya está en la raíz del proyecto).
6. Application Entry point: `application` (la variable que exporta `passenger_wsgi.py`).

## 2. Variables de entorno de la app Python

En la misma pantalla de "Setup Python App", sección **Environment variables**, agregar:

| Variable | Valor |
|---|---|
| `SECRET_KEY` | una clave larga y aleatoria nueva (**no** la de desarrollo) |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `suray.cl,www.suray.cl` |
| `SITE_URL` | `https://suray.cl` (opcional: es el valor por defecto; en test, `https://test.suray.cl`). Define el canonical, Open Graph y sitemap; cualquier otro dominio se sirve con `noindex` |
| `DB_ENGINE` | `mysql` |
| `DB_NAME` | `suraycl1_suray_web_server` |
| `DB_USER` | `suraycl1_suray_w` |
| `DB_PASSWORD` | la contraseña real de esa base de datos (gestionada solo aquí) |
| `DB_HOST` | `localhost` |
| `DB_PORT` | `3306` |

Nunca escribir estos valores en el código ni subirlos al repositorio.

`BROWSER_RELOAD` (recarga automática del navegador en desarrollo) **no se define en el servidor**: así `django_browser_reload` no se carga aunque `DEBUG` estuviera activo.

## 3. Instalar dependencias

Desde la Terminal de cPanel (o SSH), activando el virtualenv que cPanel genera para la app:

```
source /home/<usuario_cpanel>/virtualenv/<ruta_app>/3.12/bin/activate
cd ~/<ruta_app>
pip install -r requirements.txt
```

(El comando exacto de activación lo muestra la propia pantalla de "Setup Python App").

## 4. Migrar la base de datos

Con el virtualenv activado y las variables de entorno cargadas:

```
python manage.py migrate
```

Esto crea las tablas en `suraycl1_suray_web_server`. Ejecutar **una sola vez**
(las siguientes veces solo se corre `migrate` si hay migraciones nuevas).

## 5. Cargar contenido real

Opción A — vía el comando ya usado en desarrollo (si tienes un export de Firestore actualizado):

```
python manage.py cargar_horarios /ruta/al/export.json --reemplazar
```

Opción B — cargar/editar manualmente desde `https://suray.cl/admin/` una vez creado el
superusuario (paso 7).

## 6. Archivos estáticos

```
python manage.py collectstatic --noinput
```

Whitenoise sirve los estáticos directamente desde la app (no requiere configuración
adicional de Apache).

## 7. Crear superusuario de producción

```
python manage.py createsuperuser
```

Usar un usuario/clave reales, distintos de las credenciales de desarrollo local
(el superusuario `admin` creado localmente es solo para el entorno de desarrollo
y no debe reutilizarse en producción).

## 8. Verificación post-deploy

- Revisar `https://suray.cl` en escritorio y móvil.
- Confirmar que `python manage.py check --deploy` no marca errores (correr desde la
  Terminal de cPanel con las variables de entorno de producción cargadas).
- Confirmar en phpMyAdmin que las tablas de `sitio` se crearon y que el uso de disco
  sigue dentro del límite del plan (10 GB).
- Configurar backup periódico (JetBackup 5) para la base de datos y el código.

## 9. Apuntar el DNS real de suray.cl

Una vez que todo lo anterior está probado (vía URL temporal o el `hosts` local):

1. En el proveedor donde está registrado el dominio `suray.cl`, cambia los registros
   (A/AAAA o los NS, según cómo esté delegado hoy) para que apunten a este hosting cPanel
   en vez de a Firebase Hosting.
2. Espera la propagación (puede tardar desde minutos hasta ~24-48h).
3. Una vez propagado, activa el certificado SSL en cPanel (AutoSSL suele encargarse solo
   si el dominio ya resuelve hacia el servidor) y confirma que `SECURE_SSL_REDIRECT` no
   esté forzado en `False` en las variables de entorno.
4. Revierte cualquier entrada de prueba que hayas dejado en el `hosts` local.

## Notas

- `DEBUG=False` activa automáticamente `SECURE_SSL_REDIRECT`, cookies seguras y HSTS
  (ver `suray_web/settings.py`). Si el certificado SSL de `suray.cl` aún no está activo
  al desplegar, poner temporalmente `SECURE_SSL_REDIRECT=False` en las variables de
  entorno hasta que lo esté, o los usuarios verán errores de redirección.
- El proyecto asume que Apache/Passenger reenvía el header `X-Forwarded-Proto` — si cPanel
  no lo hace por defecto, revisar `SECURE_PROXY_SSL_HEADER` en `settings.py`.

## 10. Despliegue automático por webhook (test.suray.cl)

Cada push a `main` dispara el despliegue al instante: GitHub llama a
`https://test.suray.cl/deploy/webhook/`, la app valida la firma y lanza
`auto_deploy_test.py`, que sincroniza los archivos, ejecuta `pip install` (solo si cambió
`requirements.txt`), `collectstatic` y `migrate`, y recién entonces reinicia la app.

> **Importante:** `deploy/` está en `SKIP_ENTRIES`, así que el script **no se sincroniza solo**.
> La copia que corre en el servidor vive en `/home/suraycl1/deploy_scripts/auto_deploy_test.py`
> y hay que subirla a mano cada vez que cambie `deploy/auto_deploy_test.py` en el repo.

### 10.1 Generar el secreto

En tu máquina:

```
python -c "import secrets; print(secrets.token_hex(32))"
```

En cPanel → **Setup Python App** → Environment variables, agrega `WEBHOOK_SECRET` con ese
valor y reinicia la app. Mientras `WEBHOOK_SECRET` esté vacío, el endpoint responde 404.

### 10.2 Subir el script nuevo

Con File Manager de cPanel, sube `deploy/auto_deploy_test.py` a
`/home/suraycl1/deploy_scripts/auto_deploy_test.py` (reemplazando el anterior).

### 10.3 Configurar el webhook en GitHub

Repositorio → **Settings → Webhooks → Add webhook**:

- **Payload URL:** `https://test.suray.cl/deploy/webhook/` (con `https`; GitHub no sigue redirecciones).
- **Content type:** `application/json`.
- **Secret:** el mismo valor de `WEBHOOK_SECRET`.
- **Events:** "Just the push event".
- **SSL verification:** activada. **Active:** marcado.

Al guardar, GitHub envía un evento `ping`; debe aparecer con ✔ (HTTP 200) en *Recent Deliveries*.

### 10.4 Cron de respaldo y reintento

El despliegue desde el cron **no tiene las variables de entorno de cPanel**. Crea
`/home/suraycl1/deploy_scripts/deploy.env` con líneas `KEY=VALUE` (las mismas de la
sección 2: `DEBUG=False`, `ALLOWED_HOSTS`, `SECRET_KEY`, `DB_ENGINE=mysql`, `DB_NAME`,
`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`). Restringe su acceso (permisos `600`), ya
que contiene credenciales. Si el script detecta que la configuración efectiva usa SQLite,
**omite `migrate`** y deja una advertencia en el log.

En cPanel → **Cron Jobs**:

1. Cambia el cron existente de `*/15 * * * *` a cada hora (`0 * * * *`), como respaldo:
   ```
   /home/suraycl1/virtualenv/public_html/test.suray.cl/3.12/bin/python /home/suraycl1/deploy_scripts/auto_deploy_test.py
   ```
2. Opcional, cada minuto (`* * * * *`): reintenta solo si existe `deploy.flag`. El marcador
   lo crea la app si no pudo lanzar el script, o el propio script si llegó un push mientras
   había un despliegue en curso:
   ```
   [ -f /home/suraycl1/deploy_scripts/deploy.flag ] && /home/suraycl1/virtualenv/public_html/test.suray.cl/3.12/bin/python /home/suraycl1/deploy_scripts/auto_deploy_test.py
   ```

### 10.5 Revisar que funcione

- **Log del despliegue:** `/home/suraycl1/deploy_scripts/test_deploy.log` (pasos ejecutados,
  salida de `collectstatic`/`migrate` y errores).
- **Salida del lanzamiento desde la app:** `/home/suraycl1/deploy_scripts/webhook_launch.log`.
- **Entregas en GitHub:** Settings → Webhooks → tu webhook → **Recent Deliveries** (código
  de respuesta y reenvío con *Redeliver*). 202 = recibido; 403 = firma inválida
  (secreto distinto); 404 = `WEBHOOK_SECRET` no definido en la app.
- Si `collectstatic` o `migrate` fallan, la app **no se reinicia** y no se guarda el SHA:
  el siguiente intento (otro push, el cron o el marcador) lo reintenta.

> Con `DEBUG=False` los estáticos solo se sirven tras `collectstatic` (Whitenoise con
> manifiesto); si falta, las páginas dan error 500. El script ya lo ejecuta en cada despliegue.


## 11. Producción (suray.cl) con la rama `produccion`

Flujo: `main` → test.suray.cl (automático); cuando test está bien, se promueve a
`produccion` → suray.cl (automático).

```
git switch produccion
git merge --ff-only main
git push
git switch main
```

El mismo código y el mismo script sirven para los dos sitios; lo que cambia es la
configuración por variables de entorno. Sin definirlas, todo se comporta como test.

| Variable | test.suray.cl | suray.cl |
|---|---|---|
| `DEPLOY_NAME` | *(vacía, o `test`)* | `produccion` |
| `DEPLOY_BRANCH` | *(vacía, o `main`)* | `produccion` |
| `DEPLOY_TARGET` | *(vacía)* | `/home/suraycl1/suray_prod` |
| `WEBHOOK_SECRET` | el de test | uno **distinto**, propio de producción |

`suray.cl` es el dominio principal de la cuenta y su raíz (`public_html/`) no se puede
cambiar; dentro de ella viven las carpetas de los subdominios (`test.suray.cl/`,
`mantenimiento/`…). Por eso el código de producción va **fuera** de `public_html`
(`/home/suraycl1/suray_prod`, Application root de la Python App con URL `suray.cl`): cPanel
solo escribe ahí el bloque de Passenger del `.htaccess` de `public_html/`.

Defínelas en cPanel → Setup Python App → Environment variables **de la app de suray.cl**
(no en un `.env`: el script lo lanza el webhook y solo hereda las variables de la app),
junto con las de la sección 2 (`DEBUG=False`, `ALLOWED_HOSTS=suray.cl,www.suray.cl`,
`SECRET_KEY` nuevo y `DB_*` de producción). **No compartas la base de datos con test.**
`DB_PASSWORD` es la contraseña del **usuario de MySQL** (cPanel → MySQL Databases), no la de
cPanel ni la de FTP.

En el dominio principal, `SECURE_HSTS_INCLUDE_SUBDOMAINS=False` y un
`SECURE_HSTS_SECONDS` bajo al principio (p. ej. `3600`): con el valor por defecto (un año con
subdominios) el navegador forzaría HTTPS en test y en el resto de subdominios.

### 11.1 Archivos que usa cada sitio (carpeta `/home/suraycl1/deploy_scripts/`)

| | test | produccion |
|---|---|---|
| Script | `auto_deploy_test.py` | el mismo archivo |
| Log | `test_deploy.log` | `produccion_deploy.log` |
| Estado | `test_deploy_state.json` | `produccion_deploy_state.json` |
| Bloqueo / marcador | `deploy.lock` / `deploy.flag` | `produccion_deploy.lock` / `produccion_deploy.flag` |
| Variables del cron | `deploy.env` | `produccion_deploy.env` |
| Log del webhook | `webhook_launch.log` | `produccion_webhook_launch.log` |

`produccion_deploy.env` lleva las mismas líneas `KEY=VALUE` que `deploy.env` pero con los
valores de producción (sección 10.4), con permisos `600`.

### 11.2 Cron de producción

El cron no tiene las variables de la app, así que se pasan delante del comando:

```
DEPLOY_NAME=produccion DEPLOY_BRANCH=produccion DEPLOY_TARGET=/home/suraycl1/suray_prod /home/suraycl1/virtualenv/suray_prod/3.13/bin/python /home/suraycl1/deploy_scripts/auto_deploy_test.py >> /home/suraycl1/deploy_scripts/produccion_cron_stdout.log 2>&1
```

El Python es el del virtualenv que genera cPanel para la app (la versión, `3.13` aquí,
depende de la que elijas en Setup Python App). Cada hora como respaldo; y, opcional, cada
minuto solo si existe el marcador `produccion_deploy.flag` (misma forma que en la sección
10.4).

### 11.3 Webhook en GitHub

Settings → Webhooks → Add webhook: `https://suray.cl/deploy/webhook/`, `application/json`,
el secreto de producción y solo el evento push. Cada app solo despliega su rama: un push a
`main` responde 202 sin hacer nada en suray.cl, y uno a `produccion` hace lo mismo en test.

### 11.4 Primer despliegue (hosting sin SSH ni Terminal)

Con solo File Manager, FTP y Cron Jobs, el propio script hace el primer despliegue:

1. cPanel → MySQL Databases: crea una base y un usuario **solo para producción**.
2. Sube a mano el script actualizado a `deploy_scripts/` (recuerda que `deploy/` no se
   sincroniza solo) **antes** del primer despliegue automático; guarda copia del anterior.
3. Setup Python App: root `suray_prod`, URL `suray.cl`, `passenger_wsgi.py`, `application`,
   con las variables de la sección 11 (los valores secretos, pegados desde el portapapeles).
4. Crea `deploy_scripts/produccion_deploy.env` (permisos `600`) con `SECRET_KEY`, `DEBUG=False`,
   `ALLOWED_HOSTS`, `DB_*` y las de HSTS. **Debe llevar `DEBUG=False` y `DB_*`:** si el motor
   efectivo no es MySQL, el script omite `migrate` y lo deja en el log.
5. Cron de una sola vez (cada minuto) con el comando de 11.2; revisa
   `produccion_deploy.log` hasta ver «Despliegue completo» y **borra ese cron**.
6. Superusuario: cron de una sola vez con `DJANGO_SUPERUSER_USERNAME/EMAIL/PASSWORD` y
   `manage.py createsuperuser --noinput` tras cargar `produccion_deploy.env` (importando
   `load_env_file` de `auto_deploy_test`). La clave solo vive en ese cron: bórralo al terminar.
7. Cambio de sitio: mientras haya un `index.html` (u otros archivos) en la raíz de
   `public_html/`, Apache los sirve antes que Django. Mueve (no borres) esos archivos a un
   respaldo fuera de `public_html` y deja `.htaccess`, `.well-known/`, `cgi-bin/` y las
   carpetas de los subdominios. Para revertir, devuelve los archivos.
8. Webhook en GitHub (11.3), cron de respaldo cada hora (11.2) y protege la rama
   `produccion` (Settings → Branches): sin push directo ni force-push.

### 11.5 Cosas que conviene saber

- **Herencia del `.htaccess`:** el `.htaccess` de `public_html/` aplica también a las
  subcarpetas, así que las variables de la app de producción llegan a la app de test si esta
  no las redefine. La app de test debe definir `DEPLOY_NAME=test`, `DEPLOY_BRANCH=main` y
  `DEPLOY_TARGET=/home/suraycl1/public_html/test.suray.cl`; si no, su webhook ignoraría los
  push a `main`.
- **Static con manifiesto:** `CompressedManifestStaticFilesStorage` exige que todo archivo
  referenciado por un `.js`/`.css` exista (p. ej. un `sourceMappingURL` sin su `.map` hace
  fallar `collectstatic`, y con él todo el despliegue). Al vendorizar librerías, quita la
  referencia o incluye el `.map`.
- **Contraseñas:** cambiar la contraseña de un usuario de MySQL rompe cualquier app que la
  tenga en sus variables (y el `deploy.env` del cron). Actualízala en ambos sitios.
