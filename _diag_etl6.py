from __future__ import annotations
import sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from openpyxl import load_workbook
from app.services import etl_service as e

ruta = RAIZ / "catalogos_de_prueba" / "2025 CALCULO DE PESOS ACEROS LAMINADOS.xlsx"
libro = load_workbook(ruta, read_only=True, data_only=True)
hoja = libro["FERRET. IMPORTADO"]
filas = list(hoja.iter_rows(values_only=True))
for j, f in enumerate(filas[:20]):
    print(j, [str(v)[:24] if v is not None else None for v in f][:10])
print("...")
for j, f in enumerate(filas[20:26], start=20):
    print(j, [str(v)[:24] if v is not None else None for v in f][:10])
print("cabecera compuesta 14:", e._mapear_cabecera(e._cabecera_compuesta(filas, 14)))
print("precios fila 14:", e._columnas_precio(filas[14]) if len(filas) > 14 else None)
libro.close()
