from django.urls import path

from . import views

app_name = "sitio"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("horarios/", views.horarios, name="horarios"),
    path("contacto/", views.contacto, name="contacto"),
    path("ruta/", views.ruta, name="ruta"),
]
