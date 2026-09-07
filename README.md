# suray.cl — sitio informativo

Sitio informativo de Buses Suray (rutas, horarios, contacto), construido con
**Django + HTML5 + CSS puro** (sin frameworks JS pesados). Migrado 1:1 desde la app
Flutter original — ver `inventario_contenido.md` para el detalle de esa migración y
las decisiones tomadas.

No incluye el sistema POSBUS ni venta de tickets: es exclusivamente el sitio informativo
de la empresa.

## Stack

- Django 6.1 (Python 3.12)
- SQLite en desarrollo, MySQL/MariaDB en producción (vía `pymysql`)
- Whitenoise para servir estáticos
- HTML5 + CSS puro, sin build step de frontend (solo `html2canvas` por CDN para la
  descarga de horarios como imagen)

## Estructura

```
suray_web/          settings del proyecto
sitio/               app principal (modelos, vistas, templates, admin)
static/              CSS, imágenes, fuentes
preview/             mockups estáticos de Fase 1 (referencia histórica de diseño,
                     no se sirven en producción)
_legacy_reference/   clon de solo lectura del repo Flutter original (no se commitea)
assets_extraidos/    assets originales catalogados en la Fase 0
inventario_contenido.md   inventario de contenido y decisiones de la migración
DEPLOY.md            pasos de despliegue en cPanel
```

## Desarrollo local

```
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Admin: `http://127.0.0.1:8000/admin/`

## Cargar horarios reales desde un export de Firestore

```
python manage.py cargar_horarios ruta\al\export.json --reemplazar
```

Espera un JSON con la misma forma que el export original de Firestore (colecciones
`horarios` por región/tipo de día y `feriados` por año). Ver
`sitio/management/commands/cargar_horarios.py`.

## Despliegue

Ver `DEPLOY.md` para el proceso completo en cPanel (Passenger/WSGI, variables de
entorno, migración de base de datos en producción).
