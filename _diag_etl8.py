from __future__ import annotations
import sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from app.services import etl_service as e

for nombre in ("FFMJ .pdf", "3JGT CONEXIONES DE RIEGO 2026.pdf"):
    ruta = RAIZ / "catalogos_de_prueba" / nombre
    productos, errores, _ = e._extraer(ruta.name, ruta.read_bytes())
    grupos = {}
    for p in productos:
        grupos.setdefault(p["codigo"], []).append(p)
    print("=" * 70)
    print(nombre, "total", len(productos), "codigos unicos", len(grupos))
    n = 0
    for codigo, grupo in grupos.items():
        if len(grupo) > 1:
            n += 1
            print(f"  {codigo}: {len(grupo)} variantes")
            for p in grupo[:4]:
                print("     ", p["nombre"][:60], "|", p["precio"], "|", (p["descripcion"] or "")[:40])
            if n >= 12:
                break
