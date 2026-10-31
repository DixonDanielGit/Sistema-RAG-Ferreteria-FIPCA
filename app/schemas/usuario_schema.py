"""Esquemas Pydantic de autenticacion y usuarios (RF-01).

Los esquemas validan la forma y el contenido de todo lo que entra por la API.
``extra="forbid"`` rechaza campos no previstos: un atacante no puede inyectar
propiedades adicionales esperando que el servidor las interprete.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.security import LONGITUD_MAXIMA, PasswordInvalida, validar_fortaleza
from app.core.permisos import validar_capacidades

PATRON_USUARIO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{2,48}[A-Za-z0-9]")
PATRON_ROL = re.compile(r"[a-z][a-z0-9_-]{1,49}")
PATRON_CORREO = re.compile(
    r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}"
)
PATRON_CEDULA = re.compile(r"[VEJPG]?-?[0-9]{5,9}", re.IGNORECASE)
PATRON_NOMBRE = re.compile(r"[^\W\d_](?:[^\W\d_]|[ .'-])*", re.UNICODE)

class LoginRequest(BaseModel):
    """Credenciales de entrada. El identificador acepta usuario o correo."""

    model_config = ConfigDict(extra="forbid")

    identificador: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=LONGITUD_MAXIMA)

    @field_validator("identificador")
    @classmethod
    def _limpiar_identificador(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("El usuario o correo es obligatorio")
        if any(c in limpio for c in "\r\n\t\0"):
            raise ValueError("El identificador contiene caracteres no permitidos")
        if "@" in limpio:
            return validar_correo(limpio)
        return validar_usuario(limpio)

    @field_validator("password")
    @classmethod
    def _password_no_vacio(cls, valor: str) -> str:
        if not valor:
            raise ValueError("La contrasena es obligatoria")
        return valor


class UsuarioRegistro(BaseModel):
    """Datos para dar de alta una cuenta."""

    model_config = ConfigDict(extra="forbid")

    cedula: str = Field(min_length=5, max_length=20)
    nombre: str = Field(min_length=2, max_length=100)
    apellido: str = Field(min_length=2, max_length=100)
    usuario: str = Field(min_length=4, max_length=50)
    correo: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=LONGITUD_MAXIMA)
    rol: str = Field(default="ventas", max_length=50)

    @field_validator("cedula")
    @classmethod
    def _validar_cedula(cls, valor: str) -> str:
        return validar_cedula(valor)

    @field_validator("nombre", "apellido")
    @classmethod
    def _validar_nombre(cls, valor: str) -> str:
        return validar_nombre(valor)

    @field_validator("usuario")
    @classmethod
    def _validar_usuario(cls, valor: str) -> str:
        return validar_usuario(valor)

    @field_validator("correo")
    @classmethod
    def _validar_correo(cls, valor: str) -> str:
        return validar_correo(valor)

    @field_validator("password")
    @classmethod
    def _validar_password(cls, valor: str) -> str:
        try:
            validar_fortaleza(valor)
        except PasswordInvalida as exc:
            raise ValueError(str(exc)) from exc
        return valor

    @field_validator("rol")
    @classmethod
    def _validar_rol(cls, valor: str) -> str:
        return validar_rol(valor)


class UsuarioSalida(BaseModel):
    """Datos publicos de una cuenta. Nunca incluye el hash de la contrasena."""

    model_config = ConfigDict(extra="ignore")

    id: int
    cedula: str
    nombre: str
    apellido: str
    usuario: str
    correo: str
    rol: str
    rol_descripcion: str | None = None
    permisos: list[str] = Field(default_factory=list)
    activo: bool
    tiene_imagen: bool = False


def validar_cedula(valor: str) -> str:
    limpio = valor.strip().upper()
    if not PATRON_CEDULA.fullmatch(limpio):
        raise ValueError("Cedula invalida: use el formato V-12345678 o 12345678")
    return limpio


def validar_nombre(valor: str) -> str:
    limpio = " ".join(valor.split())
    if not PATRON_NOMBRE.fullmatch(limpio):
        raise ValueError("El nombre admite letras, espacios, apostrofes, puntos y guiones")
    return limpio.title()


def validar_usuario(valor: str) -> str:
    limpio = valor.strip().lower()
    if not PATRON_USUARIO.fullmatch(limpio):
        raise ValueError(
            "El usuario debe tener entre 4 y 50 caracteres alfanumericos, "
            "puntos, guiones o guion bajo, y empezar y terminar con letra o numero"
        )
    return limpio


def validar_correo(valor: str) -> str:
    limpio = valor.strip().lower()
    if not PATRON_CORREO.fullmatch(limpio):
        raise ValueError("Use el formato nombre@dominio.com con un dominio valido")
    return limpio


def validar_rol(valor: str) -> str:
    limpio = valor.strip().lower()
    if not PATRON_ROL.fullmatch(limpio):
        raise ValueError("El rol debe ser una clave de 2 a 50 caracteres: letras, numeros, guiones o guiones bajos")
    return limpio


class PerfilActualizar(BaseModel):
    """Campos editables del perfil propio; el rol y el estado son inmutables aquí."""

    model_config = ConfigDict(extra="forbid")

    cedula: str = Field(min_length=5, max_length=20)
    nombre: str = Field(min_length=2, max_length=100)
    apellido: str = Field(min_length=2, max_length=100)
    usuario: str = Field(min_length=4, max_length=50)
    correo: str = Field(min_length=5, max_length=255)

    @field_validator("cedula")
    @classmethod
    def _validar_cedula(cls, valor: str) -> str:
        return validar_cedula(valor)

    @field_validator("nombre", "apellido")
    @classmethod
    def _validar_nombre(cls, valor: str) -> str:
        return validar_nombre(valor)

    @field_validator("usuario")
    @classmethod
    def _validar_usuario(cls, valor: str) -> str:
        return validar_usuario(valor)

    @field_validator("correo")
    @classmethod
    def _validar_correo(cls, valor: str) -> str:
        return validar_correo(valor)


class RolActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rol: str = Field(min_length=1, max_length=50)

    @field_validator("rol")
    @classmethod
    def _validar_rol(cls, valor: str) -> str:
        return validar_rol(valor)


class UsuarioAdminActualizar(PerfilActualizar):
    """Campos editables por administración sin permitir modificar el estado."""

    rol: str = Field(min_length=1, max_length=50)

    @field_validator("rol")
    @classmethod
    def _validar_rol(cls, valor: str) -> str:
        return validar_rol(valor)


class EstadoCuentaActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activo: bool


class TokenRespuesta(BaseModel):
    """Respuesta del login."""

    access_token: str
    token_type: str = "bearer"
    expira_en: int = Field(description="Segundos de vigencia del token")
    expira_en_utc: datetime
    usuario: UsuarioSalida


class MensajeRespuesta(BaseModel):
    mensaje: str
    detalle: str | None = None


class RecuperarPasswordRequest(BaseModel):
    """Solicitud de enlace de recuperacion (Adenda 1)."""

    model_config = ConfigDict(extra="forbid")

    correo: str = Field(min_length=5, max_length=255)

    @field_validator("correo")
    @classmethod
    def _validar_correo(cls, valor: str) -> str:
        return validar_correo(valor)


class RestablecerPasswordRequest(BaseModel):
    """Consumo del enlace: token del correo y contrasena nueva."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=16, max_length=200)
    password: str = Field(min_length=8, max_length=LONGITUD_MAXIMA)

    @field_validator("token")
    @classmethod
    def _validar_token(cls, valor: str) -> str:
        limpio = valor.strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,200}", limpio):
            raise ValueError("El enlace de recuperacion no es valido")
        return limpio

    @field_validator("password")
    @classmethod
    def _validar_password(cls, valor: str) -> str:
        try:
            validar_fortaleza(valor)
        except PasswordInvalida as exc:
            raise ValueError(str(exc)) from exc
        return valor


class RolSalida(BaseModel):
    id_rol: int
    nombre: str
    descripcion: str | None = None
    protegido: bool = False
    usuarios_asignados: int = 0
    permisos: list[str] = Field(default_factory=list)


class PermisoSalida(BaseModel):
    clave: str
    nombre: str
    descripcion: str
    orden: int


class RolCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=2, max_length=50)
    descripcion: str = Field(default="", max_length=255)
    permisos: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("nombre")
    @classmethod
    def _validar_nombre_rol(cls, valor: str) -> str:
        return validar_rol(valor)

    @field_validator("descripcion")
    @classmethod
    def _limpiar_descripcion(cls, valor: str) -> str:
        return " ".join(valor.split())

    @field_validator("permisos")
    @classmethod
    def _validar_permisos(cls, valor: list[str]) -> list[str]:
        return validar_capacidades(valor)


class RolConfiguracionActualizar(RolCrear):
    pass
