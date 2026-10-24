from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.forms import inlineformset_factory

from .models import Aviso, Feriado, HorarioOficina, Oficina


class EditAuthenticationForm(AuthenticationForm):
    """Login de /edit/: solo entra personal (is_staff), con un unico mensaje de error."""

    error_messages = {
        "invalid_login": "Usuario o contraseña incorrectos.",
        "inactive": "Usuario o contraseña incorrectos.",
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError(
                self.error_messages["invalid_login"], code="invalid_login"
            )


class OficinaForm(forms.ModelForm):
    class Meta:
        model = Oficina
        fields = ("direccion", "telefono", "mapa_url")
        labels = {"direccion": "Dirección", "telefono": "Teléfono", "mapa_url": "Enlace del mapa"}


HorarioOficinaFormSet = inlineformset_factory(
    Oficina, HorarioOficina, fields=("dia", "horario"), extra=1, can_delete=True,
    labels={"dia": "Día", "horario": "Horario"},
)


FORMATOS_FECHA = ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"]  # Chile primero; ISO por compatibilidad


def _fecha_chile():
    """Campo de texto DD-MM-AAAA (static/js/fecha-chile.js le agrega mascara y calendario)."""
    return forms.DateInput(format="%d-%m-%Y", attrs={
        "type": "text", "inputmode": "numeric", "placeholder": "DD-MM-AAAA",
        "maxlength": "10", "autocomplete": "off", "data-fecha-cl": "",
    })


def _formato_chile(form, *nombres):
    for n in nombres:
        form.fields[n].input_formats = FORMATOS_FECHA
        form.fields[n].error_messages["invalid"] = "Escribe la fecha como DD-MM-AAAA, por ejemplo 25-12-2026."


class FeriadoForm(forms.ModelForm):
    class Meta:
        model = Feriado
        fields = ("fecha", "nombre", "sin_servicio")
        labels = {"fecha": "Fecha", "nombre": "Nombre", "sin_servicio": "Sin servicio de buses"}
        widgets = {"fecha": _fecha_chile()}
        error_messages = {"fecha": {"unique": "Ya hay un feriado en esa fecha."}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _formato_chile(self, "fecha")


class _ColorInput(forms.TextInput):
    input_type = "color"


class AvisoForm(forms.ModelForm):
    colores_propios = forms.BooleanField(
        required=False, label="Usar colores propios (si no, se usan los del tipo de aviso)",
    )

    field_order = [
        "tipo", "titulo", "mensaje", "imagen_url", "posicion", "formato", "direccion", "velocidad",
        "colores_propios",
        "estilo_color", "color_principal", "color_secundario", "desde", "hasta", "activo",
    ]

    class Meta:
        model = Aviso
        fields = (
            "tipo", "titulo", "mensaje", "imagen_url", "posicion", "formato", "direccion", "velocidad",
            "estilo_color", "color_principal", "color_secundario", "desde", "hasta", "activo",
        )
        labels = {
            "tipo": "Tipo", "titulo": "Título", "mensaje": "Mensaje (opcional)",
            "imagen_url": "Imagen (URL https, opcional)", "posicion": "Ubicación en Inicio",
            "formato": "Formato", "direccion": "Dirección del carrusel", "velocidad": "Velocidad del carrusel",
            "estilo_color": "Estilo de color",
            "color_principal": "Color principal", "color_secundario": "Color secundario",
            "desde": "Mostrar desde", "hasta": "Mostrar hasta", "activo": "Publicado",
        }
        widgets = {
            "color_principal": _ColorInput(),
            "color_secundario": _ColorInput(),
            "imagen_url": forms.URLInput(attrs={"placeholder": "https://..."}),
            "mensaje": forms.Textarea(attrs={"rows": 3}),
            "desde": _fecha_chile(),
            "hasta": _fecha_chile(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _formato_chile(self, "desde", "hasta")
        inst = self.instance
        self.fields["colores_propios"].initial = bool(inst.color_principal)
        # El selector de color no admite vacio: se muestra con un valor de partida.
        self.initial["color_principal"] = inst.color_principal or "#F47200"
        self.initial["color_secundario"] = inst.color_secundario or "#001959"

    def clean(self):
        datos = super().clean()
        if not datos.get("colores_propios"):
            # Sin colores propios, solido y degradado dejarian texto blanco sobre el naranja del
            # sitio (poco contraste): se usa el borde de color del tipo de aviso.
            datos["color_principal"] = datos["color_secundario"] = ""
            datos["estilo_color"] = Aviso.EstiloColor.BORDE
            self.instance.estilo_color = Aviso.EstiloColor.BORDE
        desde, hasta = datos.get("desde"), datos.get("hasta")
        if desde and hasta and hasta < desde:
            self.add_error("hasta", "La fecha final no puede ser anterior a la inicial.")
        return datos


class CuentaForm(forms.Form):
    """Cambia el usuario y, opcionalmente, la contraseña de quien está conectado."""

    username = forms.CharField(label="Usuario", max_length=150)
    password_actual = forms.CharField(label="Contraseña actual", widget=forms.PasswordInput)
    password1 = forms.CharField(label="Contraseña nueva (opcional)", required=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label="Repite la contraseña nueva", required=False, widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["username"].initial = user.get_username()

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if get_user_model().objects.filter(username=username).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("Ese nombre de usuario ya existe.")
        return username

    def clean_password_actual(self):
        if not self.user.check_password(self.cleaned_data["password_actual"]):
            raise forms.ValidationError("La contraseña actual no es correcta.")
        return self.cleaned_data["password_actual"]

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "Las contraseñas no coinciden.")
            else:
                try:
                    password_validation.validate_password(p1, self.user)
                except forms.ValidationError as e:
                    self.add_error("password1", e)
        return datos

    def save(self):
        self.user.username = self.cleaned_data["username"]
        if self.cleaned_data["password1"]:
            self.user.set_password(self.cleaned_data["password1"])
        self.user.save()
        return self.user
