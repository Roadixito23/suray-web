from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.forms import inlineformset_factory

from .models import Feriado, HorarioOficina, Oficina


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


class FeriadoForm(forms.ModelForm):
    class Meta:
        model = Feriado
        fields = ("fecha", "nombre", "sin_servicio")
        labels = {"fecha": "Fecha", "nombre": "Nombre", "sin_servicio": "Sin servicio de buses"}
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
        error_messages = {"fecha": {"unique": "Ya hay un feriado en esa fecha."}}


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
