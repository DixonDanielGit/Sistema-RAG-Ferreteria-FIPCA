"""Diagnostico temporal 4: cuantifica productos reales vs extraidos por columna."""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from pypdf import PdfReader

patron_codigo = re.compile(r"^[A-Z]{1,4}[0-9][A-Z0-9./-]*$")
patron_precio = re.compile(r"^\d{1,3}(?:[.,]\d{1,2})?$")

for ruta in sorted((RAIZ / "catalogos_de_prueba").glob("*.pdf")):
    lector = PdfReader(str(ruta))
    total_real = 0
    for pagina in lector.pages:
        frags = []
        def recoger(texto, _m, pos, _f, _t):
            if texto.strip():
                frags.append((float(pos[4]), float(pos[5]), texto.strip()))
        pagina.extract_text(visitor_text=recoger)
        # agrupar por y y contar "bloques" (codigo+desc+precio) por banda de x
        lineas = {}
        for x, y, t in frags:
            clave = round(y / 1.5)
            lineas.setdefault(clave, []).append((x, t))
        for y, partes in lineas.items():
            partes.sort()
            codigos = [t for x, t in partes if patron_codigo.match(t)]
            precios = [t for x, t in partes if patron_precio.match(t) and x > pagina.mediabox.width * 0.35]
            total_real += min(len(codigos), len(precios)) if codigos and precios else 0
    print(f"{ruta.name}: productos_reales~{total_real}")
