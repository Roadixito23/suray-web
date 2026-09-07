# Despliegue en cPanel — suray.cl

Pasos manuales para desplegar `suray_web` en el hosting cPanel (tema Jupiter, Python App
vía Passenger/WSGI). No automatizables desde el código — se ejecutan directamente en el
panel o por SSH/Terminal de cPanel.

## 1. Crear la app Python en cPanel

1. cPanel → **Setup Python App** → Create Application.
2. Python version: 3.12 (la más cercana disponible a la usada en desarrollo).
3. Application root: el directorio donde subiste este proyecto (ej. `suray_web`).
4. Application URL: `suray.cl` (dominio raíz).
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

## Notas

- `DEBUG=False` activa automáticamente `SECURE_SSL_REDIRECT`, cookies seguras y HSTS
  (ver `suray_web/settings.py`). Si el certificado SSL de `suray.cl` aún no está activo
  al desplegar, poner temporalmente `SECURE_SSL_REDIRECT=False` en las variables de
  entorno hasta que lo esté, o los usuarios verán errores de redirección.
- El proyecto asume que Apache/Passenger reenvía el header `X-Forwarded-Proto` — si cPanel
  no lo hace por defecto, revisar `SECURE_PROXY_SSL_HEADER` en `settings.py`.
