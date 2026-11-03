"""Diagnostico temporal: compara filas del archivo contra filas extraidas."""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from app.services import etl_service as e

carpeta = RAIZ / "catalogos_de_prueba"
for ruta in sorted(carpeta.iterdir()):
    contenido = ruta.read_bytes()
    print("=" * 70)
    print(f"ARCHIVO: {ruta.name} ({len(contenido)/1024/1024:.2f} MB)")
    try:
        productos, errores, detalles = e._extraer(ruta.name, contenido)
        print(f"  extraidos: {len(productos)}  errores: {errores}")
        unicos, duplicadas, err_dup, det_dup = e._consolidar_codigos(productos)
        print(f"  tras consolidar: {len(unicos)}  duplicadas: {duplicadas}  "
              f"descartadas por conflicto: {err_dup}")
        for d in detalles[:15]:
            print("   detalle:", d[:180])
        for d in det_dup[:8]:
            print("   dup:", d[:180])
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR: {type(exc).__name__}: {exc}")
