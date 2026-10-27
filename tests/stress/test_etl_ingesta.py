"""Prueba reducida del flujo HTTP de ingesta (20 archivos / 5000 productos).

Ejecucion explicita:
    PowerShell: $env:PRUEBA_ESTRES='1'; venv\\Scripts\\python.exe -m pytest tests\\stress -q -s
"""

from __future__ import annotations

import os
import time
import uuid

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("PRUEBA_ESTRES") != "1",
    reason="Defina PRUEBA_ESTRES=1 para ejecutar la prueba reducida de carga",
)


def test_20_catalogos_ingresan_5000_productos_en_425_segundos(
    cliente, crear_cuenta, token_de, conexion_rag_limpieza
):
    with conexion_rag_limpieza.cursor() as cursor:
        cursor.execute("TRUNCATE productos, archivos_subidos RESTART IDENTITY CASCADE")

    cuenta = crear_cuenta(usuario="admin_estres")
    token = token_de(cuenta)
    prefijo = uuid.uuid4().hex[:12]
    archivos = []
    for archivo in range(20):
        lineas = ["codigo;nombre;precio"]
        for producto in range(250):
            numero = archivo * 250 + producto
            lineas.append(f"{prefijo}-{numero};Producto {numero};1,25")
        contenido = ("\n".join(lineas) + "\n").encode("utf-8")
        archivos.append(
            ("archivos", (f"catalogo-{archivo}.txt", contenido, "text/plain"))
        )

    inicio = time.perf_counter()
    respuesta = cliente.post(
        "/api/v1/inventario/ingesta",
        files=archivos,
        headers={"Authorization": f"Bearer {token}"},
    )
    duracion = time.perf_counter() - inicio

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["total_archivos"] == 20
    assert cuerpo["archivos_ok"] == 20
    assert sum(archivo["filas_ok"] for archivo in cuerpo["resultados"]) == 5_000
    assert duracion < 4.25, f"La ingesta tardo {duracion:.2f} s (maximo: 4.25 s)"

    with conexion_rag_limpieza.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM productos WHERE codigo LIKE %s",
            (f"{prefijo.upper()}-%",),
        )
        assert cursor.fetchone()[0] == 5_000
