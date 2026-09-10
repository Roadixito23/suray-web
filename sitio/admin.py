from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.urls import reverse

from .models import ConfiguracionSitio, Feriado, Horario, HorarioOficina, Oficina, Ruta


class UsernamePasswordChangeForm(AdminPasswordChangeForm):
    username = forms.CharField(label="Usuario", max_length=150)

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields["username"].initial = user.username
        self.order_fields(["username", "password1", "password2"])

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("Ese nombre de usuario ya existe.")
        return username

    def save(self, commit=True):
        self.user.username = self.cleaned_data["username"]
        return super().save(commit=commit)


class CustomUserAdmin(UserAdmin):
    change_password_form = UsernamePasswordChangeForm


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Ruta)
class RutaAdmin(admin.ModelAdmin):
    list_display = ("origen", "destino")


@admin.register(ConfiguracionSitio)
class ConfiguracionSitioAdmin(admin.ModelAdmin):
    fields = ("google_maps_api_key",)

    def has_add_permission(self, request):
        return not ConfiguracionSitio.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = ConfiguracionSitio.load()
        return redirect(reverse("admin:sitio_configuracionsitio_change", args=[obj.pk]))


@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_display = ("ruta", "tipo_dia", "hora_salida", "es_horario_especial")
    ordering = ("tipo_dia", "ruta__origen", "hora_salida")

    class Media:
        js = ("admin/js/horario_time_format.js",)

    def changelist_view(self, request, extra_context=None):
        qs = Horario.objects.select_related("ruta").order_by("ruta__origen", "hora_salida")
        grupos = []
        for valor, etiqueta in Horario.TipoDia.choices:
            horarios = qs.filter(tipo_dia=valor)
            grupos.append({
                "slug": valor.lower(),
                "label": etiqueta,
                "horarios": horarios,
                "tiene_especial": horarios.filter(es_horario_especial=True).exists(),
            })
        extra_context = extra_context or {}
        extra_context["grupos"] = grupos
        return super().changelist_view(request, extra_context=extra_context)


class HorarioOficinaInline(admin.TabularInline):
    model = HorarioOficina
    fields = ("dia", "horario", "orden")
    ordering = ("orden",)
    extra = 1


@admin.register(Oficina)
class OficinaAdmin(admin.ModelAdmin):
    list_display = ("ciudad", "tipo", "direccion", "telefono", "orden")
    list_display_links = ("ciudad",)
    list_editable = ("orden",)
    list_filter = ("ciudad", "tipo")
    search_fields = ("ciudad", "direccion", "telefono")
    ordering = ("ciudad", "orden")
    inlines = [HorarioOficinaInline]


@admin.register(Feriado)
class FeriadoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "nombre", "sin_servicio")
    list_filter = ("sin_servicio",)
    ordering = ("fecha",)
