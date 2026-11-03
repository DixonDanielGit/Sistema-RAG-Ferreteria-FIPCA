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

from app.models import inventario as inventario_model
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

    antes = inventario_model.contar_productos_sin_embedding()
    print(f"Pendientes al iniciar: {antes}")

    total = 0
    sin_avance = 0
    while True:
        resultado = vectorizar_productos_pendientes(argumentos.lote)
        total += resultado["actualizados"]
        print(
            "Encontrados: {encontrados}; vectorizados: {actualizados}".format(
                **resultado
            )
        )
        if resultado["encontrados"] == 0:
            break
        if resultado["actualizados"] == 0:
            # Otra sesion pudo vectorizar esas filas o la escritura no aplico.
            # Sin esta guarda, --todos repetiria el mismo lote para siempre.
            sin_avance += 1
            if sin_avance >= 2:
                print(
                    "No se pudo vectorizar ninguna fila en dos intentos; "
                    "se detiene para no repetir el mismo lote.",
                    file=sys.stderr,
                )
                break
        else:
            sin_avance = 0
        if not argumentos.todos:
            break

    pendientes = inventario_model.contar_productos_sin_embedding()
    print(f"Vectorizados en esta ejecucion: {total}")
    print(f"Pendientes al terminar: {pendientes}")
    if pendientes:
        print(
            "Aun quedan productos sin vector: la busqueda semantica no los "
            "devolvera. Ejecute de nuevo con --todos hasta llegar a 0.",
            file=sys.stderr,
        )
        return 1 if argumentos.todos else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
