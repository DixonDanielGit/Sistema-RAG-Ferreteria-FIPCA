"""Diagnostico temporal 5: estructura del XLSX de prueba."""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from openpyxl import load_workbook
from app.services import etl_service as e

ruta = RAIZ / "catalogos_de_prueba" / "2025 CALCULO DE PESOS ACEROS LAMINADOS.xlsx"
libro = load_workbook(io_bytes := ruta.read_bytes(), read_only=True, data_only=True) if False else load_workbook(ruta, read_only=True, data_only=True)
for i, hoja in enumerate(libro.worksheets):
    filas = list(hoja.iter_rows(values_only=True))
    no_vacias = [f for f in filas if any(v is not None and str(v).strip() for v in f)]
    print("=" * 60)
    print(f"HOJA {i}: {hoja.title!r} filas={len(filas)} no_vacias={len(no_vacias)}")
    for f in filas[:8]:
        print("   ", [str(v)[:28] if v is not None else None for v in f][:12])
    cabecera = next((j for j, f in enumerate(filas[:100]) if e._mapear_cabecera(f)), None)
    print("   indice cabecera:", cabecera)
    if cabecera is not None:
        print("   columnas:", e._mapear_cabecera(filas[cabecera]))
        print("   columnas precio:", e._columnas_precio(filas[cabecera]))
libro.close()
