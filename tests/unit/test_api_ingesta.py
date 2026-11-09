"""Pruebas de caja negra de las rutas HTTP de ingesta."""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import usuario_actual
from app.api.v1 import inventario

# La ingesta se autoriza por capacidad, no por rol fijo: una cuenta puede
# tener `catalogos:ingestar` sin ser administradora (modelo de roles de 6_0).
PERMISOS_ADMIN = ("catalogos:ingestar", "catalogos:eliminar")
METADATOS = {
    "proveedor": "Proveedor de prueba",
    "vendedor": "Vendedora de prueba",
    "moneda": "USD",
}


def _datos_metadatos(*registros):
    return {"metadatos_catalogo": json.dumps(list(registros or [METADATOS]))}


def _app(usuario=None):
    aplicacion = FastAPI()
    aplicacion.include_router(inventario.router, prefix="/api/v1")

    def autorizar():
        return usuario or {"id": 9, "rol": "admin", "permisos": list(PERMISOS_ADMIN)}

    aplicacion.dependency_overrides[usuario_actual] = autorizar
    return aplicacion


def test_admin_carga_lote_y_recibe_resultado_por_archivo(monkeypatch):
    llamadas = []

    def procesar(nombre, contenido, id_usuario, selecciones, metadatos):
        llamadas.append((nombre, contenido, id_usuario, metadatos))
        return {
            "id_archivo": len(llamadas),
            "nombre": nombre,
            "tipo": nombre.rsplit(".", 1)[-1],
            "tamano_bytes": len(contenido),
            "estado": "ok" if nombre.endswith(".txt") else "rechazado",
            "filas_ok": 1 if nombre.endswith(".txt") else 0,
            "filas_error": 0,
            "detalle": None,
            "respuesta_ia": (
                {
                    "productos": [
                        {
                            "codigo": "SKU-1",
                            "nombre": "Martillo",
                            "precio": "1.25",
                        }
                    ]
                }
                if nombre.endswith(".txt")
                else None
            ),
        }

    monkeypatch.setattr(inventario.etl_service, "procesar_archivo", procesar)
    cliente = TestClient(_app())

    respuesta = cliente.post(
        "/api/v1/inventario/ingesta",
        files=[
            ("archivos", ("catalogo.txt", b"SKU-1;Martillo;1.25", "text/plain")),
            ("archivos", ("datos.csv", b"a,b,c", "text/csv")),
        ],
        data=_datos_metadatos(
            METADATOS,
            {
                "proveedor": "Otro proveedor",
                "vendedor": "Otro vendedor",
                "moneda": "VES",
            },
        ),
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total_archivos"] == 2
    assert cuerpo["archivos_ok"] == 1
    assert cuerpo["archivos_rechazados"] == 1
    assert cuerpo["resultados"][0]["respuesta_ia"]["productos"][0]["codigo"] == "SKU-1"
    assert [llamada[2] for llamada in llamadas] == [9, 9]
    assert [llamada[3]["proveedor"] for llamada in llamadas] == [
        "Proveedor de prueba",
        "Otro proveedor",
    ]


def test_acepta_nombre_de_proveedor_derivado_del_archivo(monkeypatch):
    recibidos = []

    def procesar(nombre, contenido, id_usuario, selecciones, metadatos):
        recibidos.append(metadatos["proveedor"])
        return {
            "id_archivo": 1,
            "nombre": nombre,
            "tipo": "pdf",
            "tamano_bytes": len(contenido),
            "estado": "ok",
            "filas_ok": 1,
            "filas_error": 0,
            "detalle": None,
        }

    monkeypatch.setattr(inventario.etl_service, "procesar_archivo", procesar)
    cliente = TestClient(_app())

    respuesta = cliente.post(
        "/api/v1/inventario/ingesta",
        files=[
            (
                "archivos",
                ("3JGT CONEXIONES DE RIEGO 2026.pdf", b"contenido", "application/pdf"),
            )
        ],
        data=_datos_metadatos(
            {
                **METADATOS,
                "proveedor": "3JGT CONEXIONES DE RIEGO 2026",
            }
        ),
    )

    assert respuesta.status_code == 200
    assert recibidos == ["3JGT CONEXIONES DE RIEGO 2026"]


def test_carga_exige_la_capacidad_de_ingesta(monkeypatch):
    llamada = False

    def procesar(*_):
        nonlocal llamada
        llamada = True

    monkeypatch.setattr(inventario.etl_service, "procesar_archivo", procesar)
    # Puede eliminar catalogos, pero no ingerirlos: la ruta debe rechazarlo.
    cliente = TestClient(
        _app(usuario={"id": 10, "rol": "ventas", "permisos": ["catalogos:eliminar"]})
    )

    respuesta = cliente.post(
        "/api/v1/inventario/ingesta",
        files=[("archivos", ("catalogo.txt", b"data", "text/plain"))],
    )

    assert respuesta.status_code == 403
    assert "permiso" in respuesta.json()["detail"]
    assert not llamada


def test_lote_vacio_y_lote_mayor_a_20_se_rechazan():
    cliente = TestClient(_app())

    vacio = cliente.post("/api/v1/inventario/ingesta")
    demasiados = cliente.post(
        "/api/v1/inventario/ingesta",
        files=[
            ("archivos", (f"{indice}.txt", b"a", "text/plain"))
            for indice in range(21)
        ],
        data=_datos_metadatos(*[METADATOS for _ in range(21)]),
    )

    assert vacio.status_code == 400
    assert demasiados.status_code == 400


def test_cada_archivo_requiere_metadatos_de_proveedor(monkeypatch):
    llamada = False

    def procesar(*_):
        nonlocal llamada
        llamada = True

    monkeypatch.setattr(inventario.etl_service, "procesar_archivo", procesar)
    cliente = TestClient(_app())

    respuesta = cliente.post(
        "/api/v1/inventario/ingesta",
        files=[("archivos", ("catalogo.pdf", b"contenido", "application/pdf"))],
    )

    assert respuesta.status_code == 400
    assert "proveedor" in respuesta.json()["detail"]
    assert not llamada


def test_lista_archivos_consulta_modelo_con_limite(monkeypatch):
    monkeypatch.setattr(inventario.inventario_model, "listar_archivos", lambda limite: [])
    cliente = TestClient(_app(usuario={"id": 10, "rol": "ventas"}))

    respuesta = cliente.get("/api/v1/inventario/archivos?limite=12")

    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_estado_de_vectorizacion_cuenta_pendientes_y_total(monkeypatch):
    monkeypatch.setattr(
        inventario.inventario_model, "contar_productos_sin_embedding", lambda: 7
    )
    monkeypatch.setattr(
        inventario.inventario_model, "contar_productos_catalogo", lambda: 120
    )
    monkeypatch.setattr(inventario.vector_search, "vectorizacion_en_curso", lambda: False)
    cliente = TestClient(_app(usuario={"id": 10, "rol": "ventas"}))

    respuesta = cliente.get("/api/v1/inventario/vectorizacion")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"total": 120, "pendientes": 7, "en_curso": False}


def test_estado_de_vectorizacion_sin_pendientes(monkeypatch):
    monkeypatch.setattr(
        inventario.inventario_model, "contar_productos_sin_embedding", lambda: 0
    )
    monkeypatch.setattr(
        inventario.inventario_model, "contar_productos_catalogo", lambda: 0
    )
    monkeypatch.setattr(inventario.vector_search, "vectorizacion_en_curso", lambda: False)
    cliente = TestClient(_app())

    respuesta = cliente.get("/api/v1/inventario/vectorizacion")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"total": 0, "pendientes": 0, "en_curso": False}


def test_estado_de_vectorizacion_avisa_si_un_lote_esta_corriendo(monkeypatch):
    """El panel necesita distinguir 'faltan 2036' de 'faltan 2036 y ya se
    estan indexando', para no mostrar un conteo viejo ni sondear de mas."""
    monkeypatch.setattr(
        inventario.inventario_model, "contar_productos_sin_embedding", lambda: 5
    )
    monkeypatch.setattr(
        inventario.inventario_model, "contar_productos_catalogo", lambda: 5
    )
    monkeypatch.setattr(inventario.vector_search, "vectorizacion_en_curso", lambda: True)
    cliente = TestClient(_app(usuario={"id": 10, "rol": "ventas"}))

    respuesta = cliente.get("/api/v1/inventario/vectorizacion")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"total": 5, "pendientes": 5, "en_curso": True}


def test_previsualizar_archivo_sin_guardarlo(monkeypatch):
    llamada = {}

    def previsualizar(nombre, contenido, selecciones):
        llamada.update(nombre=nombre, contenido=contenido, selecciones=selecciones)
        return {
            "productos_detectados": 1,
            "filas_error": 0,
            "muestra": [{"codigo": "SKU-1", "nombre": "Martillo", "precio": "2.50"}],
            "detalle": None,
            "seleccion_pendiente": False,
            "opciones_precio": [],
        }

    monkeypatch.setattr(inventario.etl_service, "previsualizar_archivo", previsualizar)
    cliente = TestClient(_app())

    respuesta = cliente.post(
        "/api/v1/inventario/previsualizacion",
        files=[("archivo", ("catalogo.txt", b"contenido", "text/plain"))],
        data={"selecciones_precio": '{"0": 3}'},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["productos_detectados"] == 1
    assert llamada == {
        "nombre": "catalogo.txt",
        "contenido": b"contenido",
        "selecciones": {0: 3},
    }


def test_ingesta_envia_seleccion_de_precio_al_procesador(monkeypatch):
    recibidos = []

    def procesar(nombre, contenido, id_usuario, selecciones, metadatos):
        recibidos.append((nombre, contenido, id_usuario, selecciones, metadatos))
        return {
            "id_archivo": 31,
            "nombre": nombre,
            "tipo": "xlsx",
            "tamano_bytes": len(contenido),
            "estado": "ok",
            "filas_ok": 1,
            "filas_error": 0,
            "detalle": None,
        }

    monkeypatch.setattr(inventario.etl_service, "procesar_archivo", procesar)
    cliente = TestClient(_app())

    respuesta = cliente.post(
        "/api/v1/inventario/ingesta",
        files=[("archivos", ("catalogo.xlsx", b"original", "application/octet-stream"))],
        data={
            "selecciones_precio": '{"0": 7}',
            **_datos_metadatos(),
        },
    )

    assert respuesta.status_code == 200
    assert recibidos == [
        (
            "catalogo.xlsx",
            b"original",
            9,
            {0: 7},
            {
                **METADATOS,
                "telefono_vendedor": None,
                "correo_vendedor": None,
                "nota_proveedor": None,
            },
        )
    ]


def test_ingesta_exitosa_lanza_la_vectorizacion_automatica(monkeypatch):
    """El catalogo recien cargado se indexa solo: el panel no debe quedar
    marcando pendientes hasta que alguien recuerde correr el script."""
    lanzadas = {"n": 0}

    def procesar(nombre, contenido, id_usuario, selecciones, metadatos):
        return {
            "id_archivo": 1,
            "nombre": nombre,
            "tipo": "txt",
            "tamano_bytes": len(contenido),
            "estado": "ok",
            "filas_ok": 1,
            "filas_error": 0,
            "detalle": None,
        }

    monkeypatch.setattr(inventario.etl_service, "procesar_archivo", procesar)
    monkeypatch.setattr(
        inventario.vector_search,
        "lanzar_vectorizacion_automatica",
        lambda: lanzadas.__setitem__("n", lanzadas["n"] + 1) or True,
    )
    cliente = TestClient(_app())

    respuesta = cliente.post(
        "/api/v1/inventario/ingesta",
        files=[("archivos", ("catalogo.txt", b"SKU-1;Martillo;1.25", "text/plain"))],
        data=_datos_metadatos(),
    )

    assert respuesta.status_code == 200
    assert lanzadas["n"] == 1


def test_ingesta_solo_con_errores_no_lanza_vectorizacion(monkeypatch):
    """Nada se guardo: no hay nada que indexar y el bucle no debe arrancar."""
    procesos = {"n": 0}

    def procesar(nombre, contenido, id_usuario, selecciones, metadatos):
        return {
            "id_archivo": 2,
            "nombre": nombre,
            "tipo": "txt",
            "tamano_bytes": len(contenido),
            "estado": "error",
            "filas_ok": 0,
            "filas_error": 1,
            "detalle": "El archivo no tiene productos legibles",
        }

    monkeypatch.setattr(inventario.etl_service, "procesar_archivo", procesar)
    monkeypatch.setattr(
        inventario.vector_search,
        "lanzar_vectorizacion_automatica",
        lambda: procesos.__setitem__("n", procesos["n"] + 1) or True,
    )
    cliente = TestClient(_app())

    respuesta = cliente.post(
        "/api/v1/inventario/ingesta",
        files=[("archivos", ("malo.txt", b"basura", "text/plain"))],
        data=_datos_metadatos(),
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["archivos_error"] == 1
    assert procesos["n"] == 0


def test_ingesta_en_proceso_bloquea_otra_con_409(monkeypatch):
    """La subida automatica es una por una: una segunda peticion concurrente
    no debe colarse (409), ni ejecutar un solo archivo."""

    def procesar(*_):
        raise AssertionError("Nada debe procesarse con la cerradura ocupada")

    monkeypatch.setattr(inventario.etl_service, "procesar_archivo", procesar)
    cliente = TestClient(_app())
    cerradura = inventario._cerradura_ingesta
    cerradura.acquire()
    try:
        respuesta = cliente.post(
            "/api/v1/inventario/ingesta",
            files=[("archivos", ("catalogo.txt", b"codigo;nombre;precio", "text/plain"))],
            data=_datos_metadatos(),
        )
    finally:
        cerradura.release()

    assert respuesta.status_code == 409
    assert "carga de catalogo" in respuesta.json()["detail"]


def test_cerradura_se_libera_tras_fallo_del_proceso(monkeypatch):
    def procesar(*_):
        raise ValueError("fallo inesperado")

    monkeypatch.setattr(inventario.etl_service, "procesar_archivo", procesar)
    cliente = TestClient(_app(), raise_server_exceptions=False)

    fallida = cliente.post(
        "/api/v1/inventario/ingesta",
        files=[("archivos", ("malo.txt", b"x", "text/plain"))],
        data=_datos_metadatos(),
    )

    assert fallida.status_code == 500
    assert not inventario._cerradura_ingesta.locked()

    monkeypatch.setattr(
        inventario.etl_service,
        "procesar_archivo",
        lambda nombre, contenido, id_usuario, selecciones, metadatos: {
            "id_archivo": 1,
            "nombre": nombre,
            "tipo": "txt",
            "tamano_bytes": len(contenido),
            "estado": "ok",
            "filas_ok": 1,
            "filas_error": 0,
            "detalle": None,
        },
    )

    posterior = cliente.post(
        "/api/v1/inventario/ingesta",
        files=[("archivos", ("bueno.txt", b"y", "text/plain"))],
        data=_datos_metadatos(),
    )

    assert posterior.status_code == 200
    assert posterior.json()["archivos_ok"] == 1
