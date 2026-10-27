-- =====================================================================
-- FERRE-INVERSIONES PEREZ C.A.
-- Sistema Web de Gestion de Inventario e Inteligencia Artificial RAG
--
-- Inicializacion de las dos bases de datos definidas en el MER:
--   1) ferreteria_rag      -> catalogo de productos e insumos del motor RAG
--   2) ferreteria_usuarios -> usuarios, roles y bitacora de auditoria
--
-- IMPORTANTE: este script es ejecutado por la imagen oficial de PostgreSQL
-- unicamente cuando el volumen "postgres_data" se crea por primera vez.
-- Para reaplicarlo: docker compose down -v && docker compose up -d
-- =====================================================================

-- =====================================================================
-- 1. CREACION DE LAS DOS BASES DE DATOS
--    (psql ejecuta en autocommit, por eso CREATE DATABASE es valido aqui)
-- =====================================================================

CREATE DATABASE ferreteria_rag;
CREATE DATABASE ferreteria_usuarios;


-- =====================================================================
-- 1.b ROL DE APLICACION CON MINIMO PRIVILEGIO (RNF-02)
--     La API nunca se conecta con la cuenta de superusuario: usa
--     "app_ferreteria", que solo puede leer y escribir datos. No puede
--     crear, alterar ni eliminar objetos, ni cambiar permisos.
--     La contrasena llega por variable de entorno desde .env y no se
--     escribe en el repositorio.
-- =====================================================================

\set app_password `printf '%s' "${APP_DB_PASSWORD:-}"`
\set app_password_valida `[ ${#APP_DB_PASSWORD} -ge 16 ] && echo 1 || echo 0`

\if :app_password_valida
\else
\echo '*** ERROR: APP_DB_PASSWORD no definida o con menos de 16 caracteres ***'
\quit 1
\endif

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ferreteria') THEN
        CREATE ROLE app_ferreteria LOGIN
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
END
$$;

ALTER ROLE app_ferreteria WITH PASSWORD :'app_password';

-- Limites defensivos: una consulta lenta no puede bloquear el servicio.
ALTER ROLE app_ferreteria SET statement_timeout = '15s';
ALTER ROLE app_ferreteria SET idle_in_transaction_session_timeout = '30s';


-- =====================================================================
-- 2. BASE DE DATOS PRINCIPAL: ferreteria_rag
--    Contiene el catalogo que consume el motor RAG.
-- =====================================================================

\connect ferreteria_rag

-- Extension de vectores: solo se instala en la base que la utiliza.
CREATE EXTENSION IF NOT EXISTS vector;

-- Extension para busqueda rapida por texto (RF-04.3).
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Tabla: archivos_subidos
-- Registra cada catalogo de proveedor procesado por el motor ETL.
CREATE TABLE archivos_subidos (
    id_archivo SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    tipo VARCHAR(100) NOT NULL,
    fecha_de_subida TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ruta TEXT,
    hash_sha256 CHAR(64),
    tamano_bytes BIGINT NOT NULL DEFAULT 0
        CONSTRAINT chk_archivos_tamano CHECK (tamano_bytes >= 0),
    estado VARCHAR(20) NOT NULL DEFAULT 'pendiente'
        CONSTRAINT chk_archivos_estado
        CHECK (estado IN ('pendiente', 'procesando', 'ok', 'parcial', 'error')),
    filas_ok INT NOT NULL DEFAULT 0
        CONSTRAINT chk_archivos_filas_ok CHECK (filas_ok >= 0),
    filas_error INT NOT NULL DEFAULT 0
        CONSTRAINT chk_archivos_filas_error CHECK (filas_error >= 0),
    detalle TEXT,
    id_usuario INT,
    terminado_en TIMESTAMPTZ
);

CREATE INDEX idx_archivos_hash ON archivos_subidos (hash_sha256);
CREATE INDEX idx_archivos_fecha ON archivos_subidos (fecha_de_subida DESC);

-- Tabla: proveedores
CREATE TABLE proveedores (
    id_proveedores SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    direccion TEXT,
    vendedor VARCHAR(255)
);

-- Tabla: categoria
CREATE TABLE categoria (
    id_categoria SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

-- Tabla: productos
-- Campos tecnicos del RF-04.2. IVA fijo en 16% y stock por defecto en 0.
CREATE TABLE productos (
    id SERIAL PRIMARY KEY,
    id_archivo INT,
    id_proveedor INT,
    id_categoria INT,
    codigo VARCHAR(50) UNIQUE,
    nombre VARCHAR(255) NOT NULL,
    marca VARCHAR(100),
    precio NUMERIC(10, 2) NOT NULL CHECK (precio >= 0),
    IVA NUMERIC(5, 2) NOT NULL DEFAULT 16.00 CHECK (IVA = 16.00),
    descuentos NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (descuentos >= 0),
    descripcion TEXT,
    stock INT NOT NULL DEFAULT 0 CHECK (stock >= 0),
    descripcion_vectorial vector(384),

    CONSTRAINT fk_productos_archivo
        FOREIGN KEY (id_archivo) REFERENCES archivos_subidos(id_archivo)
        ON DELETE SET NULL,
    CONSTRAINT fk_productos_proveedor
        FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedores)
        ON DELETE SET NULL,
    CONSTRAINT fk_productos_categoria
        FOREIGN KEY (id_categoria) REFERENCES categoria(id_categoria)
        ON DELETE SET NULL
);

-- Busqueda rapida por nombre, marca y descripcion (RF-04.3).
CREATE INDEX idx_productos_nombre_trgm
    ON productos USING gin (nombre gin_trgm_ops);
CREATE INDEX idx_productos_marca_trgm
    ON productos USING gin (marca gin_trgm_ops);
CREATE INDEX idx_productos_descripcion_trgm
    ON productos USING gin (descripcion gin_trgm_ops);

-- Busqueda vectorial por distancia de coseno (RF-03.2, Semana 4).
CREATE INDEX idx_productos_descripcion_vectorial
    ON productos USING hnsw (descripcion_vectorial vector_cosine_ops);

-- Permisos del rol de aplicacion en esta base: solo datos, nunca estructura.
GRANT CONNECT ON DATABASE ferreteria_rag TO app_ferreteria;
GRANT USAGE ON SCHEMA public TO app_ferreteria;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON archivos_subidos, proveedores, categoria, productos
    TO app_ferreteria;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_ferreteria;

COMMENT ON DATABASE ferreteria_rag IS
    'Catalogo de productos, proveedores y categorias del sistema RAG';


-- =====================================================================
-- 3. BASE DE DATOS DE USUARIOS: ferreteria_usuarios
--    Autenticacion, roles y bitacora inmutable de auditoria.
-- =====================================================================

\connect ferreteria_usuarios

-- Tabla: rol (RF-01.2)
CREATE TABLE rol (
    id_rol SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion TEXT
);

-- Semilla minima: sin estos roles el login no puede asignar permisos.
INSERT INTO rol (nombre, descripcion) VALUES
    ('admin', 'Acceso total: inventario, usuarios, bitacora e ingesta ETL'),
    ('ventas', 'Consulta de productos, chat RAG y disponibilidad')
ON CONFLICT (nombre) DO NOTHING;

-- Tabla: usuarios
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    id_rol INT NOT NULL,
    cedula VARCHAR(20) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    usuario VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    correo VARCHAR(255) NOT NULL UNIQUE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT fk_usuarios_rol
        FOREIGN KEY (id_rol) REFERENCES rol(id_rol)
        ON DELETE RESTRICT
);

-- Tabla: tokens_recuperacion
-- Recuperacion de contrasena por correo (Adenda 1, Semana 2.5).
-- Se guarda el SHA-256 del token, nunca el token en claro: quien lea la tabla
-- no puede reconstruir el enlace. Un token es de un solo uso y caduca.
CREATE TABLE tokens_recuperacion (
    id SERIAL PRIMARY KEY,
    id_usuario INT NOT NULL,
    token_hash CHAR(64) NOT NULL UNIQUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expira_en TIMESTAMPTZ NOT NULL,
    usado_en TIMESTAMPTZ,

    CONSTRAINT fk_tokens_usuario
        FOREIGN KEY (id_usuario) REFERENCES usuarios(id)
        ON DELETE CASCADE,
    CONSTRAINT chk_tokens_vigencia
        CHECK (expira_en > creado_en)
);

-- Busqueda del token por su hash (unico) y limpieza por usuario.
CREATE INDEX idx_tokens_usuario ON tokens_recuperacion (id_usuario);
CREATE INDEX idx_tokens_expira ON tokens_recuperacion (expira_en);

-- Tabla: bitacora (RF-05)
-- id_usuario admite NULL para poder auditar intentos de login fallidos
-- con un usuario inexistente. Es inmutable: no se permite UPDATE/DELETE.
CREATE TABLE bitacora (
    id_bitacora SERIAL PRIMARY KEY,
    id_usuario INT,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    hora TIME NOT NULL DEFAULT CURRENT_TIME,
    accion TEXT NOT NULL CHECK (length(trim(accion)) > 0),
    ip VARCHAR(45),
    modulo VARCHAR(50),

    CONSTRAINT fk_bitacora_usuario
        FOREIGN KEY (id_usuario) REFERENCES usuarios(id)
        ON DELETE RESTRICT
);

-- Filtros del visor de auditoria (RF-05.2).
CREATE INDEX idx_bitacora_fecha ON bitacora (fecha);
CREATE INDEX idx_bitacora_usuario ON bitacora (id_usuario);
CREATE INDEX idx_bitacora_modulo ON bitacora (modulo);

-- Funcion que garantiza la inmutabilidad de la bitacora.
CREATE OR REPLACE FUNCTION fn_bitacora_inmutable()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'La bitacora es inmutable: operacion % no permitida', TG_OP;
END;
$$;

CREATE TRIGGER trg_bitacora_inmutable
    BEFORE UPDATE OR DELETE ON bitacora
    FOR EACH ROW EXECUTE FUNCTION fn_bitacora_inmutable();

-- TRUNCATE no dispara triggers de fila: se bloquea a nivel de sentencia.
CREATE TRIGGER trg_bitacora_no_truncate
    BEFORE TRUNCATE ON bitacora
    FOR EACH STATEMENT EXECUTE FUNCTION fn_bitacora_inmutable();

COMMENT ON DATABASE ferreteria_usuarios IS
    'Usuarios, roles y bitacora de auditoria del sistema';

-- =====================================================================
-- 4. PERMISOS DEL ROL DE APLICACION EN ferreteria_usuarios
--    La bitacora solo admite INSERT y SELECT: ni UPDATE ni DELETE,
--    ni siquiera para el usuario con el que corre la API.
-- =====================================================================

GRANT CONNECT ON DATABASE ferreteria_usuarios TO app_ferreteria;
GRANT USAGE ON SCHEMA public TO app_ferreteria;

-- Roles: solo lectura. Los roles del sistema no se editan en caliente.
GRANT SELECT ON rol TO app_ferreteria;

-- Usuarios: alta y modificacion. Sin DELETE: las cuentas se desactivan
-- (activo = FALSE) para conservar la trazabilidad de la auditoria.
GRANT SELECT, INSERT, UPDATE ON usuarios TO app_ferreteria;

-- Tokens de recuperacion: se consultan, se crean y se marcan como usados.
-- No se concede DELETE: la API nunca borra un token, lo invalida con un
-- UPDATE (usado_en) para conservar el rastro.
GRANT SELECT, INSERT, UPDATE ON tokens_recuperacion TO app_ferreteria;

-- Bitacora: solo insercion y consulta. La inmutabilidad se garantiza en
-- dos capas: permisos y trigger.
GRANT SELECT, INSERT ON bitacora TO app_ferreteria;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_ferreteria;
