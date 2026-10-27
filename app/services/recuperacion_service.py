"""Logica de recuperacion de contrasena (Adenda 1).

Reglas de negocio, en un solo lugar y fuera de las rutas:

* La respuesta al usuario es **siempre la misma**, exista o no la cuenta, para
  no permitir enumerar correos registrados.
* El enlace es de **un solo uso**, caduca a los ``RECUPERACION_MINUTOS`` y
  anula cualquier enlace anterior de la misma cuenta.
* En la base solo se guarda el SHA-256 del token.
* Hay un limite de intentos por IP en memoria (mitigacion parcial de fuerza
  bruta y de spam de correos). No sustituye a un limitador distribuido: queda
  documentado como limitacion.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings
from app.core.security import generar_token_recuperacion, hash_token
from app.models import recuperacion as modelo
from app.models import usuario as usuario_model
from app.services import email_service

logger = logging.getLogger("ferreteria.recuperacion")

# Mensaje unico: no distingue entre correo registrado, inexistente o inactivo.
MENSAJE_SOLICITUD = (
    "Si el correo esta registrado, recibira un enlace para restablecer su "
    "contrasena en los proximos minutos."
)


class RecuperacionInvalida(Exception):
    """El token no existe, ya se uso o caduco."""


class DemasiadosIntentos(Exception):
    """Se supero el limite de solicitudes por IP."""


@dataclass(frozen=True)
class ResultadoSolicitud:
    """Resultado interno de una solicitud (nunca se expone tal cual)."""

    mensaje: str
    enviado: bool
    modo: str  # "smtp" | "consola" | "omitido" | "error"


class LimitadorIntentos:
    """Ventana deslizante en memoria: cuantas solicitudes por clave y por lapso."""

    def __init__(self) -> None:
        self._registros: dict[str, list[float]] = {}
        self._candado = threading.Lock()

    def permitir(self, clave: str, maximo: int, ventana_minutos: int) -> bool:
        ahora = time.monotonic()
        limite = ahora - ventana_minutos * 60

        with self._candado:
            marcas = [m for m in self._registros.get(clave, []) if m > limite]
            if len(marcas) >= maximo:
                self._registros[clave] = marcas
                return False
            marcas.append(ahora)
            self._registros[clave] = marcas
            return True

    def reiniciar(self) -> None:
        """Limpia el estado (utilidad para pruebas y reinicios controlados)."""
        with self._candado:
            self._registros.clear()


limitador = LimitadorIntentos()


def solicitar(
    correo: str,
    *,
    ip: str = "desconocida",
    settings: Settings | None = None,
) -> ResultadoSolicitud:
    """Genera el enlace y lo envia, sin revelar si el correo existe."""
    config = settings or get_settings()

    if not limitador.permitir(
        f"recuperar:{ip}", config.recuperacion_max_intentos, config.recuperacion_ventana_minutos
    ):
        logger.warning("Limite de solicitudes de recuperacion superado desde %s", ip)
        raise DemasiadosIntentos(MENSAJE_SOLICITUD)

    cuenta = usuario_model.buscar_por_correo(correo)

    if cuenta is None or not cuenta["activo"]:
        logger.info(
            "Solicitud de recuperacion sin cuenta activa asociada (correo no revelado)"
        )
        return ResultadoSolicitud(mensaje=MENSAJE_SOLICITUD, enviado=False, modo="omitido")

    token, token_hash = generar_token_recuperacion()
    modelo.crear(int(cuenta["id"]), token_hash, config.recuperacion_minutos)

    nombre = str(cuenta["nombre"]).split()[0] if cuenta["nombre"] else "usuario"
    envio = email_service.enviar_enlace_recuperacion(
        destinatario=str(cuenta["correo"]),
        nombre=nombre,
        token=token,
        minutos=config.recuperacion_minutos,
        settings=config,
    )

    return ResultadoSolicitud(mensaje=MENSAJE_SOLICITUD, enviado=envio.enviado, modo=envio.modo)


def restablecer(token: str, password_nueva: str) -> dict[str, Any]:
    """Consume el token y cambia la contrasena.

    Devuelve los datos publicos de la cuenta afectada. Lanza
    ``RecuperacionInvalida`` si el token no sirve.
    """
    if not token or not token.strip():
        raise RecuperacionInvalida("El enlace no es valido o ya fue utilizado")

    huella = hash_token(token.strip())
    id_usuario = modelo.consumir(huella)

    if id_usuario is None:
        logger.warning("Intento de restablecimiento con token invalido o vencido")
        raise RecuperacionInvalida("El enlace no es valido o ya fue utilizado")

    cuenta = usuario_model.buscar_por_id(id_usuario)
    if cuenta is None or not cuenta["activo"]:
        raise RecuperacionInvalida("La cuenta no esta disponible; contacte al administrador")

    # Importacion diferida: evita un ciclo entre seguridad y modelo.
    from app.core.security import hash_password

    usuario_model.actualizar_password(id_usuario, hash_password(password_nueva))
    modelo.invalidar_de_usuario(id_usuario)

    logger.info("Contrasena restablecida por enlace de recuperacion (id=%s)", id_usuario)
    return cuenta
