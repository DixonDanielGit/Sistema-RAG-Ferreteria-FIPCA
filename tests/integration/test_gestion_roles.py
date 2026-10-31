"""Pruebas de roles configurables y autorizacion por capacidades."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4


def _token(cuenta, token_de):
    return {"Authorization": f"Bearer {token_de(cuenta)}"}


def _nombre_rol():
    return f"equipo_{uuid4().hex[:10]}"


def _datos_rol(nombre, permisos=()):
    return {
        "nombre": nombre,
        "descripcion": "Rol de prueba",
        "permisos": list(permisos),
    }


class TestGestionDeRoles:
    def test_migracion_repara_permisos_de_admin_que_faltan(self, conexion_limpieza):
        migracion = Path(__file__).resolve().parents[2] / "scripts" / "migracion_6_0.sql"
        with conexion_limpieza.cursor() as cur:
            cur.execute(
                """
                DELETE FROM rol_permiso
                 WHERE id_rol = (SELECT id_rol FROM rol WHERE LOWER(nombre) = 'admin')
                """
            )
            cur.execute(migracion.read_text(encoding="utf-8"))
            cur.execute(
                """
                SELECT COUNT(*) AS total
                  FROM rol_permiso rp
                  JOIN rol r ON r.id_rol = rp.id_rol
                 WHERE LOWER(r.nombre) = 'admin'
                """
            )
            cantidad_primera_ejecucion = cur.fetchone()[0]
            cur.execute(migracion.read_text(encoding="utf-8"))
            cur.execute(
                """
                SELECT COUNT(*) AS total
                  FROM rol_permiso rp
                  JOIN rol r ON r.id_rol = rp.id_rol
                 WHERE LOWER(r.nombre) = 'admin'
                """
            )
            cantidad_segunda_ejecucion = cur.fetchone()[0]

        assert cantidad_primera_ejecucion == 4
        assert cantidad_segunda_ejecucion == cantidad_primera_ejecucion

    def test_solo_admin_ve_la_gestion_de_roles_en_configuracion(
        self, cliente, crear_cuenta, token_de
    ):
        admin = crear_cuenta(usuario="admin_config")
        headers_admin = _token(admin, token_de)

        pagina_admin = cliente.get("/configuracion")
        assert pagina_admin.status_code == 200
        assert 'id="form-rol"' in pagina_admin.text
        assert 'id="boton-archivos"' in cliente.get("/chat").text

        estado_configuracion = cliente.get(
            "/api/v1/auth/configuracion/admin",
            headers=headers_admin,
        )
        assert estado_configuracion.status_code == 200

        cliente.cookies.clear()
        ventas = crear_cuenta(usuario="ventas_config", rol="ventas")
        token_de(ventas)

        pagina_ventas = cliente.get("/configuracion")
        assert pagina_ventas.status_code == 200
        assert 'id="form-rol"' not in pagina_ventas.text
        assert "Roles y permisos" not in pagina_ventas.text
        assert 'id="boton-archivos"' not in cliente.get("/chat").text

    def test_admin_crea_actualiza_y_elimina_roles(
        self, cliente, crear_cuenta, token_de
    ):
        admin = crear_cuenta()
        headers = _token(admin, token_de)
        nombre = _nombre_rol()

        creado = cliente.post(
            "/api/v1/auth/roles",
            json=_datos_rol(nombre, ["catalogos:ingestar"]),
            headers=headers,
        )

        assert creado.status_code == 201
        rol = creado.json()
        assert rol["nombre"] == nombre
        assert rol["permisos"] == ["catalogos:ingestar"]
        assert rol["protegido"] is False

        actualizado = cliente.put(
            f"/api/v1/auth/roles/{rol['id_rol']}",
            json=_datos_rol(nombre, ["catalogos:ingestar", "catalogos:eliminar"]),
            headers=headers,
        )
        assert actualizado.status_code == 200
        assert set(actualizado.json()["permisos"]) == {
            "catalogos:ingestar",
            "catalogos:eliminar",
        }

        eliminado = cliente.delete(
            f"/api/v1/auth/roles/{rol['id_rol']}",
            headers=headers,
        )
        assert eliminado.status_code == 200

    def test_capacidad_cambia_sin_renovar_el_token(
        self, cliente, crear_cuenta, token_de
    ):
        admin = crear_cuenta()
        headers_admin = _token(admin, token_de)
        nombre = _nombre_rol()
        rol = cliente.post(
            "/api/v1/auth/roles",
            json=_datos_rol(nombre),
            headers=headers_admin,
        ).json()
        cuenta = crear_cuenta(usuario="operador", rol=nombre)
        headers_operador = _token(cuenta, token_de)

        assert cliente.get(
            "/api/v1/auth/usuarios", headers=headers_operador
        ).status_code == 403

        cambio = cliente.put(
            f"/api/v1/auth/roles/{rol['id_rol']}",
            json=_datos_rol(nombre, ["usuarios:gestionar"]),
            headers=headers_admin,
        )
        assert cambio.status_code == 200
        assert cliente.get(
            "/api/v1/auth/usuarios", headers=headers_operador
        ).status_code == 200

        revocacion = cliente.put(
            f"/api/v1/auth/roles/{rol['id_rol']}",
            json=_datos_rol(nombre),
            headers=headers_admin,
        )
        assert revocacion.status_code == 200
        assert cliente.get(
            "/api/v1/auth/usuarios", headers=headers_operador
        ).status_code == 403

    def test_admin_asigna_un_rol_configurable_al_registrar_usuario(
        self, cliente, crear_cuenta, token_de
    ):
        admin = crear_cuenta()
        headers = _token(admin, token_de)
        nombre = _nombre_rol()
        rol = cliente.post(
            "/api/v1/auth/roles",
            json=_datos_rol(nombre, ["catalogos:ingestar"]),
            headers=headers,
        )
        assert rol.status_code == 201

        respuesta = cliente.post(
            "/api/v1/auth/register",
            json={
                "cedula": "V-22334455",
                "nombre": "Carlos",
                "apellido": "Perez",
                "usuario": "operador.nuevo",
                "correo": "operador.nuevo@ferreteria.test",
                "password": "ClaveSegura123",
                "rol": nombre,
            },
            headers=headers,
        )

        assert respuesta.status_code == 201
        assert respuesta.json()["rol"] == nombre
        assert respuesta.json()["permisos"] == ["catalogos:ingestar"]

    def test_solo_admin_puede_gestionar_roles(
        self, cliente, crear_cuenta, token_de
    ):
        vendedor = crear_cuenta(usuario="vendedor", rol="ventas")
        headers = _token(vendedor, token_de)
        datos = _datos_rol(_nombre_rol())

        assert cliente.get(
            "/api/v1/auth/roles/permisos", headers=headers
        ).status_code == 403
        assert cliente.post(
            "/api/v1/auth/roles", json=datos, headers=headers
        ).status_code == 403

    def test_admin_protegido_y_roles_asignados_no_se_eliminan(
        self, cliente, crear_cuenta, token_de
    ):
        admin = crear_cuenta()
        crear_cuenta(usuario="vendedor", rol="ventas")
        headers = _token(admin, token_de)
        roles = cliente.get("/api/v1/auth/roles", headers=headers).json()
        rol_admin = next(item for item in roles if item["nombre"] == "admin")
        rol_ventas = next(item for item in roles if item["nombre"] == "ventas")

        assert rol_admin["protegido"] is True
        assert set(rol_admin["permisos"]) == {
            "usuarios:gestionar",
            "catalogos:ingestar",
            "catalogos:eliminar",
            "configuracion:diagnostico",
        }
        assert cliente.put(
            f"/api/v1/auth/roles/{rol_admin['id_rol']}",
            json=_datos_rol("root", ["usuarios:gestionar"]),
            headers=headers,
        ).status_code == 409
        assert cliente.delete(
            f"/api/v1/auth/roles/{rol_admin['id_rol']}",
            headers=headers,
        ).status_code == 409
        assert cliente.delete(
            f"/api/v1/auth/roles/{rol_ventas['id_rol']}",
            headers=headers,
        ).status_code == 409

    def test_usuario_con_permiso_no_puede_asignarse_admin(
        self, cliente, crear_cuenta, token_de
    ):
        admin = crear_cuenta()
        headers_admin = _token(admin, token_de)
        nombre = _nombre_rol()
        rol = cliente.post(
            "/api/v1/auth/roles",
            json=_datos_rol(nombre, ["usuarios:gestionar"]),
            headers=headers_admin,
        ).json()
        gestor = crear_cuenta(usuario="gestor", rol=nombre)
        headers_gestor = _token(gestor, token_de)

        respuesta = cliente.patch(
            f"/api/v1/auth/usuarios/{gestor['id']}/rol",
            json={"rol": "admin"},
            headers=headers_gestor,
        )
        assert respuesta.status_code == 403
        assert cliente.post(
            "/api/v1/auth/roles",
            json=_datos_rol(_nombre_rol()),
            headers=headers_gestor,
        ).status_code == 403
        assert rol["id_rol"] > 0

    def test_permisos_desconocidos_son_rechazados(
        self, cliente, crear_cuenta, token_de
    ):
        admin = crear_cuenta()
        respuesta = cliente.post(
            "/api/v1/auth/roles",
            json=_datos_rol(_nombre_rol(), ["usuarios:*"]),
            headers=_token(admin, token_de),
        )

        assert respuesta.status_code == 422
