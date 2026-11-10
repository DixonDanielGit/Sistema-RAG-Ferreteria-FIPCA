"""Pruebas de integracion de la vista y el endpoint del Buscador Comercial.

Corren sobre la copia desechable ``ferreteria_rag_test``, que recibe la
migracion ``9_0`` (columna ``texto_busqueda`` e indices GIN) desde
``tests/conftest.py``. No tocan la base de desarrollo.

Se comprueba que:
- ``/search`` exista, exija sesion y muestre la interfaz con el panel de carga;
- ``/api/v1/inventario/busqueda`` valide la consulta y responda 401/422;
- la busqueda encuentre productos reales por codigo y por full-text;
- los comodines o intentos de inyeccion no rompan la sentencia;
- cada consulta quede registrada en la bitacora.
"""

from __future__ import annotations

import uuid

import pytest

from app.models import bitacora

BUSQUEDA = "/api/v1/inventario/busqueda"


@pytest.fixture
def navegador(cliente):
    cliente.cookies.clear()
    yield cliente
    cliente.cookies.clear()


@pytest.fixture
def sesion(navegador, crear_cuenta):
    cuenta = crear_cuenta()
    respuesta = navegador.post(
        "/api/v1/auth/login",
        json={"identificador": cuenta["usuario"], "password": cuenta["password"]},
    )
    assert respuesta.status_code == 200, respuesta.text
    return {"cuenta": cuenta, "csrf": navegador.cookies.get("csrf_token")}


@pytest.fixture
def sesion_ventas(navegador, crear_cuenta):
    cuenta = crear_cuenta(usuario="vendedor", rol="ventas")
    respuesta = navegador.post(
        "/api/v1/auth/login",
        json={"identificador": cuenta["usuario"], "password": cuenta["password"]},
    )
    assert respuesta.status_code == 200, respuesta.text
    return cuenta


@pytest.fixture
def producto_de_prueba(conexion_rag_limpieza):
    """Crea productos unicos en la copia de prueba y los retira al terminar."""
    creados: list[dict] = []

    def _crear(nombre: str, *, codigo: str | None = None, stock: int = 4) -> dict:
        token = uuid.uuid4().hex[:10]
        datos = {
            "codigo": codigo or ("ZKB" + token[:8].upper()),
            "nombre": nombre.replace("{token}", token),
            "token": token,
        }
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO productos (codigo, nombre, precio, stock)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (datos["codigo"], datos["nombre"], 12.5, stock),
            )
            datos["id"] = cursor.fetchone()[0]
        creados.append(datos)
        return datos

    yield _crear

    ids = [producto["id"] for producto in creados]
    if ids:
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute("DELETE FROM productos WHERE id = ANY(%s)", (ids,))


class TestVistaDelBuscador:
    def test_sin_sesion_redirige_al_login(self, navegador):
        respuesta = navegador.get("/search", follow_redirects=False)

        assert respuesta.status_code == 303
        assert respuesta.headers["location"] == "/login"

    def test_con_sesion_muestra_el_buscador(self, navegador, sesion):
        respuesta = navegador.get("/search")

        assert respuesta.status_code == 200
        assert 'id="form-buscador"' in respuesta.text
        assert 'id="consulta-buscador"' in respuesta.text
        assert 'maxlength="200"' in respuesta.text
        assert 'id="contenedor-resultados"' in respuesta.text
        assert 'id="filas-buscador"' in respuesta.text
        assert 'id="tarjetas-buscador"' in respuesta.text
        assert 'id="orden-movil-buscador"' in respuesta.text
        assert 'id="buscador-vacio"' in respuesta.text
        assert 'id="resumen-buscador"' in respuesta.text
        assert 'id="boton-ver-catalogo"' in respuesta.text
        assert 'id="paginacion-catalogo"' in respuesta.text
        assert respuesta.text.index('id="limite-resultados-buscador"') < respuesta.text.index(
            'class="buscador__tabla-contenedor"'
        )
        cabecera = respuesta.text.split(
            '<table class="buscador__tabla">', 1
        )[1].split("</thead>", 1)[0]
        assert cabecera.count("<th ") == 4
        assert "Existencias" not in cabecera
        etiquetas = ("Código", "Producto", "Proveedor", "Precio")
        assert [etiqueta for etiqueta in etiquetas if etiqueta in cabecera] == list(
            etiquetas
        )

    def test_carga_el_javascript_de_la_vista(self, navegador, sesion):
        html = navegador.get("/search").text

        assert "/static/js/buscador.js" in html
        assert "/static/js/fuentes.js" in html

    def test_el_menu_marca_buscador_como_activo(self, navegador, sesion):
        html = navegador.get("/search").text
        tramo = html.split('href="/search"', 1)[1][:160]

        assert 'aria-current="page"' in tramo

    def test_ofrece_atajos_de_ejemplo(self, navegador, sesion):
        assert navegador.get("/search").text.count("data-buscar=") >= 3

    def test_explica_que_la_busqueda_no_usa_ia(self, navegador, sesion):
        html = navegador.get("/search").text

        assert "inteligencia artificial" in html
        assert "PostgreSQL" in html

    def test_incluye_el_panel_para_subir_archivos(self, navegador, sesion):
        html = navegador.get("/search").text

        assert 'id="panel-fuentes"' in html
        assert 'id="zona-archivos"' in html
        assert 'id="archivos"' in html
        assert 'accept=".pdf,.xlsx,.docx,.txt,.md"' in html
        assert 'id="dialogo-revision-fuentes"' in html
        assert "Agregue sus archivos aquí" in html

    def test_ventas_ve_el_buscador_sin_controles_de_carga(self, navegador, sesion_ventas):
        html = navegador.get("/search").text

        assert 'id="form-buscador"' in html
        assert 'id="panel-fuentes"' in html
        assert 'id="archivos"' not in html
        assert 'id="zona-archivos"' not in html
        assert 'id="dialogo-revision-fuentes"' not in html
        assert "Un administrador todavía no ha cargado el catálogo." in html


class TestEndpointDeBusqueda:
    def test_sin_sesion_responde_401(self, navegador):
        respuesta = navegador.get(BUSQUEDA, params={"consulta": "manguera"})

        assert respuesta.status_code == 401

    def test_consulta_vacia_se_rechaza(self, navegador, sesion):
        respuesta = navegador.get(BUSQUEDA, params={"consulta": ""})

        assert respuesta.status_code == 422

    def test_consulta_de_un_caracter_se_acepta(self, navegador, sesion):
        respuesta = navegador.get(BUSQUEDA, params={"consulta": "a"})

        assert respuesta.status_code == 200
        assert respuesta.json()["consulta"] == "a"

    def test_consulta_solo_de_espacios_se_rechaza(self, navegador, sesion):
        """Dos espacios pasan el minimo de longitud pero no significan nada."""
        respuesta = navegador.get(BUSQUEDA, params={"consulta": "  "})

        assert respuesta.status_code == 422

    def test_consulta_demasiado_larga_se_rechaza(self, navegador, sesion):
        respuesta = navegador.get(BUSQUEDA, params={"consulta": "m" * 201})

        assert respuesta.status_code == 422

    def test_limite_fuera_de_rango_se_rechaza(self, navegador, sesion):
        respuesta = navegador.get(BUSQUEDA, params={"consulta": "manguera", "limite": 500})

        assert respuesta.status_code == 422

    def test_rol_ventas_tambien_puede_buscar(self, navegador, sesion_ventas):
        respuesta = navegador.get(BUSQUEDA, params={"consulta": "manguera"})

        assert respuesta.status_code == 200, respuesta.text
        assert set(respuesta.json()) == {"consulta", "total", "productos"}

    def test_sin_coincidencias_es_un_resultado_valido(self, navegador, sesion):
        consulta = "zzz-" + uuid.uuid4().hex[:12]
        respuesta = navegador.get(BUSQUEDA, params={"consulta": consulta})

        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["consulta"] == consulta
        assert datos["total"] == 0
        assert datos["productos"] == []

    def test_encuentra_un_producto_por_su_codigo(self, navegador, sesion, producto_de_prueba):
        producto = producto_de_prueba("Manguera de prueba {token}")
        respuesta = navegador.get(BUSQUEDA, params={"consulta": producto["codigo"]})

        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["total"] >= 1
        assert any(fila["codigo"] == producto["codigo"] for fila in datos["productos"])

    def test_busca_producto_insertado_directamente_sin_archivo_usando_un_caracter(
        self, navegador, sesion, producto_de_prueba
    ):
        producto = producto_de_prueba(
            "Producto de prueba directa {token}",
            codigo="Q" + uuid.uuid4().hex[:8].upper(),
        )

        respuesta = navegador.get(BUSQUEDA, params={"consulta": "q"})

        assert respuesta.status_code == 200
        assert any(
            fila["codigo"] == producto["codigo"]
            for fila in respuesta.json()["productos"]
        )

    def test_encuentra_por_full_text_y_no_por_coincidencia_literal(
        self, navegador, sesion, producto_de_prueba
    ):
        """"mangueras de riego" no esta como subcadena del nombre, pero el
        diccionario espanol si lo resuelve: ese es el trabajo del tsvector."""
        producto = producto_de_prueba("MANGUERA RIEGO REFORZADA {token}")
        respuesta = navegador.get(BUSQUEDA, params={"consulta": "mangueras de riego"})

        assert respuesta.status_code == 200
        ids = [fila["id"] for fila in respuesta.json()["productos"]]
        assert producto["id"] in ids

    def test_el_limite_acota_la_lista_pero_no_el_total(
        self, navegador, sesion, producto_de_prueba
    ):
        for _ in range(3):
            producto_de_prueba("Rotomartillo percutor {token}")

        respuesta = navegador.get(
            BUSQUEDA, params={"consulta": "rotomartillo", "limite": 2}
        )

        datos = respuesta.json()
        assert len(datos["productos"]) == 2
        assert datos["total"] >= 3

    def test_la_busqueda_filtrada_pagina_y_ordena_todas_las_coincidencias(
        self, navegador, sesion, producto_de_prueba
    ):
        productos = [
            producto_de_prueba("Ordenable de prueba {token}", stock=stock)
            for stock in (3, 1, 2)
        ]

        paginas = [
            navegador.get(
                BUSQUEDA,
                params={
                    "consulta": "ordenable",
                    "limite": 1,
                    "pagina": pagina,
                    "ordenar_por": "stock",
                    "direccion": "asc",
                },
            )
            for pagina in (1, 2, 3)
        ]

        assert all(respuesta.status_code == 200 for respuesta in paginas)
        datos = [respuesta.json() for respuesta in paginas]
        assert all(resultado["total"] == 3 for resultado in datos)
        assert [resultado["pagina"] for resultado in datos] == [1, 2, 3]
        assert [
            resultado["productos"][0]["id"] for resultado in datos
        ] == [
            producto["id"]
            for producto in sorted(productos, key=lambda p: p["stock"])
        ]
        assert [
            resultado["productos"][0]["stock"] for resultado in datos
        ] == [1, 2, 3]

    def test_los_comodines_se_buscan_como_texto(self, navegador, sesion):
        """`%`, `_` y comillas no rompen la sentencia ni devuelven el catalogo."""
        respuesta = navegador.get(
            BUSQUEDA, params={"consulta": "%_' OR 1=1 --"}
        )

        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["total"] == 0
        assert datos["productos"] == []

    def test_se_normalizan_los_espacios_de_la_consulta(self, navegador, sesion):
        respuesta = navegador.get(
            BUSQUEDA, params={"consulta": "  manguera   riego  "}
        )

        assert respuesta.status_code == 200
        assert respuesta.json()["consulta"] == "manguera riego"

    def test_cada_consulta_queda_en_la_bitacora(
        self, navegador, sesion, conexion_limpieza
    ):
        navegador.get(BUSQUEDA, params={"consulta": "manguera de riego"})

        with conexion_limpieza.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM bitacora WHERE accion LIKE %s",
                ("busqueda de catalogo: manguera de riego%",),
            )
            assert cursor.fetchone()[0] >= 1

    def test_el_evento_de_bitacora_identifica_al_usuario(
        self, navegador, sesion, conexion_limpieza
    ):
        navegador.get(BUSQUEDA, params={"consulta": "manguera"})

        eventos = bitacora.listar(limite=1)
        assert eventos, "La busqueda no dejo registro en la bitacora"
        assert "busqueda de catalogo" in eventos[0]["accion"]
        assert eventos[0]["id_usuario"] == sesion["cuenta"]["id"]
        assert eventos[0]["modulo"] == "inventario"


class TestEndpointDeCatalogo:
    def test_sin_sesion_responde_401(self, navegador):
        respuesta = navegador.get("/api/v1/inventario/catalogo")

        assert respuesta.status_code == 401

    def test_rechaza_pagina_o_limite_fuera_de_rango(self, navegador, sesion):
        pagina = navegador.get(
            "/api/v1/inventario/catalogo", params={"pagina": 0}
        )
        limite = navegador.get(
            "/api/v1/inventario/catalogo", params={"limite": 101}
        )

        assert pagina.status_code == 422
        assert limite.status_code == 422

    def test_pagina_del_buscador_ofrece_tamanos_de_25_a_100_registros(
        self, navegador, sesion
    ):
        respuesta = navegador.get("/search")

        assert respuesta.status_code == 200
        assert 'id="limite-resultados-buscador"' in respuesta.text
        assert '<option value="25" selected>25</option>' in respuesta.text
        assert '<option value="50">50</option>' in respuesta.text
        assert '<option value="75">75</option>' in respuesta.text
        assert '<option value="100">100</option>' in respuesta.text

    def test_devuelve_paginas_estables_y_total_de_productos_activos(
        self, navegador, sesion, producto_de_prueba, conexion_rag_limpieza
    ):
        productos = [
            producto_de_prueba("Producto listado {token}") for _ in range(3)
        ]
        inactivo = productos[-1]
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute(
                "UPDATE productos SET activo = FALSE WHERE id = %s",
                (inactivo["id"],),
            )
            cursor.execute("SELECT COUNT(*) FROM productos WHERE activo")
            total_esperado = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT id
                  FROM productos
                 WHERE activo
                 ORDER BY nombre ASC, id
                 LIMIT 4
                """
            )
            ids_esperados = [fila[0] for fila in cursor.fetchall()]

        pagina_uno = navegador.get(
            "/api/v1/inventario/catalogo",
            params={"pagina": 1, "limite": 2},
        )
        pagina_dos = navegador.get(
            "/api/v1/inventario/catalogo",
            params={"pagina": 2, "limite": 2},
        )

        assert pagina_uno.status_code == 200, pagina_uno.text
        assert pagina_dos.status_code == 200, pagina_dos.text
        datos_uno = pagina_uno.json()
        datos_dos = pagina_dos.json()
        assert datos_uno["total"] == total_esperado
        assert datos_dos["total"] == total_esperado
        assert datos_uno["pagina"] == 1
        assert datos_dos["pagina"] == 2
        ids_recibidos = [
            producto["id"]
            for producto in datos_uno["productos"] + datos_dos["productos"]
        ]
        assert ids_recibidos == ids_esperados
        assert inactivo["id"] not in ids_recibidos

    def test_pagina_fuera_del_catalogo_devuelve_lista_vacia_y_total(
        self, navegador, sesion, conexion_rag_limpieza
    ):
        with conexion_rag_limpieza.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM productos WHERE activo")
            total_esperado = cursor.fetchone()[0]

        respuesta = navegador.get(
            "/api/v1/inventario/catalogo",
            params={"pagina": total_esperado + 1, "limite": 1},
        )

        assert respuesta.status_code == 200
        assert respuesta.json()["total"] == total_esperado
        assert respuesta.json()["productos"] == []
