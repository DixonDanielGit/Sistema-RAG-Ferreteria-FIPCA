"""Verificacion estatica del endurecimiento de Docker (Semana 1).

No requiere Docker en ejecucion: revisa docker-compose.yml y .dockerignore
para evitar que una configuracion insegura vuelva al repositorio.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
COMPOSE_TEXTO = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")


def test_imagenes_con_version_fijada():
    imagenes = re.findall(r"^\s*image:\s*(\S+)", COMPOSE_TEXTO, re.MULTILINE)

    assert len(imagenes) == 2, f"Se esperaban 2 imagenes, se encontraron {imagenes}"
    for imagen in imagenes:
        assert ":" in imagen, f"{imagen} no tiene tag"
        tag = imagen.rsplit(":", 1)[1]
        assert tag != "latest", f"{imagen} usa 'latest': builds no reproducibles"
        assert re.match(r"\d", tag), f"{imagen} no fija version numerica"


def test_puertos_publicados_solo_en_loopback():
    mapeos = re.findall(r'^\s*-\s*"([^"]+)"\s*$', COMPOSE_TEXTO, re.MULTILINE)
    publicados = [m for m in mapeos if ":5432" in m or ":80" in m]

    assert publicados, "No se encontraron mapeos de puertos"
    for mapeo in publicados:
        assert "127.0.0.1" in mapeo or "${BIND_ADDRESS" in mapeo, (
            f"El puerto {mapeo} queda expuesto en todas las interfaces"
        )


def test_no_new_privileges_en_ambos_servicios():
    assert COMPOSE_TEXTO.count("no-new-privileges:true") == 2


def test_ningun_contenedor_privilegiado():
    assert not re.search(r"privileged:\s*true", COMPOSE_TEXTO)


def test_init_sql_montado_en_solo_lectura():
    linea = next(
        (l for l in COMPOSE_TEXTO.splitlines() if "init.sql" in l and "docker-entrypoint" in l),
        None,
    )
    assert linea is not None, "init.sql no esta montado como script de inicializacion"
    assert linea.rstrip().endswith(":ro"), "init.sql debe montarse en modo solo lectura"


def test_sin_clave_version_obsoleta():
    assert not re.search(r"^version:", COMPOSE_TEXTO, re.MULTILINE)


def test_contrasenas_no_incrustadas_en_compose():
    for variable in ("POSTGRES_PASSWORD", "PGADMIN_DEFAULT_PASSWORD"):
        assert re.search(
            rf"{variable}:\s*\$\{{{variable}\}}", COMPOSE_TEXTO
        ), f"{variable} debe venir de .env, no estar escrita en el compose"


def test_healthchecks_definidos():
    assert COMPOSE_TEXTO.count("healthcheck:") == 2


def test_dockerignore_existe_y_excluye_secretos():
    dockerignore = RAIZ / ".dockerignore"
    assert dockerignore.is_file(), "Falta .dockerignore"

    contenido = dockerignore.read_text(encoding="utf-8")
    for patron in (".env", "venv/", "__pycache__/", "uploads/"):
        assert patron in contenido, f".dockerignore no excluye {patron}"


def test_dockerfile_no_copia_secretos():
    """El Dockerfile aun esta vacio; cuando exista, no debe copiar .env."""
    dockerfile = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
    if not dockerfile.strip():
        pytest.skip("Dockerfile aun no implementado (Semana 8)")

    assert ".env" not in dockerfile
