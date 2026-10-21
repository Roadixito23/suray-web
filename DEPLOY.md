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
