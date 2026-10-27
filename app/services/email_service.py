"""Envio de correo saliente (Adenda 1).

Usa solo ``smtplib`` y ``email.message`` de la biblioteca estandar: el sistema
no necesita ninguna dependencia extra para mandar el enlace de recuperacion.

Modo consola
------------
Si no hay SMTP configurado en ``.env`` (``SMTP_HOST`` y ``SMTP_REMITENTE``),
el contenido del correo se escribe en el log del proceso con nivel WARNING.
Eso permite demostrar el flujo completo en desarrollo y en las pruebas sin
montar un servidor de correo, sin inventar un mecanismo distinto al real.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import quote

from app.config import Settings, get_settings

logger = logging.getLogger("ferreteria.correo")

ASUNTO_RECUPERACION = "Recuperacion de contrasena - FERRE-INVERSIONES PEREZ C.A."
TIEMPO_ESPERA_SEGUNDOS = 10


@dataclass(frozen=True)
class ResultadoEnvio:
    """Como termino el intento de envio."""

    enviado: bool
    modo: str  # "smtp" | "consola" | "error"


def construir_enlace(token: str, settings: Settings | None = None) -> str:
    """Arma la URL que el usuario abrira desde el correo."""
    config = settings or get_settings()
    return f"{config.url_base}/restablecer?token={quote(token, safe='')}"


def _cuerpo(nombre: str, enlace: str, minutos: int) -> str:
    return (
        f"Hola {nombre},\n\n"
        "Recibimos una solicitud para restablecer la contrasena de su cuenta en "
        "el Sistema de Inventario de FERRE-INVERSIONES PEREZ C.A.\n\n"
        "Abra este enlace para crear una contrasena nueva:\n\n"
        f"{enlace}\n\n"
        f"El enlace es personal, se puede usar una sola vez y vence en {minutos} "
        "minutos.\n\n"
        "Si usted no solicito este cambio, ignore este mensaje: su contrasena "
        "actual sigue siendo valida.\n\n"
        "Este es un mensaje automatico; no responda a este correo.\n"
    )


def enviar_enlace_recuperacion(
    *,
    destinatario: str,
    nombre: str,
    token: str,
    minutos: int,
    settings: Settings | None = None,
) -> ResultadoEnvio:
    """Envia el enlace de recuperacion por SMTP o lo escribe en el log."""
    config = settings or get_settings()
    enlace = construir_enlace(token, config)
    cuerpo = _cuerpo(nombre, enlace, minutos)

    if not config.smtp_configurado:
        logger.warning(
            "SMTP no configurado: enlace de recuperacion para %s -> %s", destinatario, enlace
        )
        return ResultadoEnvio(enviado=True, modo="consola")

    mensaje = EmailMessage()
    mensaje["Subject"] = ASUNTO_RECUPERACION
    mensaje["From"] = formataddr((config.empresa, config.smtp_remitente))
    mensaje["To"] = destinatario
    mensaje.set_content(cuerpo)

    try:
        with smtplib.SMTP(
            config.smtp_host, config.smtp_puerto, timeout=TIEMPO_ESPERA_SEGUNDOS
        ) as servidor:
            servidor.ehlo()
            if config.smtp_tls:
                servidor.starttls()
                servidor.ehlo()
            if config.smtp_usuario:
                servidor.login(config.smtp_usuario, config.smtp_password)
            servidor.send_message(mensaje)
    except (smtplib.SMTPException, OSError) as exc:
        # El fallo se registra, pero la respuesta al usuario no cambia: revelar
        # "no se pudo enviar" permitiria deducir si el correo existe.
        logger.error("No se pudo enviar el correo a %s: %s", destinatario, exc)
        return ResultadoEnvio(enviado=False, modo="error")

    logger.info("Enlace de recuperacion enviado a %s", destinatario)
    return ResultadoEnvio(enviado=True, modo="smtp")
