"""Pruebas unitarias de la ruta para consultar el catalogo completo."""

from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import usuario_actual
from app.api.v1 import inventario
from app.models import inventario as inventario_model


def _cliente():
    aplicacion = FastAPI()
    aplicacion.include_router(inventario.router, prefix="/api/v1")
    aplicacion.dependency_overrides[usuario_actual] = lambda: {
        "id": 9,
        "rol": "admin",
    }
    return TestClient(aplicacion)


def test_catalogo_entrega_pagina_total_y_audita_la_consulta(monkeypatch):
    llamadas = []
    auditorias = []
    producto = {
        "id": 42,
        "codigo": "ABC-42",
        "nombre": "Producto de prueba",
        "precio": 12.5,
        "iva": 16,
        "descuentos": 0,
        "stock": 4,
        "moneda": "USD",
    }

    def listar(limite, desplazamiento, ordenar_por, direccion):
        llamadas.append((limite, desplazamiento, ordenar_por, direccion))
        return [producto], 61

    monkeypatch.setattr(
        inventario.inventario_model, "listar_productos_catalogo", listar
    )
    monkeypatch.setattr(
        inventario,
        "registrar_evento",
        lambda request, accion, id_usuario: auditorias.append(
            (accion, id_usuario)
        ),
    )

    respuesta = _cliente().get(
        "/api/v1/inventario/catalogo",
        params={"pagina": 3, "limite": 25},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 61
    assert respuesta.json()["pagina"] == 3
    assert respuesta.json()["limite"] == 25
    assert respuesta.json()["productos"][0]["id"] == 42
    assert llamadas == [(25, 50, None, "asc")]
    assert auditorias == [("consulta de catalogo completo: pagina 3", 9)]


def test_catalogo_usa_pagina_y_limite_predeterminados(monkeypatch):
    llamadas = []

    def listar(limite, desplazamiento, ordenar_por, direccion):
        llamadas.append((limite, desplazamiento, ordenar_por, direccion))
        return [], 0

    monkeypatch.setattr(
        inventario.inventario_model,
        "listar_productos_catalogo",
        listar,
    )
    monkeypatch.setattr(inventario, "registrar_evento", lambda *_args, **_kwargs: None)

    respuesta = _cliente().get("/api/v1/inventario/catalogo")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "total": 0,
        "pagina": 1,
        "limite": inventario.LIMITE_DEFECTO_BUSQUEDA,
        "productos": [],
    }
    assert llamadas == [
        (inventario.LIMITE_DEFECTO_BUSQUEDA, 0, None, "asc")
    ]


def test_catalogo_acepta_ordenamiento_por_columna(monkeypatch):
    llamadas = []

    def listar(limite, desplazamiento, ordenar_por, direccion):
        llamadas.append((limite, desplazamiento, ordenar_por, direccion))
        return [], 0

    monkeypatch.setattr(
        inventario.inventario_model, "listar_productos_catalogo", listar
    )
    monkeypatch.setattr(inventario, "registrar_evento", lambda *_args, **_kwargs: None)

    respuesta = _cliente().get(
        "/api/v1/inventario/catalogo",
        params={"ordenar_por": "proveedor", "direccion": "desc"},
    )

    assert respuesta.status_code == 200
    assert llamadas == [
        (inventario.LIMITE_DEFECTO_BUSQUEDA, 0, "proveedor", "desc")
    ]


def test_modelo_lista_productos_activos_con_limite_y_desplazamiento(monkeypatch):
    consultas = []

    class CursorFalso:
        def execute(self, consulta, parametros=()):
            consultas.append((" ".join(consulta.split()), parametros))

        def fetchone(self):
            return {"total": 3}

        def fetchall(self):
            return [{"id": 8, "nombre": "Producto de prueba"}]

    @contextmanager
    def cursor_falso(*, commit):
        assert commit is False
        yield CursorFalso()

    monkeypatch.setattr(inventario_model, "cursor_rag", cursor_falso)

    filas, total = inventario_model.listar_productos_catalogo(2, 2)

    assert total == 3
    assert filas == [{"id": 8, "nombre": "Producto de prueba"}]
    assert consultas[0][1] == ()
    assert consultas[1][1] == (2, 2)
    assert "WHERE p.activo" in consultas[1][0]
    assert "ORDER BY p.nombre ASC, p.id" in consultas[1][0]


def test_modelo_usa_orden_validado_antes_de_paginar(monkeypatch):
    consultas = []

    class CursorFalso:
        def execute(self, consulta, parametros=()):
            consultas.append((" ".join(consulta.split()), parametros))

        def fetchone(self):
            return {"total": 5}

        def fetchall(self):
            return [{"id": 8, "nombre": "Producto de prueba"}]

    @contextmanager
    def cursor_falso(*, commit):
        assert commit is False
        yield CursorFalso()

    monkeypatch.setattr(inventario_model, "cursor_rag", cursor_falso)

    inventario_model.listar_productos_catalogo(2, 2, "precio", "desc")

    assert "ORDER BY p.precio DESC NULLS LAST, p.id ASC" in consultas[1][0]
    assert consultas[1][1] == (2, 2)


def test_modelo_ordena_todas_las_coincidencias_antes_de_paginar(monkeypatch):
    consultas = []

    class CursorFalso:
        def execute(self, consulta, parametros=()):
            consultas.append((" ".join(consulta.split()), parametros))

        def fetchone(self):
            return {"total": 9}

        def fetchall(self):
            return [{"id": 8, "stock": 2}]

    @contextmanager
    def cursor_falso(*, commit):
        assert commit is False
        yield CursorFalso()

    monkeypatch.setattr(inventario_model, "cursor_rag", cursor_falso)

    filas, total = inventario_model.buscar_productos_fulltext(
        "martillo", 2, 4, "stock", "desc"
    )

    consulta, parametros = consultas[1]
    assert total == 9
    assert filas == [{"id": 8, "stock": 2}]
    assert "ORDER BY p.stock DESC NULLS LAST, p.id ASC" in consulta
    assert consulta.endswith("LIMIT %s OFFSET %s")
    assert parametros[-2:] == (2, 4)


def test_modelo_no_consulta_pagina_mas_alla_del_total(monkeypatch):
    consultas = []

    class CursorFalso:
        def execute(self, consulta, parametros=()):
            consultas.append(consulta)

        def fetchone(self):
            return {"total": 3}

    @contextmanager
    def cursor_falso(*, commit):
        yield CursorFalso()

    monkeypatch.setattr(inventario_model, "cursor_rag", cursor_falso)

    filas, total = inventario_model.listar_productos_catalogo(50, 3)

    assert filas == []
    assert total == 3
    assert len(consultas) == 1
