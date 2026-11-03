"""Diagnostico temporal 3: inspeccion del layout real de los PDF."""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from pypdf import PdfReader

ruta = RAIZ / "catalogos_de_prueba" / "3JGT CONEXIONES DE RIEGO 2026.pdf"
lector = PdfReader(str(ruta))
for i, pagina in enumerate(lector.pages[:2], start=1):
    print("=" * 40, "PAGINA", i, "ancho", pagina.mediabox.width)
    fragmentos = []
    def recoger(texto, _m, pos, _f, _t):
        if texto.strip():
            fragmentos.append((round(float(pos[4]), 1), round(float(pos[5]), 1), texto.strip()))
    pagina.extract_text(visitor_text=recoger)
    por_linea = {}
    for x, y, t in fragmentos:
        por_linea.setdefault(y, []).append((x, t))
    for y in sorted(por_linea, reverse=True)[:45]:
        partes = sorted(por_linea[y])
        print(f"y={y:7.1f} | " + "  ".join(f"[{x:6.1f}]{t}" for x, t in partes)[:200])
    print("... total lineas:", len(por_linea))
