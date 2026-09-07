from django.contrib import admin

from .models import Feriado, Horario, HorarioOficina, Oficina, Ruta


@admin.register(Ruta)
class RutaAdmin(admin.ModelAdmin):
    list_display = ("origen", "destino")


@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_display = ("ruta", "tipo_dia", "hora_salida", "es_horario_especial")
    list_filter = ("tipo_dia", "ruta", "es_horario_especial")
    ordering = ("tipo_dia", "ruta__origen", "hora_salida")


class HorarioOficinaInline(admin.TabularInline):
    model = HorarioOficina
    extra = 1


@admin.register(Oficina)
class OficinaAdmin(admin.ModelAdmin):
    list_display = ("ciudad", "tipo", "direccion", "telefono", "orden")
    list_filter = ("ciudad", "tipo")
    ordering = ("ciudad", "orden")
    inlines = [HorarioOficinaInline]


@admin.register(Feriado)
class FeriadoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "nombre", "sin_servicio")
    list_filter = ("sin_servicio",)
    ordering = ("fecha",)
