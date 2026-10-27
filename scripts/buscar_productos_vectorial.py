"""Prueba una consulta semantica contra productos ya vectorizados.

Uso:
    venv\\Scripts\\python.exe scripts\\buscar_productos_vectorial.py "taladro para concreto"
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.services.vector_search import buscar_productos


def _serializar(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return str(valor)
    raise TypeError(f"Tipo no serializable: {type(valor).__name__}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pregunta", help="Consulta de productos en lenguaje natural")
    parser.add_argument("--limite", type=int, default=5)
    argumentos = parser.parse_args()

    resultados = buscar_productos(argumentos.pregunta, argumentos.limite)
    print(json.dumps(resultados, ensure_ascii=False, indent=2, default=_serializar))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
