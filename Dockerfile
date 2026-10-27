# Imagen de la API (Semana 4: ingesta ETL y embeddings locales).
#
# Se construye con el servicio de ingesta y su almacenamiento persistente:
#   docker compose build api
#   docker compose up -d api
#
# La configuracion (DSN, JWT_SECRET, SMTP, URL_BASE) llega por variables de
# entorno desde docker-compose.yml; no se copia ningun .env a la imagen.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Las dependencias se copian solas para aprovechar la cache de capas: cambiar
# el codigo no obliga a reinstalar paquetes.
COPY requirements.txt requirements-embeddings.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-embeddings.txt

# Codigo, plantillas y estaticos. El entrypoint resuelve las plantillas en la
# raiz del proyecto (/app/templates) y los estaticos dentro del paquete.
COPY app ./app
COPY templates ./templates
COPY scripts ./scripts

# Usuario sin privilegios: los originales solo se escriben en el volumen de
# ingestas; el resto del sistema de archivos permanece en solo lectura.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin ferreteria \
    && mkdir -p /app/uploads /app/model-cache \
    && chown -R ferreteria:ferreteria /app

USER ferreteria

EXPOSE 8000

# /salud comprueba las dos bases; si alguna no responde, el contenedor se marca
# como no saludable y Docker puede reiniciarlo.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/salud', timeout=4).read()"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
