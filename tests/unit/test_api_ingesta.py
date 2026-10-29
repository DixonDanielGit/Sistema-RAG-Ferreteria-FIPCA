"""Pruebas de caja negra de las rutas HTTP de ingesta."""

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.deps import requiere_admin, usuario_actual
from app.api.v1 import inventario


def _app(usuario=None, *, rechazar=False):
    aplicacion = FastAPI()
    aplicacion.include_router(inventario.router, prefix="/api/v1")

    def autorizar():
        if rechazar:
            raise HTTPException(status_code=403, detail="Se requiere rol administrador")
        return usuario or {"id": 9, "rol": "admin"}

    aplicacion.dependency_overrides[requiere_admin] = autorizar
    aplicacion.dependency_overrides[usuario_actual] = autorizar
    return aplicacion


def test_admin_carga_lote_y_recibe_resultado_por_archivo(monkeypatch):
    llamadas = []

    def procesar(nombre, contenido, id_usuario):
        llamadas.append((nombre, contenido, id_usuario))
        return {
            "id_archivo": len(llamadas),
            "nombre": nombre,
            "tipo": nombre.rsplit(".", 1)[-1],
            "tamano_bytes": len(contenido),
            "estado": "ok" if nombre.endswith(".txt") else "rechazado",
            "filas_ok": 1 if nombre.endswith(".txt") else 0,
            "filas_error": 0,
            "detalle": None,
        }

    monkeypatch.setattr(inventario.etl_service, "procesar_archivo", procesar)
    cliente = TestClient(_app())

    respuesta = cliente.post(
        "/api/v1/inventario/ingesta",
        files=[
            ("archivos", ("catalogo.txt", b"SKU-1;Martillo;1.25", "text/plain")),
            ("archivos", ("datos.csv", b"a,b,c", "text/csv")),
        ],
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total_archivos"] == 2
    assert cuerpo["archivos_ok"] == 1
    assert cuerpo["archivos_rechazados"] == 1
    assert [llamada[2] for llamada in llamadas] == [9, 9]


def test_carga_requiere_administrador(monkeypatch):
    llamada = False

    def procesar(*_):
        nonlocal llamada
        llamada = True

    monkeypatch.setattr(inventario.etl_service, "procesar_archivo", procesar)
    cliente = TestClient(_app(rechazar=True))

    respuesta = cliente.post(
        "/api/v1/inventario/ingesta",
        files=[("archivos", ("catalogo.txt", b"data", "text/plain"))],
    )

    assert respuesta.status_code == 403
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
    )

    assert vacio.status_code == 400
    assert demasiados.status_code == 400


def test_lista_archivos_consulta_modelo_con_limite(monkeypatch):
    monkeypatch.setattr(inventario.inventario_model, "listar_archivos", lambda limite: [])
    cliente = TestClient(_app(usuario={"id": 10, "rol": "ventas"}))

    respuesta = cliente.get("/api/v1/inventario/archivos?limite=12")

    assert respuesta.status_code == 200
    assert respuesta.json() == []


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
    )

    assert fallida.status_code == 500
    assert not inventario._cerradura_ingesta.locked()

    monkeypatch.setattr(
        inventario.etl_service,
        "procesar_archivo",
        lambda nombre, contenido, id_usuario: {
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
    )

    assert posterior.status_code == 200
    assert posterior.json()["archivos_ok"] == 1
