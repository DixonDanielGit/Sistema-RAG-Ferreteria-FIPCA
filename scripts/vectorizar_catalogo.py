"""Vectoriza productos pendientes de forma manual y por lotes.

Uso:
    venv\\Scripts\\python.exe scripts\\vectorizar_catalogo.py --lote 10
    venv\\Scripts\\python.exe scripts\\vectorizar_catalogo.py --todos
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.services.vector_search import (
    MAX_PRODUCTOS_POR_LOTE,
    vectorizar_productos_pendientes,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lote",
        type=int,
        default=25,
        help=f"Productos por lote (1-{MAX_PRODUCTOS_POR_LOTE}; por defecto: 25)",
    )
    parser.add_argument(
        "--todos",
        action="store_true",
        help="Procesa paginas hasta que no queden productos pendientes",
    )
    argumentos = parser.parse_args()

    while True:
        resultado = vectorizar_productos_pendientes(argumentos.lote)
        print(
            "Encontrados: {encontrados}; vectorizados: {actualizados}".format(
                **resultado
            )
        )
        if not argumentos.todos or resultado["encontrados"] == 0:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
