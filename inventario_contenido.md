# Inventario de Contenido — suray.cl (Fase 0)

Extraído por lectura directa del código fuente en `_legacy_reference/` (clon de
`https://github.com/Roadixito23/suray`, commit `16663e6`). Todo el texto citado es
copy exacto encontrado en el código Dart, no parafraseado. Las secciones marcadas
**"pendiente de confirmar"** requieren una decisión del usuario antes de avanzar a Fase 1.

---

## 1. Páginas / secciones a recrear

La app Flutter actual tiene **5 pantallas**, todas navegadas mediante `Navigator.push`
(no hay rutas URL reales — es una SPA de un solo `MaterialApp`):

| # | Pantalla (archivo) | Ruta propuesta Django | Descripción |
|---|---|---|---|
| 1 | `splash.dart` | *(no aplica — sin equivalente estático)* | Splash de ~1s, solo logo, sin copy. Registra una visita en Firestore. |
| 2 | `home.dart` | `/` (inicio) | Carrusel de fondo, próximas salidas, botón a horarios, footer con redes |
| 3 | `schedules_page.dart` | `/horarios/` | Horarios Lunes-Viernes / Sábado / Domingo-Feriado, por ciudad |
| 4 | `contact_page.dart` | `/contacto/` | Ubicaciones, teléfonos, horarios de oficina, contacto de servicios especiales |
| 5 | `paraderos_page.dart` | `/ruta/` | Mapa interactivo (Google Maps) con los 2 terminales y geolocalización |

**Hallazgo importante — pendiente de confirmar con el usuario:** el plan de migración
(Fase 3) propone modelos `Ruta`, `Horario`, `Tarifa` y `Noticia`. En el código actual
**no existe ninguna página de tarifas/precios ni de noticias**. No hay evidencia de que
esas secciones existan hoy en el sitio. Antes de crear esos modelos en Fase 3 hay que
confirmar si son:
- (a) contenido nuevo que el usuario quiere agregar en la migración, o
- (b) un error/generalización del plan que debe ajustarse al contenido real (solo
  horarios, sin tarifas ni noticias).

Tampoco existe una sección "Quiénes somos" ni una página de términos/legal.

---

## 2. Copy exacto por sección

### 2.1 Splash (`splash.dart`)
Sin texto visible. Solo `assets/logocircle.png` sobre gradiente
(`primaryNavy → lightNavy → primaryOrange`). Dura 1 segundo y navega a Home. También
incrementa un contador de visitas en Firestore (`estadisticas/visitas`) deduplicado por
`localStorage` (24h) — **funcionalidad dinámica, no aplica a un sitio estático sin backend
propio; pendiente de confirmar si se quiere replicar como analítica simple en Django**.

### 2.2 Inicio (`home.dart`)
- Botones de header: **"Ubícanos"** (ícono `location_on`) → Contacto; **"Ruta"** (ícono
  `map`) → Paraderos.
- Botón principal (pill negra con borde naranja): **"TODOS LOS HORARIOS"** → Horarios.
- Tarjeta de estado del día:
  - Normal: `"Hoy es {DíaSemana} {día} de {MES_ABREV}"` (ej. "Hoy es Lunes 6 de SEP")
  - Feriado: `"Hoy es Feriado: {nombreFeriado}"`
  - Encabezado de subsección: **"Próximas Salidas:"**
  - Columnas: **"Desde Aysén"** / **"Desde Coyhaique"**
  - Estados posibles de salida (generados dinámicamente, no hardcodeados):
    `"Hoy a las {hora} a.m./hrs."`, `"Mañana a las {hora}..."`, `"Sin salidas próximas"`,
    `"Sin recorrido"` (día sin servicio)
  - Etiquetas de chip: **"HOY"** / **"MAÑANA"**
- Footer:
  - Redes: **"@buses.suray.cargo"** (Instagram) y **"buses.suray.cargo"** (Facebook)
  - Copyright: **"Copyright © 2026 - MMKT GRUPO SURAY - CMO dante@suray.cl"**
    *(el año se ve hardcodeado a 2026 en el código, no es dinámico — copiar literal)*

**Nota — contenido dinámico vía Firestore, no copy estático:** los horarios reales
(`horarios/{region}/{coleccion}`) y feriados (`feriados/{año}`) viven en Firestore, no en
el código. **No se pudo extraer el contenido real de horarios/feriados desde el repo**
— eso vive en la base de datos Firebase de producción, no en el código fuente. **Pendiente
de confirmar con el usuario**: se necesita acceso a esos datos (export de Firestore, o
que el usuario los liste manualmente) para poblar los modelos `Ruta`/`Horario` de Fase 3
con datos reales, no de prueba.

También hay un **widget de clima en tiempo real** (OpenWeatherMap, coordenadas de
Coyhaique y Puerto Aysén) mostrado junto a cada salida — **funcionalidad no contemplada
en el plan de migración actual; pendiente de confirmar si se replica** (requeriría una
API key de OpenWeatherMap y JS en el sitio estático, o se omite).

### 2.3 Horarios (`schedules_page.dart`)
- Título AppBar: **"Horarios"**
- Tres secciones (tarjetas), con ícono y color propio:
  1. **"Lunes a Viernes"** (verde menta)
  2. **"Sábados"** (naranja dorado, ícono mixto trabajo/fin de semana)
  3. **"Domingo o Feriado"** (rojo coral)
- Subtítulo de cada tarjeta: **"Salidas desde:"**
- Columnas por tarjeta: **"Puerto Aysén"** / **"Coyhaique"**
- Badge cuando aplica horario especial de feriado: **"HORARIO ESPECIAL"**
- Estados vacíos: **"Sin horarios"**, **"Sin servicio\npor feriado"**, **"Error al cargar"**
- Función de descarga de horarios como imagen PNG (`schedule_image_generator.dart`,
  duplica el mismo copy) — nombre de archivo `horarios_suray_{fecha}_{hora}.png`.
  **Pendiente de confirmar** si esta función (exportar horarios como imagen) se replica
  en el sitio Django o se omite (no es contenido, es una utilidad de UI).
- Los horarios (`times`) en sí son datos de Firestore, mismo caso que 2.2.

### 2.4 Contacto (`contact_page.dart`)
- Título de header: **"Ponte en Contacto"**
- Subtítulo: **"Para consultar por horarios, información sobre encomiendas o servicios
  especiales, puedes usar los siguientes canales de comunicación:"**

**Puerto Aysén** (color `primaryNavy`):
| Tipo | Dirección | Teléfono | Mapa |
|---|---|---|---|
| Oficina de venta de pasajes | Eusebio Ibar 630 | 672 336222 | maps.app.goo.gl/1nv7mAcGRpFVPMacA |
| Oficina de correspondencia | Eusebio Ibar 630 (interior) | 672 336231 | maps.app.goo.gl/1nv7mAcGRpFVPMacA |

Horario oficina de pasajes Pto. Aysén: Lun-Vie 06:30–19:00 · Sáb 08:00–19:00 ·
Dom 08:00–13:30 / 16:30–18:00
Horario oficina de correspondencia (ambas ciudades): Lun-Vie 09:00–13:30 / 15:18–19:00 ·
Sáb 10:00–13:00 · Dom Cerrado

**Coyhaique** (color `accentBlue`):
| Tipo | Dirección | Teléfono | Mapa |
|---|---|---|---|
| Oficina de venta de pasajes | Av. Norte Sur/Las Violetas, Terminal de Coyhaique, Of. N°2 | 672 212639 | maps.app.goo.gl/9AJMknQmkmf3tHSo8 |
| Oficina de correspondencia | Arturo Prat 265 (interior) | 672 234085 | maps.app.goo.gl/pMdzjb5y1Mg1iNQd9 |

Horario oficina de pasajes Coyhaique: Lun-Vie 06:30–19:00 · Sáb 08:00–19:00 ·
Dom 10:00–15:30 / 18:00–19:30

- Tabs por ciudad: **"Ubícanos"** / **"Horarios"**
- Sub-encabezados de horario: **"Oficina de Pasajes"** / **"Oficina de Correspondencia"**,
  columnas de tabla **"Día"** / **"Horario"**
- Tarjeta "Servicios Especiales": título **"Servicios Especiales"**, correo de contacto
  **"suray.ltda@gmail.com"** (`mailto:` con asunto `"Consulta desde suray.cl"`)

### 2.5 Ruta / Paraderos (`paraderos_page.dart`)
- Título flotante sobre el mapa: **"Ruta Buses Suray"**
- Botones rápidos: **"AYS"** (naranja) / **"COY"** (azul), botón de dirección (alterna
  ícono de flecha), botón de ubicación del usuario (GPS), controles de zoom, brújula.
- Coordenadas de los 2 terminales (marcadores en el mapa):
  - Puerto Aysén: `-45.40111614852224, -72.68738064167634`
  - Coyhaique: `-45.582039, -72.078136`
  - Centro inicial del mapa: `-45.4915, -72.3827`, zoom 9.5
  - Límites del mapa: lat `-45.82` a `-45.19`, lng `-73.0` a `-71.8`
- Tarjeta info terminal al tocar un marcador: título **"Terminal"**, subtítulo
  **"Aysén Suray"** / **"Coyhaique Suray"**
- Mensajes de estado de geolocalización: "GPS desactivado", "Permiso denegado",
  "Permiso bloqueado", "Ubicación encontrada", "Fuera del área", "Tu ubicación está
  fuera de la zona Puerto Aysén - Coyhaique", "Error al obtener ubicación"

**Pendiente de confirmar:** esta pantalla usa Google Maps interactivo (`google_maps_flutter`
+ Google Maps JavaScript API, con API key visible en `web/index.html`:
`AIzaSyCSNlH9e84Orco1EAXnB-Iq9TYLBCLynFo`). Replicarlo 1:1 en Django/HTML requiere
incrustar el mismo JS de Google Maps (o un embed estático) — el plan permite HTMX/Alpine
vía CDN pero no menciona Google Maps explícitamente. Confirmar si se usa Google Maps JS
API directamente, un iframe de Google Maps Embed, o un mapa estático más simple. También
confirmar si la key expuesta debe rotarse/restringirse por dominio antes de reutilizarla.

### 2.6 SEO / metadatos (`web/index.html`)
Útiles para replicar en `base.html` de Django:
- `<title>`: **"Buses Suray | Suray Cargo"**
- Meta description / og:description / twitter:description (idéntico en los 3):
  **"Transporte rural de pasajeros con servicio de correspondencia entre Puerto Aysén y
  Coyhaique. Información de horarios, teléfonos, direcciones, paraderos en ruta 240 y
  servicios especiales."**
- Meta keywords: "Suray, Buses Aysén, Coyhaique, Cargo, Encomiendas, Pasajes, Transporte
  Patagonia, Horarios Buses, Ruta 240, Puerto Aysén, Transporte Rural, Buses Región de
  Aysén"
- Schema.org `TravelAgency`: área servida "Aysén del General Carlos Ibáñez del Campo",
  dirección `Puerto Aysén, Aysén, CL`
- `theme-color`: `#0175c2` (nota: no coincide con la paleta real de la app — es el azul
  por defecto de Flutter, probablemente sin actualizar; usar la paleta real de `main.dart`
  en su lugar, no este valor)

---

## 3. Assets

Copiados a `assets_extraidos/` (organizados por tipo). Todos existen en
`_legacy_reference/assets/` y están declarados en `pubspec.yaml`.

| Archivo original | Nuevo nombre propuesto | Uso confirmado en código |
|---|---|---|
| `assets/logo.png` | `logos/logo.png` | Logo horizontal — header de Inicio y pie de horarios |
| `assets/logocircle.png` | `logos/logo_circular.png` | Logo circular — pantalla Splash |
| `assets/insta_icon.png` | `iconos/icono_instagram.png` | Botón Instagram en footer de Inicio |
| `assets/icons/bus_reloj.png` | `iconos/icono_bus_reloj.png` | Ícono botón "TODOS LOS HORARIOS" |
| `assets/icons/calendario_reloj.png` | `iconos/icono_calendario_reloj.png` | Ícono tarjeta "Hoy es..." |
| `assets/home_panels/puente_aysen.png` | `fotos/panel_puente_aysen.png` | Carrusel de fondo, Inicio (imagen 1) |
| `assets/home_panels/tunel.png` | `fotos/panel_tunel.png` | Carrusel de fondo, Inicio (imagen 2) |
| `assets/home_panels/aysen.png` | `fotos/panel_aysen.png` | Fondo tarjeta Puerto Aysén, Contacto |
| `assets/home_panels/coyhaique.jpg` | `fotos/panel_coyhaique.jpg` | Fondo tarjeta Coyhaique, Contacto |
| `assets/home_panels/buses.png` | `fotos/panel_buses.png` | Textura de fondo repetida en tarjetas de Contacto |
| `assets/fonts/Hemiheads.otf` | `fuentes/Hemiheads.otf` | Fuente de títulos/headlines |

**Assets declarados en `pubspec.yaml` pero SIN uso detectado en el código actual:**
`assets/home_panels/terminal_coy.png`, `assets/bg/background_route.png`,
`assets/ruta_240.png` — **descartados por decisión del usuario (checkpoint 1)**, ya
eliminados de `assets_extraidos/`.

**Otros assets referenciados que NO están en el repo** (se generan/cargan externamente,
no requieren migración de archivo): ícono Material `Icons.facebook` (fuente de íconos
Flutter, se reemplaza por un ícono SVG/webfont equivalente en HTML).

---

## 4. Paleta de colores extraída (de `main.dart`, clase `MyApp`)

```css
:root {
  /* Paleta principal */
  --color-primary-navy: #001959;
  --color-primary-orange: #F47200;
  --color-light-navy: #1E3A8A;
  --color-deep-orange: #E65100;
  --color-soft-orange: #FFA726;
  --color-accent-blue: #3B82F6;
  --color-bg-light: #F8FAFC;
  --color-surface-white: #FFFFFF;
  --color-text-dark: #1E293B;
  --color-text-light: #64748B;
  --color-border: #E2E8F0;
  --color-success: #10B981;
  --color-warning: #F59E0B;
  --color-error: #EF4444;

  /* Colores por tipo de día (sección Horarios) */
  --color-weekday-mint: #06D6A0;
  --color-weekday-mint-dark: #05B287;
  --color-saturday-orange: #FFB703;
  --color-saturday-orange-dark: #FB8500;
  --color-sunday-red: #EF476F;
  --color-sunday-red-dark: #D62246;
}
```

Colores adicionales encontrados sueltos en pantallas específicas (no centralizados en
el tema, pero usados de forma consistente):
- `#D4CFC4` — fondo del footer de Inicio (beige)
- `#1877F2` — azul de Facebook (ícono footer)
- `#0A1628` / `#112240` / `#1A3050` — fondos de modo oscuro (Horarios y Contacto)
- `#1E88E5` (azul "HOY") / `#AB47BC` (lila "MAÑANA") / `#6A1B9A` (morado, chip "Mañana")
  — usados en los chips de próxima salida

**Nota:** la app tiene modo oscuro (`darkModeNotifier`, activado por defecto en web) que
afecta Horarios y Contacto. El plan actual no menciona modo oscuro — **pendiente de
confirmar** si el sitio Django debe soportarlo o solo replicar el modo claro.

---

## 5. Tipografía

- **Hemiheads** — fuente personalizada (`assets/fonts/Hemiheads.otf`, formato OTF), usada
  en títulos/headlines (`headlineLarge/Medium/Small`, `titleLarge`, y títulos puntuales
  como "Ponte en Contacto", nombres de ciudad, "Próximas Salidas:", "Ruta Buses Suray").
  Se debe servir como `@font-face` local en `static/fonts/`, no es de Google Fonts.
- **Montserrat** — declarada como `fontFamily: 'Montserrat'` en el tema general (texto de
  botones) pero **no está bundleada en `pubspec.yaml`** (no hay sección de fuentes para
  Montserrat) **ni hay dependencia `google_fonts` ni un `<link>` a Google Fonts en
  `web/index.html`**. Esto significa que en la práctica el navegador probablemente cae al
  font-family por defecto (system-ui) en vez de mostrar Montserrat real.
  **Pendiente de confirmar con el usuario:** ¿se quiere importar Montserrat de verdad
  (vía Google Fonts) en el sitio nuevo, o replicar el comportamiento actual (fuente de
  sistema por defecto)?

---

## 6. Componentes de navegación

- **No hay menú/nav bar tradicional.** La navegación es por botones contextuales:
  - Inicio → Contacto (botón "Ubícanos"), Inicio → Ruta (botón "Ruta"), Inicio → Horarios
    (botón pill "TODOS LOS HORARIOS")
  - Contacto, Horarios y Ruta tienen un botón "atrás" (`arrow_back_ios_new`) en vez de
    integrarse en un layout con nav persistente.
- **Footer** solo existe en Inicio: redes sociales (Instagram, Facebook) + copyright.
  Contacto/Horarios/Ruta no tienen footer propio.
- Toggle de modo oscuro presente en Horarios y Contacto (ícono sol/luna), ausente en
  Inicio y Ruta.

Esto es una diferencia estructural importante frente a un sitio web convencional: no hay
un `base.html` con header/nav/footer consistente en todas las páginas del original — cada
pantalla es casi una app independiente. **Pendiente de confirmar con el usuario:** ¿el
sitio Django debe imponer un layout consistente (nav + footer en todas las páginas, más
"web-like") o replicar fielmente la navegación por botones contextuales sin nav bar fija?

---

## 7. Referencias de build antiguo

- `public/index.html`: es la página placeholder por defecto de **Firebase Hosting**
  ("Welcome / Firebase Hosting Setup Complete"), sin relación con el contenido real del
  sitio. No sirve como referencia visual.
- `suray_web.tar.gz` (35.8 MB): build compilado de Flutter Web con renderer **CanvasKit**
  (`build/web/canvaskit/*.wasm`, `main.dart.js`). No contiene HTML/CSS semántico — es una
  app que dibuja todo en un `<canvas>` vía WebAssembly, por lo que **no sirve como
  referencia de maquetación HTML**, solo se podría ejecutar en un navegador para ver
  capturas visuales si se desea comparar el resultado final (Fase 4, checkpoint de
  fidelidad visual). No se extrajo su contenido más allá de listar el índice del tar,
  ya que no aporta nada adicional al inventario de copy/assets ya extraído del código
  fuente Dart (que es la fuente de verdad real).

---

## 8. Explícitamente fuera de alcance (no auditado, por instrucción)

`android/`, `linux/`, `firebase.json`, `firestore.rules`, `.firebaserc`, `backend/`
(POSBUS/ticketing), `.claude/`, `.github/`, `scriptsql/`. No se leyó ni catalogó
contenido de estas carpetas.

---

## Checkpoint 1 — Decisiones confirmadas por el usuario (2026-09-06)

1. **Tarifas/Noticias**: eliminados del plan. No se crean modelos `Tarifa` ni `Noticia`.
   Fase 3 solo define `Ruta` y `Horario` (y lo necesario para Contacto, que es contenido
   mayormente estático/hardcodeado en template, no un modelo).
2. **Horarios/feriados reales**: se cargarán después manualmente vía el admin de Django
   (no hay export de Firestore por ahora). Fase 3 puede usar datos de estructura correcta
   pero de prueba, a sabiendas de que se reemplazan manualmente antes de producción.
3. **Clima en tiempo real**: se replica (widget OpenWeatherMap junto a cada salida, Inicio).
4. **Mapa (Ruta/Paraderos)**: se reemplaza el mapa interactivo de Google Maps JS por un
   **mapa estático** (imagen con los 2 terminales marcados/etiquetados — sin JS de Google
   Maps, sin API key, sin geolocalización GPS interactiva). Simplifica Fase 4 y evita
   reusar la API key expuesta del repo original.
5. **Modo oscuro**: se replica (toggle sol/luna en Horarios y Contacto, como en el original).
6. **Fuente "Montserrat"**: se mantiene el bug del original — no se importa de verdad vía
   Google Fonts, se deja caer a la fuente de sistema (system-ui), igual que hoy.
7. **3 assets sin uso** (`terminal_coy.png`, `background_route.png`, `ruta_240.png`):
   descartados. Ya eliminados de `assets_extraidos/`.
8. **Descarga de horarios como PNG**: se replica (misma función que en Flutter, generación
   de imagen desde los datos de horarios visibles).
9. **Navegación**: se unifica en un layout tipo sitio web normal — `base.html` con
   nav bar y footer consistentes en las 4 páginas (Inicio, Horarios, Contacto, Ruta),
   en vez de la navegación contextual sin nav fija del original.
10. **Analítica de visitas y notificaciones push**: quedan fuera del alcance (dependían de
    Firebase, no aplican a un sitio estático sin ese backend).

Estas decisiones ya están reflejadas en las secciones anteriores de este documento y
rigen a partir de Fase 1.
