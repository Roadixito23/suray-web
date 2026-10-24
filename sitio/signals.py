from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import vivo
from .models import Aviso, Feriado, Horario, Ruta


@receiver([post_save, post_delete], sender=Horario)
@receiver([post_save, post_delete], sender=Feriado)
@receiver([post_save, post_delete], sender=Ruta)
@receiver([post_save, post_delete], sender=Aviso)
def invalidar_vivo(sender, **kwargs):
    vivo.invalidar()
