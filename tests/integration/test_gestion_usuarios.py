"""Pruebas de API y vistas de administracion y perfil."""

from __future__ import annotations

from io import BytesIO

from PIL import Image


def _token(cuenta, token_de):
    return {"Authorization": f"Bearer {token_de(cuenta)}"}


def _perfil(**cambios):
    datos = {
        "cedula": "V-22334455",
        "nombre": "Ana",
        "apellido": "Perez",
        "usuario": "ana.perfil",
        "correo": "ana.perfil@ferreteria.test",
    }
    datos.update(cambios)
    return datos


def _png() -> bytes:
    salida = BytesIO()
    Image.new("RGB", (20, 20), color=(36, 99, 235)).save(salida, format="PNG")
    return salida.getvalue()


class TestAdministracionUsuarios:
    def test_admin_lista_cuentas_sin_hash_ni_imagen(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta()
        respuesta = cliente.get("/api/v1/auth/usuarios", headers=_token(cuenta, token_de))

        assert respuesta.status_code == 200
        assert respuesta.json()[0]["usuario"] == cuenta["usuario"]
        assert respuesta.json()[0]["tiene_imagen"] is False
        assert "password" not in respuesta.text
        assert "imagen_perfil" not in respuesta.text

    def test_ventas_no_puede_listar_cuentas(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta(usuario="vendedor", rol="ventas")
        respuesta = cliente.get("/api/v1/auth/usuarios", headers=_token(cuenta, token_de))
        assert respuesta.status_code == 403

    def test_no_se_puede_quitar_el_ultimo_rol_admin(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta()
        respuesta = cliente.patch(
            f"/api/v1/auth/usuarios/{cuenta['id']}/rol",
            json={"rol": "ventas"},
            headers=_token(cuenta, token_de),
        )
        assert respuesta.status_code == 409

    def test_no_se_puede_desactivar_el_ultimo_admin(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta()
        respuesta = cliente.patch(
            f"/api/v1/auth/usuarios/{cuenta['id']}/estado",
            json={"activo": False},
            headers=_token(cuenta, token_de),
        )
        assert respuesta.status_code == 409

    def test_admin_puede_cambiar_rol_y_estado_de_otra_cuenta(
        self, cliente, crear_cuenta, token_de
    ):
        admin = crear_cuenta()
        ventas = crear_cuenta(usuario="vendedor", rol="ventas")
        headers = _token(admin, token_de)

        cambio_rol = cliente.patch(
            f"/api/v1/auth/usuarios/{ventas['id']}/rol",
            json={"rol": "admin"},
            headers=headers,
        )
        assert cambio_rol.status_code == 200
        assert cambio_rol.json()["rol"] == "admin"

        desactivar = cliente.patch(
            f"/api/v1/auth/usuarios/{ventas['id']}/estado",
            json={"activo": False},
            headers=headers,
        )
        assert desactivar.status_code == 200
        assert desactivar.json()["activo"] is False

    def test_admin_puede_editar_datos_y_rol_desde_la_cuenta(
        self, cliente, crear_cuenta, token_de
    ):
        admin = crear_cuenta()
        ventas = crear_cuenta(usuario="vendedor", rol="ventas")
        respuesta = cliente.put(
            f"/api/v1/auth/usuarios/{ventas['id']}",
            json=_perfil(
                cedula="V-22334455",
                usuario="vendedor.actualizado",
                correo="vendedor.actualizado@ferreteria.test",
                rol="admin",
            ),
            headers=_token(admin, token_de),
        )

        assert respuesta.status_code == 200
        assert respuesta.json()["usuario"] == "vendedor.actualizado"
        assert respuesta.json()["correo"] == "vendedor.actualizado@ferreteria.test"
        assert respuesta.json()["rol"] == "admin"

    def test_ventas_no_puede_editar_otra_cuenta(
        self, cliente, crear_cuenta, token_de
    ):
        admin = crear_cuenta()
        ventas = crear_cuenta(usuario="vendedor", rol="ventas")
        respuesta = cliente.put(
            f"/api/v1/auth/usuarios/{admin['id']}",
            json=_perfil(rol="ventas"),
            headers=_token(ventas, token_de),
        )
        assert respuesta.status_code == 403

    def test_admin_no_puede_quitarse_el_ultimo_rol_al_editar(
        self, cliente, crear_cuenta, token_de
    ):
        admin = crear_cuenta()
        respuesta = cliente.put(
            f"/api/v1/auth/usuarios/{admin['id']}",
            json=_perfil(rol="ventas"),
            headers=_token(admin, token_de),
        )
        assert respuesta.status_code == 409

    def test_estado_no_permite_eliminar_una_cuenta(
        self, cliente, crear_cuenta, token_de
    ):
        cuenta = crear_cuenta()
        respuesta = cliente.delete(
            f"/api/v1/auth/usuarios/{cuenta['id']}",
            headers=_token(cuenta, token_de),
        )
        assert respuesta.status_code == 405


class TestPerfilPersonal:
    def test_actualiza_datos_sin_cambiar_rol(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta()
        respuesta = cliente.put(
            "/api/v1/auth/me",
            json=_perfil(),
            headers=_token(cuenta, token_de),
        )
        assert respuesta.status_code == 200
        assert respuesta.json()["usuario"] == "ana.perfil"
        assert respuesta.json()["cedula"] == "V-22334455"
        assert respuesta.json()["rol"] == "admin"

    def test_rechaza_usuario_o_cedula_duplicados(self, cliente, crear_cuenta, token_de):
        propietario = crear_cuenta()
        crear_cuenta(usuario="otro", correo="otro@ferreteria.test")
        respuesta = cliente.put(
            "/api/v1/auth/me",
            json=_perfil(usuario="otro"),
            headers=_token(propietario, token_de),
        )
        assert respuesta.status_code == 409

    def test_perfil_no_admite_editar_rol(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta()
        datos = _perfil(rol="ventas")
        respuesta = cliente.put(
            "/api/v1/auth/me",
            json=datos,
            headers=_token(cuenta, token_de),
        )
        assert respuesta.status_code == 422

    def test_perfil_rechaza_correo_con_dominio_malformado(
        self, cliente, crear_cuenta, token_de
    ):
        cuenta = crear_cuenta()
        respuesta = cliente.put(
            "/api/v1/auth/me",
            json=_perfil(correo="ana@-ferreteria.test"),
            headers=_token(cuenta, token_de),
        )

        assert respuesta.status_code == 422

    def test_subir_consultar_y_quitar_imagen(self, cliente, crear_cuenta, token_de):
        cuenta = crear_cuenta()
        headers = _token(cuenta, token_de)
        subida = cliente.post(
            "/api/v1/auth/me/imagen",
            files={"archivo": ("foto.png", _png(), "image/png")},
            headers=headers,
        )
        assert subida.status_code == 200

        imagen = cliente.get("/api/v1/auth/me/imagen", headers=headers)
        assert imagen.status_code == 200
        assert imagen.headers["content-type"] == "image/webp"
        assert imagen.headers["cache-control"] == "private, no-store"
        assert imagen.content.startswith(b"RIFF")

        eliminacion = cliente.delete("/api/v1/auth/me/imagen", headers=headers)
        assert eliminacion.status_code == 200
        assert cliente.get("/api/v1/auth/me/imagen", headers=headers).status_code == 404

    def test_rechaza_svg_y_solicitudes_excesivas(self, cliente, crear_cuenta, token_de):
        headers = _token(crear_cuenta(), token_de)
        svg = cliente.post(
            "/api/v1/auth/me/imagen",
            files={"archivo": ("avatar.svg", b"<svg/>", "image/svg+xml")},
            headers=headers,
        )
        assert svg.status_code == 422

        grande = cliente.post(
            "/api/v1/auth/me/imagen",
            files={"archivo": ("foto.png", b"x" * (2 * 1024 * 1024 + 1), "image/png")},
            headers=headers,
        )
        assert grande.status_code == 413


class TestConfiguracion:
    def test_estado_tecnico_solo_es_visible_para_admin(self, cliente, crear_cuenta, token_de):
        admin = crear_cuenta()
        ventas = crear_cuenta(usuario="vendedor", rol="ventas")

        respuesta_admin = cliente.get(
            "/api/v1/auth/configuracion/admin",
            headers=_token(admin, token_de),
        )
        respuesta_ventas = cliente.get(
            "/api/v1/auth/configuracion/admin",
            headers=_token(ventas, token_de),
        )

        assert respuesta_admin.status_code == 200
        assert set(respuesta_admin.json()["bases"]) == {
            "ferreteria_rag",
            "ferreteria_usuarios",
        }
        assert respuesta_admin.json()["imagen_perfil_max_mb"] == 2
        assert respuesta_ventas.status_code == 403


class TestVistasDeCuenta:
    def test_librerias_de_interfaz_estan_disponibles_localmente(self, cliente):
        for ruta in (
            "/static/vendor/sweetalert2.all.min.js",
            "/static/vendor/datatables.core.min.js",
            "/static/vendor/datatables.dataTables.min.js",
            "/static/vendor/datatables.responsive.core.min.js",
            "/static/vendor/datatables.responsive.min.js",
            "/static/vendor/datatables.responsive.min.css",
        ):
            respuesta = cliente.get(ruta)
            assert respuesta.status_code == 200
            assert respuesta.content

    def test_vistas_requieren_sesion(self, cliente):
        for ruta in ("/usuarios", "/perfil", "/configuracion"):
            respuesta = cliente.get(ruta, follow_redirects=False)
            assert respuesta.status_code == 303
            assert respuesta.headers["location"] == "/login"

    def test_ventas_ve_perfil_y_configuracion_pero_no_usuarios(
        self, cliente, crear_cuenta
    ):
        cuenta = crear_cuenta(usuario="vendedor", rol="ventas")
        cliente.post(
            "/api/v1/auth/login",
            json={"identificador": cuenta["usuario"], "password": cuenta["password"]},
        )

        assert cliente.get("/perfil").status_code == 200
        configuracion = cliente.get("/configuracion")
        assert configuracion.status_code == 200
        assert "Estado y límites técnicos" not in configuracion.text
        assert "/static/js/configuracion.js" not in configuracion.text
        usuarios = cliente.get("/usuarios", follow_redirects=False)
        assert usuarios.status_code == 303

    def test_perfil_muestra_avatar_por_defecto(self, cliente, crear_cuenta):
        cuenta = crear_cuenta()
        cliente.post(
            "/api/v1/auth/login",
            json={"identificador": cuenta["usuario"], "password": cuenta["password"]},
        )
        html = cliente.get("/perfil").text
        assert "/static/img/avatar-default.svg" in html
        assert "/static/js/perfil.js" in html
        assert 'id="modal-perfil"' in html
        assert "modal-lg modal-dialog-scrollable perfil-modal-dialog" in html
        assert 'id="abrir-modal-perfil"' in html
        assert 'id="abrir-modal-usuario"' not in html
        assert 'id="form-perfil" novalidate' in html
        assert 'class="perfil-modal__datos"' in html
        assert 'class="perfil-modal__lateral"' in html
        assert html.count("input-validar") == 5
        assert all(
            f'name="{campo}"' in html
            for campo in ("nombre", "apellido", "cedula", "usuario", "correo")
        )
        assert 'id="perfil-resumen-usuario"' in html
        assert 'id="perfil-resumen-cedula"' in html
        assert 'id="perfil-resumen-correo"' in html

    def test_admin_ve_gestion_de_usuarios(self, cliente, crear_cuenta):
        cuenta = crear_cuenta()
        cliente.post(
            "/api/v1/auth/login",
            json={"identificador": cuenta["usuario"], "password": cuenta["password"]},
        )
        html = cliente.get("/usuarios").text
        assert 'id="form-usuario"' in html
        assert 'id="modal-usuario"' in html
        assert html.count("<form") == 1
        assert 'id="form-usuario2"' not in html
        assert 'name="passwordConf"' in html
        assert "input-validar" in html
        assert 'id="filas-usuarios"' in html
        assert "/static/js/usuarios.js" in html
        assert "/static/vendor/datatables.dataTables.min.js" in html
        assert 'class="datatable-contenedor"' in html
        assert 'class="datatable-tabla-scroll"' in html
        assert "/static/vendor/datatables.responsive.min.js" not in html
        assert 'id="tabla-usuarios"' in html
        assert 'id="fipca-menu-toggle"' in html
        assert 'aria-label="Cerrar sesión"' in html
