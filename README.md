# Sistema Web de Gestión de Inventario e IA RAG

Aplicación web para **FERRE-INVERSIONES PEREZ C.A.** que combina gestión de
inventario con un asistente basado en RAG (Retrieval-Augmented Generation)
sobre el catálogo real de productos.

- **Backend:** Python 3.11+ / FastAPI / Uvicorn / Pydantic
- **Base de datos:** PostgreSQL 16 + `pgvector`
- **Frontend:** Jinja2 + Bootstrap 5 + JavaScript vanilla (fetch/AJAX)
- **IA:** modelo de embeddings + modelo generativo (Semana 4/5)
- **Infraestructura:** Docker + Docker Compose

> Estado actual: **Semana 2 completada** (infraestructura, base de datos,
> autenticación JWT y auditoría). Las semanas 3 a 8 añaden ETL, vectores,
> RAG, interfaz y despliegue.

## Requisitos

- Docker Desktop con Docker Compose
- Python 3.11 o superior
- Git

## Puesta en marcha

```bash
# 1. Crear la configuración local a partir de la plantilla
cp .env.example .env
#    Edita .env y cambia TODAS las contraseñas y JWT_SECRET por valores propios

# 2. Instalar dependencias en el entorno virtual
python -m venv venv
venv\Scripts\activate            # Windows
source venv/bin/activate         # Linux / WSL / macOS
pip install -r requirements.txt

# 3. Levantar PostgreSQL + pgAdmin
docker compose up -d

# 4. Arrancar la API
uvicorn app.main:app --reload
```

| Servicio | URL | Credenciales |
|---|---|---|
| API (Swagger UI) | http://localhost:8000/docs | — |
| Estado del servicio | http://localhost:8000/salud | — |
| pgAdmin | http://localhost:8080 | `PGADMIN_DEFAULT_*` de `.env` |
| PostgreSQL | `localhost:5432` | `POSTGRES_*` de `.env` |

Generar un `JWT_SECRET` propio:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Crear la primera cuenta

Mientras no exista ningún usuario, el alta está abierta: la primera cuenta
**debe** ser administradora (es el arranque del sistema). Después, solo un
administrador autenticado puede registrar cuentas.

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "cedula": "V-12345678",
    "nombre": "Dixon",
    "apellido": "Bastias",
    "usuario": "admin",
    "correo": "admin@ferreteria.com",
    "password": "ClaveSegura2026",
    "rol": "admin"
  }'
```

### Iniciar sesión

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identificador": "admin", "password": "ClaveSegura2026"}'
```

La respuesta trae `access_token`. Para usarlo:

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

En Swagger UI también puedes pulsar **Authorize** y pegar el token.

## Endpoints de la API

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| POST | `/api/v1/auth/login` | público | Valida credenciales y entrega un JWT |
| POST | `/api/v1/auth/register` | admin (o público si no hay cuentas) | Alta de usuarios |
| GET | `/api/v1/auth/me` | autenticado | Datos de la cuenta actual |
| POST | `/api/v1/auth/logout` | autenticado | Registra el cierre de sesión |
| GET | `/api/v1/auth/roles` | admin | Catálogo de roles |
| GET | `/salud` | público | Estado de las bases de datos |
| GET | `/docs` | público | Documentación interactiva |

Reglas de autenticación:

- El JWT expira a los `JWT_EXPIRACION_MINUTOS` (30 por defecto). Ese plazo
  implementa el cierre de sesión por inactividad (RF-01.3).
- El token incluye el rol; cada ruta decide el permiso (`admin` / `ventas`).
- La cuenta se relee de la base en cada petición: desactivar un usuario
  invalida sus tokens de inmediato.

### Conectar pgAdmin a PostgreSQL

pgAdmin corre en otro contenedor, por lo que **no** debe usarse `localhost`
como host:

1. Abre http://localhost:8080 e inicia sesión.
2. Clic derecho en **Servers → Register → Server…**
3. **General** → Name: `Ferreteria`.
4. **Connection**:
   - Host: `db`
   - Port: `5432`
   - Maintenance database: `ferreteria`
   - Username / Password: los de `.env`
5. Guarda y despliega `ferreteria_rag` o `ferreteria_usuarios`.

Para ver el MER: clic derecho sobre una base → **ERD For Database**.

## Bases de datos

El esquema se define en `init.sql` y crea dos bases:

| Base | Tablas | Uso |
|---|---|---|
| `ferreteria_rag` | `archivos_subidos`, `proveedores`, `categoria`, `productos` | Catálogo e insumos del motor RAG (incluye `descripcion_vectorial vector(1536)` e índice HNSW) |
| `ferreteria_usuarios` | `rol`, `usuarios`, `bitacora` | Autenticación, roles y auditoría inmutable |
| `ferreteria` | — | Base de mantenimiento (la usa pgAdmin para conectarse) |

### Dos roles de base de datos

| Rol | Uso | Privilegios |
|---|---|---|
| `admin_ferreteria` | Administración y tareas puntuales | Superusuario |
| `app_ferreteria` | **La API** | Solo datos: `SELECT/INSERT/UPDATE/DELETE` en el catálogo, `SELECT/INSERT` en la bitácora. Sin `CREATE`, sin `DELETE` de usuarios, sin acceso a la estructura |

La contraseña de `app_ferreteria` se define en `APP_DB_PASSWORD` (`.env`) y
`init.sql` la aplica al crear el volumen. La API nunca usa la cuenta de
superusuario.

### Recrear el esquema

`init.sql` solo se ejecuta cuando el volumen `postgres_data` se crea por
primera vez. Para volver a aplicarlo:

```bash
docker compose down -v   # ¡elimina todos los datos!
docker compose up -d
```

## Pruebas

```bash
pytest -q
```

| Carpeta | Contenido |
|---|---|
| `unit/` | Caja blanca: esquema SQL, hashing de contraseñas, JWT |
| `integration/` | Caja negra: login, registro, roles, auditoría |
| `boundary/` | Valores límite: expiración exacta del JWT |
| `security/` | Inyección SQL, permisos de BD, endurecimiento de Docker |
| `stress/` | Carga masiva de catálogos (Semana 3) |

Resultado actual:

```text
230 passed, 1 skipped
```

Las pruebas de integración **no tocan las bases de desarrollo**: al iniciar la
sesión clonan `ferreteria_rag` y `ferreteria_usuarios` como
`ferreteria_rag_test` y `ferreteria_usuarios_test`, y las eliminan al terminar.
Si PostgreSQL no responde, esas pruebas se omiten en lugar de fallar.

> Si pgAdmin tiene sesiones abiertas sobre las bases, PostgreSQL no permite
> clonarlas. En ese caso cierra las pestañas de consulta en pgAdmin y vuelve a
> ejecutar las pruebas.

## Estructura del proyecto

```text
app/                Código del backend (FastAPI)
  api/v1/           Rutas REST (/api/v1/...)
  core/             Seguridad, JWT y auditoría
  db/               Pools de conexión a PostgreSQL
  models/           Acceso a datos (SQL parametrizado)
  schemas/          DTOs de Pydantic
  services/         ETL, embeddings, búsqueda vectorial y LLM
  static/           CSS y JS
templates/          Vistas Jinja2
tests/              Suite de pruebas
init.sql            Esquema de las dos bases
docker-compose.yml  PostgreSQL + pgAdmin
docs/actas/         Actas de entrega semanales
```

## Seguridad aplicada

- Contraseñas **fuera del repositorio** (`.env` ignorado por Git).
- Contraseñas con **scrypt** (16 MiB de costo por verificación) y sal aleatoria;
  nunca se guardan ni se registran en claro.
- JWT firmado con **HS256** y secreto de 48 bytes; sin secreto válido la
  aplicación no arranca.
- **Consultas parametrizadas** en todo el acceso a datos (anti-SQL Injection).
- Validación estricta de entrada con Pydantic (`extra="forbid"`).
- Rol de base de datos de **mínimo privilegio** para la API.
- Bitácora **inmutable**: solo `INSERT` y `SELECT`; los triggers bloquean
  `UPDATE`, `DELETE` y `TRUNCATE` incluso para el propietario.
- Puertos publicados solo en `127.0.0.1` (cambia `BIND_ADDRESS` para un VPS).
- `no-new-privileges` en ambos contenedores e imágenes con versión fija.

## Problemas frecuentes

| Síntoma | Causa / solución |
|---|---|
| pgAdmin no conecta con host `localhost` | Usa `db` (nombre del servicio) |
| Solo aparece la base `ferreteria` | El volumen es antiguo: `docker compose down -v && docker compose up -d` |
| Cambios en `init.sql` no se aplican | El script solo corre con volumen nuevo |
| `Configuracion invalida: Falta JWT_SECRET` | Copia `.env.example` a `.env` y define los valores |
| `password authentication failed for user "app_ferreteria"` | Recrea el volumen para que `init.sql` aplique `APP_DB_PASSWORD` |
| Las pruebas de integración se omiten | PostgreSQL apagado o pgAdmin con sesiones abiertas sobre las bases |
| `docker: command not found` en WSL | Activa la integración WSL 2 en Docker Desktop o usa PowerShell |
| Puerto 5432/8000/8080 ocupado | Cambia `POSTGRES_HOST_PORT` / usa otro `--port` / `PGADMIN_HOST_PORT` |

## Documentación del proyecto

- `prompts/requisitos_funcionales_y_no_funcionales_del_sistema.md`
- `prompts/lista_de_tareas_y_checklist_de_ejecucion_del_proyecto.md`
- `prompts/estructura_y_arquitectura_del_proyecto.md`
- `docs/actas/` — actas de entrega
