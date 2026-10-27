"""Hashing y verificacion de contrasenas (RNF-02.1).

Se usa ``scrypt`` de la biblioteca estandar: es un KDF con costo de memoria
disenado para resistir ataques con GPU y no depende de librerias externas que
puedan quedar sin mantenimiento.

Formato del hash almacenado::

    scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>

Incluir los parametros dentro del propio hash permite subir el costo en el
futuro sin invalidar las contrasenas existentes: al iniciar sesion se detecta
el formato antiguo y se re-genera el hash (ver ``necesita_rehash``).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from functools import lru_cache

# Parametros de costo. n=2**14 y r=8 usan 16 MiB de RAM por verificacion,
# lo que tarda ~50-100 ms en hardware domestico: imperceptible al entrar,
# prohibitivo para un atacante que pruebe millones de claves.
N = 2**14
R = 8
P = 1
DKLEN = 64
SAL_LONGITUD = 16

PREFIJO = "scrypt"

LONGITUD_MINIMA = 8
LONGITUD_MAXIMA = 128


class PasswordInvalida(ValueError):
    """La contrasena no cumple la politica minima de seguridad."""


def _b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode("ascii")


def _unb64(texto: str) -> bytes:
    return base64.b64decode(texto.encode("ascii"), validate=True)


def _derivar(password: str, sal: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=sal,
        n=n,
        r=r,
        p=p,
        dklen=dklen,
        maxmem=128 * n * r * 2,
    )


def validar_fortaleza(password: str) -> None:
    """Aplica la politica de contrasenas.

    Se exige longitud y variedad de caracteres, no reglas arbitrarias de
    mayusculas: la longitud es lo que realmente encarece un ataque.
    """
    if not isinstance(password, str):
        raise PasswordInvalida("La contrasena debe ser texto")

    if len(password) < LONGITUD_MINIMA:
        raise PasswordInvalida(
            f"La contrasena debe tener al menos {LONGITUD_MINIMA} caracteres"
        )

    if len(password) > LONGITUD_MAXIMA:
        raise PasswordInvalida(
            f"La contrasena no puede superar {LONGITUD_MAXIMA} caracteres"
        )

    if password.strip() != password:
        raise PasswordInvalida("La contrasena no puede empezar ni terminar con espacios")

    if password.strip() == "":
        raise PasswordInvalida("La contrasena no puede estar vacia")

    tiene_letra = any(c.isalpha() for c in password)
    tiene_digito = any(c.isdigit() for c in password)

    if not tiene_letra or not tiene_digito:
        raise PasswordInvalida("La contrasena debe combinar letras y numeros")


def hash_password(password: str) -> str:
    """Genera un hash scrypt con sal aleatoria.

    Cada llamada produce un valor distinto aunque la contrasena se repita.
    """
    validar_fortaleza(password)
    sal = secrets.token_bytes(SAL_LONGITUD)
    derivado = _derivar(password, sal, N, R, P, DKLEN)
    return f"{PREFIJO}${N}${R}${P}${_b64(sal)}${_b64(derivado)}"


def _parsear(hash_guardado: str) -> tuple[int, int, int, bytes, bytes] | None:
    """Separa un hash almacenado en sus componentes. None si es invalido."""
    if not isinstance(hash_guardado, str):
        return None

    partes = hash_guardado.split("$")
    if len(partes) != 6 or partes[0] != PREFIJO:
        return None

    try:
        n, r, p = int(partes[1]), int(partes[2]), int(partes[3])
        sal = _unb64(partes[4])
        derivado = _unb64(partes[5])
    except (ValueError, TypeError):
        return None

    if n < 2 or r < 1 or p < 1 or not sal or not derivado:
        return None

    # Limites defensivos: un hash manipulado con parametros enormes agotaria
    # la memoria del servidor (DoS). Los valores legitimos caben de sobra.
    if n > 2**20 or n & (n - 1) or r > 32 or p > 16 or len(derivado) > 128:
        return None

    return n, r, p, sal, derivado


def verify_password(password: str, hash_guardado: str) -> bool:
    """Comprueba una contrasena contra su hash.

    Nunca lanza excepcion por datos corruptos: devuelve False. Se usa
    comparacion en tiempo constante para no filtrar informacion por latencia.
    """
    if not isinstance(password, str) or not password:
        return False

    if len(password) > LONGITUD_MAXIMA:
        return False

    partes = _parsear(hash_guardado)
    if partes is None:
        return False

    n, r, p, sal, derivado_guardado = partes

    try:
        derivado = _derivar(password, sal, n, r, p, len(derivado_guardado))
    except (ValueError, MemoryError):
        # Parametros absurdos en la base (posible manipulacion): se rechaza.
        return False

    return hmac.compare_digest(derivado, derivado_guardado)


def necesita_rehash(hash_guardado: str) -> bool:
    """Indica si un hash valido usa parametros distintos a los actuales."""
    partes = _parsear(hash_guardado)
    if partes is None:
        return True

    n, r, p, _, derivado = partes
    return (n, r, p, len(derivado)) != (N, R, P, DKLEN)


def gastar_tiempo_como_si_existiera(password: str) -> None:
    """Verifica contra un hash ficticio para igualar la latencia del login.

    Se invoca cuando el usuario no existe, de modo que la respuesta tarde lo
    mismo que con una cuenta real y no se pueda deducir que usuarios existen.
    """
    verify_password(password, _hash_ficticio())


@lru_cache(maxsize=1)
def _hash_ficticio() -> str:
    """Hash real de una contrasena descartada (se calcula una sola vez)."""
    return hash_password("contrasena-ficticia-para-igualar-tiempos-0")


# ---------------------------------------------------------------------------
# Tokens de un solo uso (recuperacion de contrasena, Adenda 1)
# ---------------------------------------------------------------------------

TOKEN_RECUPERACION_BYTES = 32


def hash_token(token: str) -> str:
    """SHA-256 en hexadecimal del token.

    Es lo unico que se guarda en la base: si alguien copia la tabla no puede
    reutilizar los enlaces. No se usa scrypt aqui a proposito: el token ya es
    aleatorio de 256 bits, no requiere un KDF lento.
    """
    if not token or not isinstance(token, str):
        raise ValueError("El token no puede estar vacio")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generar_token_recuperacion() -> tuple[str, str]:
    """Devuelve ``(token_crudo, sha256)``.

    El token crudo viaja una sola vez, dentro del enlace del correo. En la
    base queda unicamente su hash.
    """
    token = secrets.token_urlsafe(TOKEN_RECUPERACION_BYTES)
    return token, hash_token(token)


def tokens_coinciden(primero: str, segundo: str) -> bool:
    """Comparacion en tiempo constante (evita filtrar informacion por tiempo)."""
    return hmac.compare_digest(primero.encode("utf-8"), segundo.encode("utf-8"))


def generar_token_csrf() -> str:
    """Token anti-CSRF para los formularios de la interfaz web."""
    return secrets.token_urlsafe(32)
