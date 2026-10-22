from django.urls import path

from . import views, views_edit

app_name = "sitio"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("horarios/", views.horarios, name="horarios"),
    path("contacto/", views.contacto, name="contacto"),
    path("ruta/", views.ruta, name="ruta"),
    path("edit/", views_edit.edit_inicio, name="edit_inicio"),
    path("edit/login/", views_edit.edit_login, name="edit_login"),
    path("edit/logout/", views_edit.edit_logout, name="edit_logout"),
    path("edit/horarios/<str:tipo>/", views_edit.edit_horarios, name="edit_horarios"),
]
