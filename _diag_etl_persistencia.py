from __future__ import annotations
import sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from app.services import etl_service as e

ruta = RAIZ / "catalogos_de_prueba" / "3JGT CONEXIONES DE RIEGO 2026.pdf"
resultado = e.procesar_archivo(ruta.name, ruta.read_bytes(), 1)
print({k: resultado[k] for k in ("id_archivo", "estado", "filas_ok", "filas_error")})
print("detalle:", (resultado.get("detalle") or "")[:300])

from app.models import inventario as m
id_archivo = resultado["id_archivo"]
print("en base:", m.contar_productos_de_archivo(id_archivo))
print("sin vector:", m.contar_productos_sin_embedding())
print(m.eliminar_catalogo(id_archivo)["productos_eliminados"], "productos eliminados de prueba")
