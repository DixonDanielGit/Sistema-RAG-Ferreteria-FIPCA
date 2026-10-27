"""Pruebas de seguridad frente a inyeccion SQL (RNF-02.2).

Comprueban dos capas independientes:

1. La API usa consultas parametrizadas: una carga maliciosa se trata como
   texto, nunca como SQL.
2. El rol de la aplicacion no puede alterar la estructura ni borrar datos,
   de modo que ni una hipotetica inyeccion lograria dano permanente.
"""

from __future__ import annotations

import psycopg2
import pytest

from app.config import get_settings

pytestmark = pytest.mark.usefixtures("usuarios_limpios")

LOGIN = "/api/v1/auth/login"
REGISTRO = "/api/v1/auth/register"
ME = "/api/v1/auth/me"

CARGAS = [
    "' OR '1'='1",
    "' OR 1=1 --",
    "admin'--",
    "admin' #",
    "'; DROP TABLE usuarios; --",
    "' UNION SELECT NULL, NULL, NULL --",
    '" OR ""="',
    "1; DELETE FROM usuarios",
    "' OR EXISTS (SELECT 1 FROM usuarios) --",
    "%' OR usuario LIKE '%",
    "' AND 1=(SELECT COUNT(*) FROM usuarios) --",
    "'||(SELECT current_user)||'",
]


def _contar_usuarios() -> int:
    with psycopg2.connect(get_settings().database_url_usuarios) as conexion:
        with conexion.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM usuarios")
            return int(cur.fetchone()[0])


class TestInyeccionEnElLogin:
    @pytest.mark.parametrize("carga", CARGAS)
    def test_en_el_identificador_no_autentica(self, cliente, crear_cuenta, carga):
        crear_cuenta()

        respuesta = cliente.post(
            LOGIN, json={"identificador": carga, "password": "ClaveSegura123"}
        )

        assert respuesta.status_code == 401
        assert "access_token" not in respuesta.text

    @pytest.mark.parametrize("carga", CARGAS)
    def test_en_la_contrasena_no_autentica(self, cliente, crear_cuenta, carga):
        cuenta = crear_cuenta()

        respuesta = cliente.post(
            LOGIN, json={"identificador": cuenta["usuario"], "password": carga}
        )

        assert respuesta.status_code == 401
        assert "access_token" not in respuesta.text

    def test_la_tabla_de_usuarios_sobrevive_a_los_intentos(self, cliente, crear_cuenta):
        crear_cuenta()
        antes = _contar_usuarios()

        for carga in CARGAS:
            cliente.post(LOGIN, json={"identificador": carga, "password": carga})
            cliente.post(LOGIN, json={"identificador": "supervisor", "password": carga})

        assert _contar_usuarios() == antes

    def test_el_sistema_sigue_funcionando_despues_de_los_ataques(
        self, cliente, crear_cuenta
    ):
        cuenta = crear_cuenta()

        for carga in CARGAS:
            cliente.post(LOGIN, json={"identificador": carga, "password": carga})

        respuesta = cliente.post(
            LOGIN, json={"identificador": cuenta["usuario"], "password": cuenta["password"]}
        )

        assert respuesta.status_code == 200
        token = respuesta.json()["access_token"]
        assert cliente.get(ME, headers={"Authorization": f"Bearer {token}"}).status_code == 200

    def test_un_identificador_gigante_no_derriba_el_servicio(self, cliente, crear_cuenta):
        crear_cuenta()

        respuesta = cliente.post(LOGIN, json={"identificador": "A" * 10000, "password": "x"})

        assert respuesta.status_code == 422

    def test_los_caracteres_nulos_son_rechazados(self, cliente, crear_cuenta):
        crear_cuenta()

        respuesta = cliente.post(
            LOGIN, json={"identificador": "admin\0", "password": "ClaveSegura123"}
        )

        assert respuesta.status_code == 422


class TestInyeccionEnElRegistro:
    @pytest.mark.parametrize(
        "campo, valor",
        [
            ("usuario", "admin'; DROP TABLE usuarios; --"),
            ("usuario", "' OR 1=1 --"),
            ("nombre", "Ana'; DELETE FROM usuarios; --"),
            ("apellido", "Perez' OR '1'='1"),
            ("correo", "a@b.com'; DROP TABLE usuarios; --"),
            ("cedula", "V-12345678'; DROP TABLE usuarios; --"),
        ],
    )
    def test_los_datos_maliciosos_son_rechazados(self, cliente, crear_cuenta, token_de, campo, valor):
        admin = crear_cuenta(usuario="jefe", rol="admin")
        payload = {
            "cedula": "V-12345678",
            "nombre": "Ana",
            "apellido": "Perez",
            "usuario": "supervisor",
            "correo": "supervisor@ferreteria.test",
            "password": "ClaveSegura123",
            "rol": "ventas",
        }
        payload[campo] = valor

        respuesta = cliente.post(
            REGISTRO,
            json=payload,
            headers={"Authorization": f"Bearer {token_de(admin)}"},
        )

        assert respuesta.status_code == 422
        assert _contar_usuarios() == 1

    def test_las_tablas_siguen_intactas_tras_los_intentos(self, cliente, crear_cuenta):
        crear_cuenta()

        respuesta = cliente.get("/salud")

        assert respuesta.status_code == 200
        assert respuesta.json()["bases"]["ferreteria_usuarios"] == "operativa"


class TestPrivilegiosDelRolDeLaAplicacion:
    """Segunda capa: aunque se colara SQL, el rol no puede hacer dano."""

    @pytest.fixture
    def conexion(self):
        conexion = psycopg2.connect(get_settings().database_url_usuarios)
        conexion.autocommit = True
        yield conexion
        conexion.close()

    def test_no_puede_borrar_una_tabla(self, conexion):
        with pytest.raises(psycopg2.Error, match="permission denied|must be owner"):
            with conexion.cursor() as cur:
                cur.execute("DROP TABLE usuarios")

    def test_no_puede_crear_tablas(self, conexion):
        with pytest.raises(psycopg2.Error, match="permission denied"):
            with conexion.cursor() as cur:
                cur.execute("CREATE TABLE infiltrada (id int)")

    def test_no_puede_borrar_la_bitacora(self, conexion):
        with pytest.raises(psycopg2.Error):
            with conexion.cursor() as cur:
                cur.execute("DELETE FROM bitacora")

    def test_no_puede_alterar_la_bitacora(self, conexion):
        with pytest.raises(psycopg2.Error):
            with conexion.cursor() as cur:
                cur.execute("UPDATE bitacora SET accion = 'alterado'")

    def test_no_puede_eliminar_usuarios(self, conexion):
        with pytest.raises(psycopg2.Error, match="permission denied"):
            with conexion.cursor() as cur:
                cur.execute("DELETE FROM usuarios")

    def test_no_puede_cambiar_los_roles_del_sistema(self, conexion):
        with pytest.raises(psycopg2.Error, match="permission denied"):
            with conexion.cursor() as cur:
                cur.execute("UPDATE rol SET nombre = 'superadmin'")

    def test_no_es_superusuario(self, conexion):
        with conexion.cursor() as cur:
            cur.execute("SELECT current_user, (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)")
            usuario_actual, es_super = cur.fetchone()

        assert usuario_actual == "app_ferreteria"
        assert es_super is False
