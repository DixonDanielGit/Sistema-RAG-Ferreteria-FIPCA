from __future__ import annotations
import sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from pypdf import PdfReader

ruta = RAIZ / "catalogos_de_prueba" / "FFMJ .pdf"
lector = PdfReader(str(ruta))
for i, pagina in enumerate(lector.pages, start=1):
    texto = pagina.extract_text() or ""
    if "E0600000030" in texto:
        print("=" * 60, "pagina", i)
        for linea in texto.splitlines():
            print(repr(linea[:110]))
        break
