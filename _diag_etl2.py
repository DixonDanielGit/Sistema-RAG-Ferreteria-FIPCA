"""Diagnostico temporal 2: cuantas filas hay realmente en cada PDF."""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from pypdf import PdfReader
from app.services import etl_service as e

carpeta = RAIZ / "catalogos_de_prueba"
patron_precio = re.compile(r"\bprecio\s*:\s*(.+)$", re.IGNORECASE)
patron_codigo = re.compile(r"\b(?:sku|codigo|c[oó]digo|referencia)\s*:\s*([A-Z0-9][A-Z0-9._/-]{3,})", re.IGNORECASE)

for ruta in sorted(carpeta.glob("*.pdf")):
    contenido = ruta.read_bytes()
    lector = PdfReader(str(ruta), strict=True)
    paginas = [p.extract_text() or "" for p in lector.pages]
    texto = "\n".join(paginas)
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]

    n_codigos = len(patron_codigo.findall(texto))
    n_precios = len(patron_precio.findall(texto))
    # heuristicas espaciales
    esp, esp_err, _ = e._extraer_pdf_espacial(PdfReader(str(ruta), strict=True))
    fic, fic_err, _ = e._extraer_pdf_fichas(PdfReader(str(ruta), strict=True))
    tab, tab_err, _ = e._extraer_pdf_tabla(texto)
    filas = e._filas_pdf(texto)
    gen = []
    if filas:
        try:
            gen, gen_err, _ = e._extraer_filas(filas, permitir_posicional=False)
        except Exception as exc:  # noqa: BLE001
            gen, gen_err = [], 0

    print("=" * 78)
    print(ruta.name, "| paginas:", len(paginas), "| lineas:", len(lineas))
    print(f"  'codigo:' etiquetados={n_codigos}  'precio:' etiquetados={n_precios}")
    print(f"  espacial={len(esp)} (err {esp_err})  fichas={len(fic)} (err {fic_err})  tabla={len(tab)}  generico={len(gen)}")
    print(f"  FINAL _extraer_pdf -> {len(e._extraer_pdf(contenido)[0])}")
    # fragmentos con coordenadas: cuantos textos parecen codigo/precio/nombre
    muestra = [l for l in lineas[:40]]
    print("  muestra texto:", " || ".join(muestra[:6])[:400])
