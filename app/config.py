"""Configuracion central del sistema.

Toda la configuracion se lee de variables de entorno (.env en desarrollo).
Ningun secreto se escribe en el codigo ni en el repositorio.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent

# No sobrescribe variables ya presentes en el entorno: en pruebas se puede
# apuntar a otras bases definiendo las variables antes de importar el modulo.
load_dotenv(RAIZ_PROYECTO / ".env")


def _entero(nombre: str, defecto: int) -> int:
    valor = os.getenv(nombre)
    if valor is None or not valor.strip():
        return defecto
    try:
        return int(valor)
    except ValueError as exc:
        raise ValueError(f"{nombre} debe ser un numero entero, no '{valor}'") from exc


def _booleano(nombre: str, defecto: bool = False) -> bool:
    valor = os.getenv(nombre)
    if valor is None:
        return defecto
    return valor.strip().lower() in {"1", "true", "si", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Valores de configuracion inmutables de la aplicacion."""

    nombre: str = "Sistema de Inventario e IA RAG"
    empresa: str = "FERRE-INVERSIONES PEREZ C.A."
    version: str = "0.2.0"
    entorno: str = field(default_factory=lambda: os.getenv("ENTORNO", "desarrollo").strip().lower())

    # Base de datos
    database_url_rag: str = field(default_factory=lambda: os.getenv("DATABASE_URL_RAG", ""))
    database_url_usuarios: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL_USUARIOS", "")
    )
    admin_database_url: str = field(default_factory=lambda: os.getenv("ADMIN_DATABASE_URL", ""))
    db_pool_minimo: int = field(default_factory=lambda: _entero("DB_POOL_MINIMO", 1))
    db_pool_maximo: int = field(default_factory=lambda: _entero("DB_POOL_MAXIMO", 5))

    # JWT
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", ""))
    jwt_algoritmo: str = field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))
    jwt_expiracion_minutos: int = field(
        default_factory=lambda: _entero("JWT_EXPIRACION_MINUTOS", 30)
    )
    jwt_emisor: str = field(default_factory=lambda: os.getenv("JWT_EMISOR", "ferreteria-fipca"))

    # Red
    cors_origenes: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origen.strip()
            for origen in os.getenv("CORS_ORIGENES", "").split(",")
            if origen.strip()
        )
    )
    confiar_en_proxy: bool = field(default_factory=lambda: _booleano("CONFIAR_EN_PROXY", False))

    @property
    def es_produccion(self) -> bool:
        return self.entorno == "produccion"

    def validar(self) -> None:
        """Comprueba que la configuracion critica este completa.

        En produccion los valores de ejemplo o vacios son un error fatal:
        arrancar con una clave JWT por defecto permitiria falsificar tokens.
        """
        problemas: list[str] = []

        if not self.database_url_usuarios.strip():
            problemas.append("Falta DATABASE_URL_USUARIOS")
        if not self.database_url_rag.strip():
            problemas.append("Falta DATABASE_URL_RAG")

        secreto = self.jwt_secret.strip()
        if not secreto:
            problemas.append("Falta JWT_SECRET")
        elif len(secreto) < 32:
            problemas.append("JWT_SECRET debe tener al menos 32 caracteres")
        elif self.es_produccion and secreto.startswith("cambia_esta_clave"):
            problemas.append("JWT_SECRET sigue siendo el valor de ejemplo")

        if self.jwt_expiracion_minutos <= 0:
            problemas.append("JWT_EXPIRACION_MINUTOS debe ser mayor que cero")

        if self.jwt_algoritmo not in {"HS256", "HS384", "HS512"}:
            problemas.append(
                f"JWT_ALGORITHM '{self.jwt_algoritmo}' no permitido; use HS256/HS384/HS512"
            )

        if problemas:
            raise ValueError("Configuracion invalida: " + "; ".join(problemas))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la configuracion (cacheada) de la aplicacion."""
    return Settings()
