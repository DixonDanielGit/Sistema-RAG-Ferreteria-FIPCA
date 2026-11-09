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


def _booleano_opcional(nombre: str) -> bool | None:
    """Como ``_booleano`` pero distingue "sin definir" de "false"."""
    valor = os.getenv(nombre)
    if valor is None or not valor.strip():
        return None
    return valor.strip().lower() in {"1", "true", "si", "yes", "on"}


def _directorio_cargas() -> Path:
    valor = os.getenv("UPLOADS_DIR", "").strip()
    ruta = Path(valor).expanduser() if valor else Path("uploads")
    return ruta if ruta.is_absolute() else RAIZ_PROYECTO / ruta


@dataclass(frozen=True)
class Settings:
    """Valores de configuracion inmutables de la aplicacion."""

    nombre: str = "Sistema de Inventario e IA RAG"
    empresa: str = "FERRE-INVERSIONES PEREZ C.A."
    version: str = "0.4.0 Beta Experimental"
    desarrollador: str = "Dixon Bastias"
    desarrollador_github: str = "DixonDanielGit"
    entorno: str = field(default_factory=lambda: os.getenv("ENTORNO", "desarrollo").strip().lower())

    # Base de datos
    database_url_rag: str = field(default_factory=lambda: os.getenv("DATABASE_URL_RAG", ""))
    database_url_usuarios: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL_USUARIOS", "")
    )
    admin_database_url: str = field(default_factory=lambda: os.getenv("ADMIN_DATABASE_URL", ""))
    db_pool_minimo: int = field(default_factory=lambda: _entero("DB_POOL_MINIMO", 1))
    db_pool_maximo: int = field(default_factory=lambda: _entero("DB_POOL_MAXIMO", 5))
    uploads_dir: Path = field(default_factory=_directorio_cargas)
    embedding_cache_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("EMBEDDING_CACHE_DIR", ".cache/embeddings")
        ).expanduser()
    )
    # Vectorizacion del catalogo (Semana 4). Con la activacion por defecto,
    # cada ingesta exitosa lanza en segundo plano la indexacion de los
    # productos nuevos y el panel de fuentes baja solo a 0 pendientes. Con
    # VECTORIZACION_AUTOMATICA=0 se conserva el flujo manual del script
    # scripts/vectorizar_catalogo.py.
    vectorizacion_automatica: bool = field(
        default_factory=lambda: _booleano("VECTORIZACION_AUTOMATICA", True)
    )

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

    # Interfaz web (Adenda 1): la sesion viaja en cookie HttpOnly y los POST
    # exigen un token CSRF adicional.
    url_base: str = field(
        default_factory=lambda: os.getenv("URL_BASE", "http://localhost:8000").strip().rstrip("/")
    )
    cookie_nombre: str = field(
        default_factory=lambda: os.getenv("COOKIE_NOMBRE", "access_token").strip()
    )
    cookie_csrf: str = field(
        default_factory=lambda: os.getenv("COOKIE_CSRF", "csrf_token").strip()
    )
    cookie_segura_env: bool | None = field(
        default_factory=lambda: _booleano_opcional("COOKIE_SEGURA")
    )

    # Recuperacion de contrasena (Adenda 1)
    recuperacion_minutos: int = field(
        default_factory=lambda: _entero("RECUPERACION_MINUTOS", 30)
    )
    recuperacion_max_intentos: int = field(
        default_factory=lambda: _entero("RECUPERACION_MAX_INTENTOS", 5)
    )
    recuperacion_ventana_minutos: int = field(
        default_factory=lambda: _entero("RECUPERACION_VENTANA_MINUTOS", 15)
    )

    # Correo saliente (smtplib). Sin SMTP configurado el enlace se escribe en
    # el log del proceso (modo consola), suficiente para desarrollo y pruebas.
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", "").strip())
    smtp_puerto: int = field(default_factory=lambda: _entero("SMTP_PUERTO", 587))
    smtp_usuario: str = field(default_factory=lambda: os.getenv("SMTP_USUARIO", "").strip())
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    smtp_remitente: str = field(
        default_factory=lambda: os.getenv("SMTP_REMITENTE", "").strip()
    )
    smtp_tls: bool = field(default_factory=lambda: _booleano("SMTP_TLS", True))

    # Proveedor de lenguaje del asistente (Semana 4). Cualquier API compatible
    # con POST /chat/completions de OpenAI; para un modelo local (Ollama, LM
    # Studio) basta apuntar LLM_BASE_URL a su endpoint /v1. Sin las tres
    # variables el asistente no envia solicitudes al proveedor.
    llm_base_url: str = field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    )
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", "").strip())
    llm_modelo: str = field(default_factory=lambda: os.getenv("LLM_MODELO", "").strip())
    llm_timeout_segundos: int = field(
        default_factory=lambda: _entero("LLM_TIMEOUT_SEGUNDOS", 30)
    )
    llm_max_tokens: int = field(default_factory=lambda: _entero("LLM_MAX_TOKENS", 500))

    # Transformacion de catalogos Markdown. Se mantiene separada del proveedor
    # configurable del chat: esta etapa solo admite modelos gratuitos de OpenRouter.
    openrouter_api_key: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "").strip()
    )
    openrouter_base_url: str = field(
        default_factory=lambda: os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ).strip().rstrip("/")
    )
    openrouter_model: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_MODEL", "").strip()
    )
    openrouter_timeout_segundos: int = field(
        default_factory=lambda: _entero("OPENROUTER_TIMEOUT_SEGUNDOS", 60)
    )

    @property
    def es_produccion(self) -> bool:
        return self.entorno == "produccion"

    @property
    def smtp_configurado(self) -> bool:
        """True cuando hay un servidor de correo utilizable."""
        return bool(self.smtp_host and self.smtp_remitente)

    @property
    def llm_configurado(self) -> bool:
        """True cuando el proveedor de lenguaje tiene endpoint, clave y modelo."""
        return bool(self.llm_base_url and self.llm_api_key and self.llm_modelo)

    @property
    def openrouter_configurado(self) -> bool:
        """True cuando OpenRouter tiene URL, clave y modelo definidos."""
        return bool(
            self.openrouter_base_url
            and self.openrouter_api_key
            and self.openrouter_model
        )

    @property
    def cookie_segura(self) -> bool:
        """En produccion la cookie solo viaja por HTTPS.

        Se puede forzar con COOKIE_SEGURA=true/false para escenarios concretos
        (por ejemplo, una prueba local con proxy TLS).
        """
        if self.cookie_segura_env is not None:
            return self.cookie_segura_env
        return self.es_produccion

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

        if self.recuperacion_minutos <= 0:
            problemas.append("RECUPERACION_MINUTOS debe ser mayor que cero")
        elif self.recuperacion_minutos > 24 * 60:
            problemas.append("RECUPERACION_MINUTOS no puede superar 1440 (24 horas)")

        if self.recuperacion_max_intentos <= 0:
            problemas.append("RECUPERACION_MAX_INTENTOS debe ser mayor que cero")
        if self.recuperacion_ventana_minutos <= 0:
            problemas.append("RECUPERACION_VENTANA_MINUTOS debe ser mayor que cero")

        if not self.url_base.startswith(("http://", "https://")):
            problemas.append("URL_BASE debe empezar por http:// o https://")

        if not self.cookie_nombre.strip():
            problemas.append("COOKIE_NOMBRE no puede estar vacio")

        if self.llm_base_url and not self.llm_base_url.startswith(
            ("http://", "https://")
        ):
            problemas.append("LLM_BASE_URL debe empezar por http:// o https://")
        if self.es_produccion and self.llm_base_url.startswith("http://"):
            problemas.append(
                "LLM_BASE_URL debe usar https en produccion: la clave viaja en "
                "cada solicitud"
            )
        if any((self.llm_base_url, self.llm_api_key, self.llm_modelo)) and not (
            self.llm_configurado
        ):
            problemas.append(
                "Configuracion LLM incompleta: defina LLM_BASE_URL, LLM_API_KEY "
                "y LLM_MODELO, o deje las tres vacias"
            )
        if self.llm_timeout_segundos <= 0:
            problemas.append("LLM_TIMEOUT_SEGUNDOS debe ser mayor que cero")
        if self.llm_max_tokens <= 0:
            problemas.append("LLM_MAX_TOKENS debe ser mayor que cero")

        if problemas:
            raise ValueError("Configuracion invalida: " + "; ".join(problemas))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la configuracion (cacheada) de la aplicacion."""
    return Settings()
