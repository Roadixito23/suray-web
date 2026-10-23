"""Clima actual de las ciudades de origen, desde Open-Meteo (sin API key)."""
import json
import logging
from urllib.parse import urlencode
from urllib.request import urlopen

from django.core.cache import cache

logger = logging.getLogger(__name__)

API_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 3  # segundos; la portada no debe quedar esperando a la API
CACHE_KEY = "clima_actual"
CACHE_OK = 15 * 60
CACHE_ERROR = 60  # tras un fallo no se reintenta en cada visita

# Mismos terminales que usa la vista de la ruta.
CIUDADES = {
    "Puerto Aysén": (-45.40111614852224, -72.68738064167634),
    "Coyhaique": (-45.582039, -72.078136),
}

# Codigos WMO de Open-Meteo -> (icono, descripcion corta).
_CODIGOS = {
    0: ("☀️", "Despejado"),
    1: ("🌤️", "Mayormente despejado"),
    2: ("⛅", "Parcialmente nublado"),
    3: ("☁️", "Nublado"),
    45: ("🌫️", "Niebla"),
    48: ("🌫️", "Niebla con escarcha"),
    51: ("🌦️", "Llovizna ligera"),
    53: ("🌦️", "Llovizna"),
    55: ("🌧️", "Llovizna intensa"),
    56: ("🌧️", "Llovizna helada"),
    57: ("🌧️", "Llovizna helada"),
    61: ("🌧️", "Lluvia ligera"),
    63: ("🌧️", "Lluvia"),
    65: ("🌧️", "Lluvia intensa"),
    66: ("🌧️", "Lluvia helada"),
    67: ("🌧️", "Lluvia helada"),
    71: ("🌨️", "Nevada ligera"),
    73: ("🌨️", "Nevada"),
    75: ("❄️", "Nevada intensa"),
    77: ("🌨️", "Granizo fino"),
    80: ("🌦️", "Chubascos ligeros"),
    81: ("🌧️", "Chubascos"),
    82: ("⛈️", "Chubascos fuertes"),
    85: ("🌨️", "Chubascos de nieve"),
    86: ("🌨️", "Chubascos de nieve"),
    95: ("⛈️", "Tormenta"),
    96: ("⛈️", "Tormenta con granizo"),
    99: ("⛈️", "Tormenta con granizo"),
}


def describir(codigo, es_dia=True):
    icono, texto = _CODIGOS.get(codigo, ("🌡️", "Sin datos"))
    if codigo in (0, 1) and not es_dia:
        icono = "🌙"
    return icono, texto


def _consultar():
    nombres = list(CIUDADES)
    params = urlencode({
        "latitude": ",".join(str(CIUDADES[n][0]) for n in nombres),
        "longitude": ",".join(str(CIUDADES[n][1]) for n in nombres),
        "current": "temperature_2m,weather_code,is_day",
        "timezone": "America/Santiago",
    })
    with urlopen(f"{API_URL}?{params}", timeout=TIMEOUT) as resp:
        datos = json.load(resp)
    if isinstance(datos, dict):
        datos = [datos]

    clima = {}
    for nombre, item in zip(nombres, datos):
        actual = item["current"]
        icono, texto = describir(actual["weather_code"], bool(actual.get("is_day", 1)))
        clima[nombre] = {
            "temperatura": round(actual["temperature_2m"]),
            "icono": icono,
            "descripcion": texto,
        }
    return clima


def clima_actual():
    """Devuelve {ciudad: {temperatura, icono, descripcion}}; {} si la API falla."""
    clima = cache.get(CACHE_KEY)
    if clima is not None:
        return clima
    try:
        clima = _consultar()
        cache.set(CACHE_KEY, clima, CACHE_OK)
    except Exception:
        logger.warning("No se pudo obtener el clima de Open-Meteo", exc_info=True)
        clima = {}
        cache.set(CACHE_KEY, clima, CACHE_ERROR)
    return clima
