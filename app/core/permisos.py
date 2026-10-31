"""Capacidades conocidas por la aplicacion y validacion de asignaciones."""

from __future__ import annotations

CAPACIDADES: tuple[dict[str, str | int], ...] = (
    {
        "clave": "usuarios:gestionar",
        "nombre": "Gestionar usuarios",
        "descripcion": "Consultar y administrar cuentas del sistema.",
        "orden": 10,
    },
    {
        "clave": "catalogos:ingestar",
        "nombre": "Cargar catalogos",
        "descripcion": "Cargar catalogos de productos y consultar su procesamiento.",
        "orden": 20,
    },
    {
        "clave": "catalogos:eliminar",
        "nombre": "Eliminar catalogos",
        "descripcion": "Eliminar catalogos y los productos que contienen.",
        "orden": 30,
    },
    {
        "clave": "configuracion:diagnostico",
        "nombre": "Consultar diagnostico",
        "descripcion": "Consultar estado de bases de datos y limites tecnicos.",
        "orden": 40,
    },
)

CLAVES_CAPACIDADES = frozenset(str(item["clave"]) for item in CAPACIDADES)


def validar_capacidades(valores: list[str]) -> list[str]:
    """Rechaza permisos desconocidos y elimina repeticiones."""
    resultado = list(dict.fromkeys(valores))
    desconocidos = sorted(set(resultado) - CLAVES_CAPACIDADES)
    if desconocidos:
        raise ValueError(f"Capacidades no admitidas: {', '.join(desconocidos)}")
    return resultado
