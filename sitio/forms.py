from django import forms
from django.contrib.auth.forms import AuthenticationForm


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
