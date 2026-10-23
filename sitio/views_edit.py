from datetime import datetime
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.core.cache import cache
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse, reverse_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .forms import CuentaForm, EditAuthenticationForm, FeriadoForm, HorarioOficinaFormSet, OficinaForm
from .models import Feriado, Horario, Oficina, Ruta

MAX_INTENTOS = 5
BLOQUEO_SEGUNDOS = 15 * 60

TIPOS = {
    "lv": Horario.TipoDia.LUNES_VIERNES,
    "sab": Horario.TipoDia.SABADO,
    "df": Horario.TipoDia.DOMINGO_FERIADO,
}


def no_indexable(view):
    """Cabeceras para que buscadores y caches no guarden nada de /edit/."""

    @wraps(view)
    def envuelta(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response

    return never_cache(envuelta)


def solo_staff(view):
    @wraps(view)
    def envuelta(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('sitio:edit_login')}?next={request.path}")
        if not (request.user.is_active and request.user.is_staff):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return envuelta


def _clave_intentos(request, username):
    ip = request.META.get("REMOTE_ADDR", "")
    return f"edit-login:{ip}:{(username or '').strip().lower()}"


class EditLoginView(LoginView):
    template_name = "edit/login.html"
    authentication_form = EditAuthenticationForm
    redirect_authenticated_user = True
    next_page = reverse_lazy("sitio:edit_inicio")

    def post(self, request, *args, **kwargs):
        clave = _clave_intentos(request, request.POST.get("username"))
        if cache.get(clave, 0) >= MAX_INTENTOS:
            form = self.get_form()
            form.is_valid()
            form.add_error(None, "Demasiados intentos. Espera 15 minutos e inténtalo de nuevo.")
            response = self.render_to_response(self.get_context_data(form=form))
            response.status_code = 429
            return response
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        clave = _clave_intentos(self.request, self.request.POST.get("username"))
        cache.add(clave, 0, BLOQUEO_SEGUNDOS)
        cache.incr(clave)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(_clave_intentos(self.request, self.request.POST.get("username")))
        return super().form_valid(form)


edit_login = no_indexable(EditLoginView.as_view())
edit_logout = no_indexable(LogoutView.as_view(next_page=reverse_lazy("sitio:edit_login")))


@no_indexable
@solo_staff
def edit_inicio(request):
    return redirect("sitio:edit_horarios", tipo="lv")


def _filas_desde_bd(ruta, tipo_dia):
    horas = Horario.objects.filter(ruta=ruta, tipo_dia=tipo_dia).order_by("hora_salida")
    return [{"valor": h.hora_salida.strftime("%H:%M"), "error": ""} for h in horas]


def _bloques(tipo_dia, post=None):
    """Una entrada por ciudad de origen, con sus filas (de la BD o del POST)."""
    bloques = []
    hay_errores = False
    for ruta in Ruta.objects.order_by("id"):
        if post is None:
            filas = _filas_desde_bd(ruta, tipo_dia)
        else:
            filas = []
            vistos = set()
            for crudo in post.getlist(f"horas_{ruta.id}"):
                valor = crudo.strip()
                if not valor:
                    continue
                fila = {"valor": valor, "error": ""}
                try:
                    hora = datetime.strptime(valor, "%H:%M").time()
                except ValueError:
                    fila["error"] = "Usa el formato HH:MM, por ejemplo 07:30."
                    hay_errores = True
                else:
                    if hora in vistos:
                        continue
                    vistos.add(hora)
                    fila["valor"] = hora.strftime("%H:%M")
                    fila["hora"] = hora
                filas.append(fila)
        bloques.append({"ruta": ruta, "filas": filas})
    return bloques, hay_errores


@no_indexable
@solo_staff
@require_http_methods(["GET", "POST"])
def edit_horarios(request, tipo):
    if tipo not in TIPOS:
        raise Http404
    tipo_dia = TIPOS[tipo]

    if request.method == "POST":
        bloques, hay_errores = _bloques(tipo_dia, request.POST)
        especial = request.POST.get("especial") == "on"
        if not hay_errores:
            with transaction.atomic():
                for bloque in bloques:
                    nuevas = {f["hora"] for f in bloque["filas"]}
                    existentes = Horario.objects.filter(ruta=bloque["ruta"], tipo_dia=tipo_dia)
                    existentes.exclude(hora_salida__in=nuevas).delete()
                    ya_estan = set(existentes.values_list("hora_salida", flat=True))
                    Horario.objects.bulk_create([
                        Horario(ruta=bloque["ruta"], tipo_dia=tipo_dia, hora_salida=hora)
                        for hora in sorted(nuevas - ya_estan)
                    ])
                Horario.objects.filter(tipo_dia=tipo_dia).update(es_horario_especial=especial)
            messages.success(request, "Horarios guardados.")
            return HttpResponseRedirect(reverse("sitio:edit_horarios", args=[tipo]))
        messages.error(request, "Revisa las horas marcadas. No se guardó nada.")
    else:
        bloques, _ = _bloques(tipo_dia)
        especial = Horario.objects.filter(tipo_dia=tipo_dia, es_horario_especial=True).exists()

    return render(request, "edit/horarios.html", {
        "tipo": tipo,
        "tabs": [(slug, Horario.TipoDia(valor).label) for slug, valor in TIPOS.items()],
        "bloques": bloques,
        "especial": especial,
    })


def _tarjeta_oficina(oficina, post=None):
    return {
        "oficina": oficina,
        "form": OficinaForm(post, instance=oficina, prefix=f"of{oficina.pk}"),
        "horarios": HorarioOficinaFormSet(post, instance=oficina, prefix=f"h{oficina.pk}"),
    }


@no_indexable
@solo_staff
@require_http_methods(["GET", "POST"])
def edit_oficinas(request, pk=None):
    if request.method == "POST" and pk is None:
        raise Http404
    tarjetas = []
    for oficina in Oficina.objects.order_by("ciudad", "orden"):
        if request.method == "POST" and oficina.pk == pk:
            tarjeta = _tarjeta_oficina(oficina, request.POST)
            if tarjeta["form"].is_valid() and tarjeta["horarios"].is_valid():
                with transaction.atomic():
                    tarjeta["form"].save()
                    formset = tarjeta["horarios"]
                    nuevos = formset.save(commit=False)
                    for obj in formset.deleted_objects:
                        obj.delete()
                    siguiente = (oficina.horarios.aggregate(m=Max("orden"))["m"] or 0) + 1
                    for obj in nuevos:
                        if obj.pk is None:
                            obj.orden = siguiente
                            siguiente += 1
                        obj.save()
                messages.success(request, f"Guardado: {oficina}.")
                return HttpResponseRedirect(f"{reverse('sitio:edit_oficinas')}#oficina-{oficina.pk}")
            messages.error(request, f"Revisa los campos marcados de {oficina}. No se guardó nada.")
        else:
            tarjeta = _tarjeta_oficina(oficina)
        tarjetas.append(tarjeta)
    return render(request, "edit/oficinas.html", {"tarjetas": tarjetas})


@no_indexable
@solo_staff
@require_http_methods(["GET", "POST"])
def edit_feriados(request):
    form = FeriadoForm()
    if request.method == "POST":
        if request.POST.get("accion") == "eliminar":
            feriado = get_object_or_404(Feriado, pk=request.POST.get("feriado"))
            feriado.delete()
            messages.success(request, f"Feriado eliminado: {feriado.nombre}.")
            return redirect("sitio:edit_feriados")
        form = FeriadoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Feriado agregado.")
            return redirect("sitio:edit_feriados")
        messages.error(request, "Revisa los campos marcados. No se guardó nada.")
    hoy = timezone.localdate()
    return render(request, "edit/feriados.html", {
        "form": form,
        "proximos": Feriado.objects.filter(fecha__gte=hoy).order_by("fecha"),
        "pasados": Feriado.objects.filter(fecha__lt=hoy).order_by("-fecha"),
    })


@no_indexable
@solo_staff
@require_http_methods(["GET", "POST"])
def edit_cuenta(request):
    if request.method == "POST":
        form = CuentaForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Cuenta actualizada.")
            return redirect("sitio:edit_cuenta")
        messages.error(request, "Revisa los campos marcados. No se guardó nada.")
    else:
        form = CuentaForm(request.user)
    return render(request, "edit/cuenta.html", {"form": form})
