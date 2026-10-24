from django.core.validators import RegexValidator, URLValidator
from django.db import models

validar_color = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Usa un color con formato #RRGGBB.")
validar_https = URLValidator(schemes=["https"], message="La imagen debe ser una URL que empiece con https://")


def _luminancia(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


class Ruta(models.Model):
    origen = models.CharField(max_length=100)
    destino = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Ruta"
        verbose_name_plural = "Rutas"

    def __str__(self):
        return f"{self.origen} → {self.destino}"


class Horario(models.Model):
    class TipoDia(models.TextChoices):
        LUNES_VIERNES = "LV", "Lunes a Viernes"
        SABADO = "SAB", "Sábados"
        DOMINGO_FERIADO = "DF", "Domingo o Feriado"

    ruta = models.ForeignKey(Ruta, on_delete=models.CASCADE, related_name="horarios")
    hora_salida = models.TimeField()
    tipo_dia = models.CharField(max_length=3, choices=TipoDia.choices)
    es_horario_especial = models.BooleanField(
        default=False,
        help_text="Marca este horario como 'HORARIO ESPECIAL' (ej. feriado con salidas distintas a lo habitual).",
    )

    class Meta:
        verbose_name = "Horario"
        verbose_name_plural = "Horarios"
        ordering = ["tipo_dia", "ruta__origen", "hora_salida"]

    def __str__(self):
        return f"{self.ruta.origen} - {self.get_tipo_dia_display()} - {self.hora_salida}"


class Oficina(models.Model):
    class Tipo(models.TextChoices):
        PASAJES = "PJ", "Oficina de venta de pasajes"
        CORRESPONDENCIA = "CO", "Oficina de correspondencia"

    ciudad = models.CharField(max_length=100)
    tipo = models.CharField(max_length=2, choices=Tipo.choices)
    direccion = models.CharField(max_length=200)
    telefono = models.CharField(max_length=50)
    mapa_url = models.URLField(blank=True, help_text="Link corto de Google Maps (maps.app.goo.gl/...).")
    orden = models.PositiveSmallIntegerField(default=0, help_text="Controla el orden dentro de la ciudad.")

    class Meta:
        verbose_name = "Oficina"
        verbose_name_plural = "Oficinas"
        ordering = ["ciudad", "orden"]

    def __str__(self):
        return f"{self.ciudad} — {self.get_tipo_display()}"


class HorarioOficina(models.Model):
    oficina = models.ForeignKey(Oficina, on_delete=models.CASCADE, related_name="horarios")
    dia = models.CharField(max_length=50, help_text="Ej. 'Lun-Vie', 'Sábado', 'Domingo'.")
    horario = models.CharField(max_length=100, help_text="Ej. '06:30–19:00' o 'Cerrado'.")
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Horario de oficina"
        verbose_name_plural = "Horarios de oficina"
        ordering = ["oficina", "orden"]

    def __str__(self):
        return f"{self.oficina} — {self.dia}: {self.horario}"


class Feriado(models.Model):
    fecha = models.DateField(unique=True)
    nombre = models.CharField(max_length=150)
    sin_servicio = models.BooleanField(
        default=False,
        help_text="Marca si este feriado no tiene salidas (equivalente a 'Sin servicio por feriado').",
    )

    class Meta:
        verbose_name = "Feriado"
        verbose_name_plural = "Feriados"
        ordering = ["fecha"]

    def __str__(self):
        return f"{self.fecha} - {self.nombre}"


class Aviso(models.Model):
    class Tipo(models.TextChoices):
        SUSPENSION = "suspension", "Suspensión de recorrido"
        OFERTA = "oferta", "Oferta"
        INFO = "info", "Información"

    titulo = models.CharField(max_length=120)
    mensaje = models.TextField(max_length=500, blank=True)
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.INFO)
    activo = models.BooleanField(default=True)
    desde = models.DateField(null=True, blank=True, help_text="Primer día en que se muestra. Vacío = desde ya.")
    hasta = models.DateField(null=True, blank=True, help_text="Último día en que se muestra. Vacío = sin fin.")
    creado = models.DateTimeField(auto_now_add=True)

    class Posicion(models.TextChoices):
        ARRIBA = "arriba", "Arriba de las próximas salidas"
        MEDIO = "medio", "Abajo de las próximas salidas"
        BOTON = "boton", "Abajo del botón «Todos los horarios»"

    class Formato(models.TextChoices):
        SIMPLE = "simple", "Aviso simple"
        CARTEL = "cartel", "Cartel grande (card)"
        CARRUSEL = "carrusel", "Carrusel tipo noticiero"

    class EstiloColor(models.TextChoices):
        SOLIDO = "solido", "Sólido"
        DEGRADADO = "degradado", "Degradado"
        BORDE = "borde", "Borde de color"

    class Direccion(models.TextChoices):
        IZQ_DER = "izq_der", "De izquierda a derecha"
        DER_IZQ = "der_izq", "De derecha a izquierda"

    class Velocidad(models.TextChoices):
        LENTA = "lenta", "Lenta"
        NORMAL = "normal", "Normal"
        RAPIDA = "rapida", "Rápida"

    VELOCIDAD_PX_S = {"lenta": 40, "normal": 80, "rapida": 140}

    direccion = models.CharField(max_length=8, choices=Direccion.choices, default=Direccion.IZQ_DER)
    velocidad = models.CharField(max_length=8, choices=Velocidad.choices, default=Velocidad.NORMAL)
    posicion = models.CharField(max_length=10, choices=Posicion.choices, default=Posicion.ARRIBA)
    formato = models.CharField(max_length=10, choices=Formato.choices, default=Formato.SIMPLE)
    estilo_color = models.CharField(max_length=10, choices=EstiloColor.choices, default=EstiloColor.BORDE)
    color_principal = models.CharField(max_length=7, blank=True, validators=[validar_color])
    color_secundario = models.CharField(max_length=7, blank=True, validators=[validar_color])
    imagen_url = models.URLField(max_length=500, blank=True, validators=[validar_https])

    class Meta:
        verbose_name = "Aviso"
        verbose_name_plural = "Avisos"
        ordering = ["-creado"]

    def __str__(self):
        return self.titulo

    @property
    def color_texto(self):
        """Blanco o negro segun el fondo, para mantener el contraste."""
        if not self.color_principal or self.estilo_color == self.EstiloColor.BORDE:
            return "#FFFFFF"  # el estilo borde va sobre el panel oscuro del sitio
        colores = [self.color_principal]
        if self.estilo_color == self.EstiloColor.DEGRADADO and self.color_secundario:
            colores.append(self.color_secundario)
        lums = [_luminancia(c) for c in colores]
        # Gana el color de texto cuyo peor contraste (sobre cualquiera de los fondos) es mayor.
        con_negro = min((l + 0.05) / 0.05 for l in lums)
        con_blanco = min(1.05 / (l + 0.05) for l in lums)
        return "#000000" if con_negro > con_blanco else "#FFFFFF"

    @property
    def mensaje_linea(self):
        """El mensaje en una sola linea, para el texto corrido del noticiero."""
        return " · ".join(l.strip() for l in self.mensaje.splitlines() if l.strip())

    @property
    def ticker_segundos(self):
        """Duracion de una vuelta del noticiero: lo que mide la cinta (~11 px por caracter, minimo
        un ancho de pantalla de ~1200 px) dividido por la velocidad elegida en px/s."""
        ancho = max(1200, len(self.mensaje_linea) * 11)
        return max(4, round(ancho / self.VELOCIDAD_PX_S[self.velocidad]))

    @property
    def estilo_css(self):
        """Variables CSS del aviso; solo contiene colores #RRGGBB ya validados."""
        if not self.color_principal:
            return ""
        alt = self.color_secundario or self.color_principal
        return f"--n-main:{self.color_principal};--n-alt:{alt};--n-ink:{self.color_texto}"
