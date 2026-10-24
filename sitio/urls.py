from django.urls import path

from . import views, views_edit

app_name = "sitio"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("horarios/", views.horarios, name="horarios"),
    path("vivo/<str:nombre>/", views.vivo_fragmento, name="vivo"),
    path("contacto/", views.contacto, name="contacto"),
    path("ruta/", views.ruta, name="ruta"),
    path("edit/", views_edit.edit_inicio, name="edit_inicio"),
    path("edit/login/", views_edit.edit_login, name="edit_login"),
    path("edit/logout/", views_edit.edit_logout, name="edit_logout"),
    path("edit/horarios/<str:tipo>/", views_edit.edit_horarios, name="edit_horarios"),
    path("edit/oficinas/", views_edit.edit_oficinas, name="edit_oficinas"),
    path("edit/oficinas/<int:pk>/", views_edit.edit_oficinas, name="edit_oficina"),
    path("edit/feriados/", views_edit.edit_feriados, name="edit_feriados"),
    path("edit/avisos/", views_edit.edit_avisos, name="edit_avisos"),
    path("edit/avisos/<int:pk>/", views_edit.edit_avisos, name="edit_aviso"),
    path("edit/cuenta/", views_edit.edit_cuenta, name="edit_cuenta"),
]
