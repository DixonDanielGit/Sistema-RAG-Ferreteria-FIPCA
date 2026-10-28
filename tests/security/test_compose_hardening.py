"""Verificacion estatica del endurecimiento de Docker.
No requiere Docker en ejecucion: revisa docker-compose.yml, el Dockerfile y
.dockerignore para evitar que una configuracion insegura vuelva al repositorio.
Cubre la infraestructura de la Semana 1 y la imagen de la API de la Adenda 1.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
COMPOSE_TEXTO = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
DOCKERFILE_TEXTO = (RAIZ / "Dockerfile").read_text(encoding="utf-8")

def _bloque_servicio(nombre: str) -> str:
    """Devuelve el texto del servicio indicado dentro del compose."""
    patron = rf"^  {nombre}:\n(.*?)(?=^  [a-z]+:|\Z)"
    coincidencia = re.search(patron, COMPOSE_TEXTO, re.MULTILINE | re.DOTALL)
    assert coincidencia, f"No se encontro el servicio '{nombre}' en docker-compose.yml"
    return coincidencia.group(1)


def test_imagenes_con_version_fijada():
    imagenes = re.findall(r"^\s*image:\s*(\S+)", COMPOSE_TEXTO, re.MULTILINE)

    assert len(imagenes) == 3, f"Se esperaban 3 imagenes, se encontraron {imagenes}"
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


def test_no_new_privileges_en_todos_los_servicios():
    assert COMPOSE_TEXTO.count("no-new-privileges:true") == 3


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

    # La contrasena del rol de aplicacion tambien entra por entorno.
    assert "${APP_DB_PASSWORD}" in COMPOSE_TEXTO


def test_healthchecks_definidos():
    # db y pgadmin lo declaran en el compose; la API lo trae en su imagen.
    assert COMPOSE_TEXTO.count("healthcheck:") == 2
    assert "HEALTHCHECK" in DOCKERFILE_TEXTO


def test_api_espera_a_la_base_sana():
    api = _bloque_servicio("api")
    assert "depends_on:" in api
    assert "condition: service_healthy" in api


def test_api_con_sistema_de_archivos_solo_lectura():
    api = _bloque_servicio("api")
    assert "read_only: true" in api
    assert "tmpfs:" in api
    assert "/tmp" in api


def test_imagen_api_no_corre_como_root():
    assert re.search(r"useradd[^\n]*--uid\s+10001", DOCKERFILE_TEXTO), (
        "El Dockerfile debe crear un usuario sin privilegios con uid fijo"
    )
    assert re.search(r"^USER\s+(?!root\b)\S+", DOCKERFILE_TEXTO, re.MULTILINE), (
        "El Dockerfile debe cambiar a un usuario sin privilegios antes del CMD"
    )


def test_dockerignore_existe_y_excluye_secretos():
    dockerignore = RAIZ / ".dockerignore"
    assert dockerignore.is_file(), "Falta .dockerignore"

    contenido = dockerignore.read_text(encoding="utf-8")
    for patron in (".env", "venv/", "__pycache__/", "uploads/"):
        assert patron in contenido, f".dockerignore no excluye {patron}"


def test_dockerfile_no_copia_secretos():
    """La imagen no debe arrastrar credenciales ni el contexto completo."""
    assert not re.search(
        r"^(COPY|ADD)\s+[^\n]*(\.env|venv/|uploads/|\.git)", DOCKERFILE_TEXTO, re.MULTILINE
    ), "El Dockerfile copia archivos sensibles al contexto de la imagen"

    assert not re.search(r"^(COPY|ADD)\s+\.\s+\.", DOCKERFILE_TEXTO, re.MULTILINE), (
        "Evita copiar todo el contexto: el .dockerignore es la unica barrera"
    )
