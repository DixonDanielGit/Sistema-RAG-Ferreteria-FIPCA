from __future__ import annotations
import sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from openpyxl import load_workbook
from app.services import etl_service as e

ruta = RAIZ / "catalogos_de_prueba" / "2025 CALCULO DE PESOS ACEROS LAMINADOS.xlsx"
libro = load_workbook(ruta, read_only=True, data_only=True)
for i, hoja in enumerate(libro.worksheets):
    filas = list(hoja.iter_rows(values_only=True))
    simple = next(((j, e._mapear_cabecera(f)) for j, f in enumerate(filas[:100]) if e._mapear_cabecera(f)), None)
    compuesta = next(
        (
            (j, e._mapear_cabecera(c))
            for j in range(min(100, len(filas)))
            for c in [e._cabecera_compuesta(filas, j)]
            if e._mapear_cabecera(c)
        ),
        None,
    )
    print("=" * 66)
    print(f"HOJA {i} {hoja.title!r} filas={len(filas)}")
    print("  cabecera simple:", simple)
    print("  cabecera compuesta:", compuesta)
    if compuesta:
        j, cols = compuesta
        precios = e._columnas_precio(e._cabecera_compuesta(filas, j))
        print("  columnas precio compuesta:", precios, "-> cols:", cols)
        try:
            prods, err, det = e._extraer_filas(filas, precio_indice=(precios[0] if precios else None), columnas_forzadas=cols, indice_cabecera_forzado=j)
            print(f"  extraidos={len(prods)} errores={err}")
            for d in det[:6]:
                print("    ", d[:150])
            # cuantas filas con datos quedan despues de la cabecera
            resto = [f for f in filas[j+1:] if any(v is not None and str(v).strip() for v in f)]
            print(f"  filas con datos tras cabecera={len(resto)}  -> perdidas={len(resto)-len(prods)-err}")
        except Exception as exc:
            print("  ERROR:", type(exc).__name__, exc)
    else:
        # cuantas filas con datos tiene la hoja
        resto = [f for f in filas if any(v is not None and str(v).strip() for v in f)]
        print(f"  SIN CABECERA -> hoja omitida por completo ({len(resto)} filas con datos)")
libro.close()
