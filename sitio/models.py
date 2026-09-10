from django.db import models


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


class ConfiguracionSitio(models.Model):
    """Fila unica (pk=1) con ajustes globales del sitio editables desde el admin."""

    google_maps_api_key = models.CharField(
        max_length=200,
        blank=True,
        help_text="API key de Google Maps JavaScript API para el mapa interactivo de Ruta. "
                   "Restringela por dominio (HTTP referrer) en Google Cloud Console.",
    )

    class Meta:
        verbose_name = "Configuración del sitio"
        verbose_name_plural = "Configuración del sitio"

    def __str__(self):
        return "Configuración del sitio"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
