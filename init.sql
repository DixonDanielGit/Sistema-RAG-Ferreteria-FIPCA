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
    id_proveedor INT,
    vendedor_nombre VARCHAR(255),
    vendedor_telefono VARCHAR(40),
    vendedor_correo VARCHAR(255),
    moneda CHAR(3) NOT NULL DEFAULT 'USD',
    nota_proveedor TEXT,
    terminado_en TIMESTAMPTZ,
    -- Markdown del catalogo: original .md o conversion de MarkItDown
    -- (RF-02.4, migracion 10_0); puede ser NULL si no se pudo leer.
    contenido_markdown TEXT
);

CREATE INDEX idx_archivos_hash ON archivos_subidos (hash_sha256);
CREATE INDEX idx_archivos_fecha ON archivos_subidos (fecha_de_subida DESC);

-- Tabla: proveedores
-- Identidad, contacto y condiciones comerciales (migracion 7_0). El plazo
-- de entrega es la promesa del proveedor; las compras reales lo contrastan.
CREATE TABLE proveedores (
    id_proveedores SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    rif VARCHAR(20),
    direccion TEXT,
    telefono VARCHAR(40),
    correo VARCHAR(255),
    vendedor VARCHAR(255),
    telefono_vendedor VARCHAR(40),
    correo_vendedor VARCHAR(255),
    moneda CHAR(3) NOT NULL DEFAULT 'USD',
    plazo_entrega_dias SMALLINT
        CONSTRAINT chk_proveedores_plazo
        CHECK (plazo_entrega_dias IS NULL OR plazo_entrega_dias >= 0),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Evita proveedores duplicados por diferencias de mayusculas.
CREATE UNIQUE INDEX uq_proveedores_nombre_lower
    ON proveedores (LOWER(nombre));

ALTER TABLE archivos_subidos
    ADD CONSTRAINT fk_archivos_proveedor
    FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedores)
    ON DELETE SET NULL;

CREATE INDEX idx_archivos_proveedor
    ON archivos_subidos (id_proveedor, fecha_de_subida DESC);

-- Tabla: categoria
-- Admite jerarquia (id_padre) y sinonimos para ampliar la busqueda sin
-- inventar productos.
CREATE TABLE categoria (
    id_categoria SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    id_padre INT,
    sinonimos TEXT,

    CONSTRAINT fk_categoria_padre
        FOREIGN KEY (id_padre) REFERENCES categoria(id_categoria)
        ON DELETE SET NULL
);

-- Tabla: productos
-- Campos tecnicos del RF-04.2. IVA fijo en 16% y stock por defecto en 0.
-- Las columnas de la migracion 7_0 describen moneda, presentacion, politica
-- de reorden y el estado del vector; el ETL actual las deja en su valor por
-- defecto y siguen siendo validas.
CREATE TABLE productos (
    id SERIAL PRIMARY KEY,
    id_archivo INT,
    id_proveedor INT,
    id_categoria INT,
    codigo VARCHAR(50) UNIQUE,
    codigo_interno VARCHAR(50),
    nombre VARCHAR(255) NOT NULL,
    marca VARCHAR(100),
    precio NUMERIC(10, 2) NOT NULL CHECK (precio >= 0),
    moneda CHAR(3) NOT NULL DEFAULT 'USD',
    IVA NUMERIC(5, 2) NOT NULL DEFAULT 16.00 CHECK (IVA = 16.00),
    descuentos NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (descuentos >= 0),
    descripcion TEXT,
    unidad_medida VARCHAR(30),
    presentacion VARCHAR(120),
    stock INT NOT NULL DEFAULT 0 CHECK (stock >= 0),
    punto_reorden INT
        CONSTRAINT chk_productos_punto_reorden
        CHECK (punto_reorden IS NULL OR punto_reorden >= 0),
    ubicacion VARCHAR(80),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    descripcion_vectorial vector(384),
    modelo_embedding VARCHAR(80),
    vectorizado_en TIMESTAMPTZ,
    -- Texto indexado del Buscador Comercial (migracion 9_0): se recalcula
    -- solo con el diccionario espanol y nunca se escribe a mano.
    texto_busqueda tsvector
        GENERATED ALWAYS AS (
            to_tsvector(
                'spanish'::regconfig,
                coalesce(nombre, '') || ' ' ||
                coalesce(codigo, '') || ' ' ||
                coalesce(codigo_interno, '') || ' ' ||
                coalesce(marca, '') || ' ' ||
                coalesce(descripcion, '') || ' ' ||
                coalesce(presentacion, '') || ' ' ||
                coalesce(unidad_medida, '') || ' ' ||
                coalesce(ubicacion, '')
            )
        ) STORED,

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

-- Codigo interno de la ferreteria: unico solo cuando esta informado.
CREATE UNIQUE INDEX uq_productos_codigo_interno
    ON productos (codigo_interno)
    WHERE codigo_interno IS NOT NULL;

-- Filtros del asistente por proveedor y categoria.
CREATE INDEX idx_productos_proveedor ON productos (id_proveedor);
CREATE INDEX idx_productos_categoria ON productos (id_categoria);

-- Reconciliacion de la vectorizacion: encontrar rapido lo que falta.
CREATE INDEX idx_productos_sin_vector
    ON productos (id)
    WHERE descripcion_vectorial IS NULL;

-- Busqueda rapida por nombre, marca y descripcion (RF-04.3).
CREATE INDEX idx_productos_nombre_trgm
    ON productos USING gin (nombre gin_trgm_ops);
CREATE INDEX idx_productos_marca_trgm
    ON productos USING gin (marca gin_trgm_ops);
CREATE INDEX idx_productos_descripcion_trgm
    ON productos USING gin (descripcion gin_trgm_ops);

-- Busqueda por coincidencia parcial en codigo, proveedor y categoria
-- (Buscador Comercial, migracion 9_0).
CREATE INDEX idx_productos_codigo_trgm
    ON productos USING gin (codigo gin_trgm_ops);
CREATE INDEX idx_proveedores_nombre_trgm
    ON proveedores USING gin (nombre gin_trgm_ops);
CREATE INDEX idx_categoria_nombre_trgm
    ON categoria USING gin (nombre gin_trgm_ops);

-- Busqueda full-text en espanol: tsvector @@ plainto_tsquery (RF-03.2).
CREATE INDEX idx_productos_texto_busqueda
    ON productos USING gin (texto_busqueda);

-- Busqueda vectorial por distancia de coseno (RF-03.2, Semana 4).
CREATE INDEX idx_productos_descripcion_vectorial
    ON productos USING hnsw (descripcion_vectorial vector_cosine_ops);

-- =====================================================================
-- 2.b MODELO DE CONSULTA DEL ASISTENTE (migracion 7_0)
--     Comparar precios y plazos entre proveedores, saber a quien se le
--     compra y que se esta agotando requiere hechos, no solo la ficha
--     del catalogo.
-- =====================================================================

-- Tabla: producto_proveedor
-- Oferta de un proveedor para un producto. Es la tabla que permite
-- responder "quien lo tiene mas barato" y "en cuantos dias llega".
CREATE TABLE producto_proveedor (
    id SERIAL PRIMARY KEY,
    id_producto INT NOT NULL,
    id_proveedor INT NOT NULL,
    codigo_proveedor VARCHAR(50) NOT NULL,
    precio NUMERIC(12, 2) NOT NULL
        CONSTRAINT chk_oferta_precio CHECK (precio >= 0),
    moneda CHAR(3) NOT NULL DEFAULT 'USD',
    iva NUMERIC(5, 2) NOT NULL DEFAULT 0.00
        CONSTRAINT chk_oferta_iva CHECK (iva >= 0 AND iva <= 100),
    iva_incluido BOOLEAN,
    descuento NUMERIC(10, 2)
        CONSTRAINT chk_oferta_descuento CHECK (descuento IS NULL OR descuento >= 0),
    cantidad_disponible_proveedor INT
        CONSTRAINT chk_oferta_disponibilidad CHECK (
            cantidad_disponible_proveedor IS NULL OR cantidad_disponible_proveedor >= 0
        ),
    politica_ventas TEXT,
    plazo_entrega_dias SMALLINT
        CONSTRAINT chk_oferta_plazo
        CHECK (plazo_entrega_dias IS NULL OR plazo_entrega_dias >= 0),
    tiempo_reposicion_dias SMALLINT
        CONSTRAINT chk_oferta_reposicion
        CHECK (tiempo_reposicion_dias IS NULL OR tiempo_reposicion_dias >= 0),
    cantidad_minima INT NOT NULL DEFAULT 1
        CONSTRAINT chk_oferta_cantidad CHECK (cantidad_minima > 0),
    disponible BOOLEAN DEFAULT TRUE,
    es_preferido BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_cotizacion DATE NOT NULL DEFAULT CURRENT_DATE,
    vigente_desde DATE,
    vigente_hasta DATE,
    id_archivo INT,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_oferta_producto
        FOREIGN KEY (id_producto) REFERENCES productos(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_oferta_proveedor
        FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedores)
        ON DELETE CASCADE,
    CONSTRAINT fk_oferta_archivo
        FOREIGN KEY (id_archivo) REFERENCES archivos_subidos(id_archivo)
        ON DELETE SET NULL,
    CONSTRAINT uq_oferta_proveedor_codigo
        UNIQUE (id_proveedor, codigo_proveedor),
    CONSTRAINT uq_oferta_producto_proveedor
        UNIQUE (id_producto, id_proveedor),
    CONSTRAINT chk_oferta_vigencia CHECK (
        vigente_hasta IS NULL OR vigente_desde IS NULL
        OR vigente_hasta >= vigente_desde
    )
);

CREATE INDEX idx_oferta_producto_precio
    ON producto_proveedor (id_producto, precio);
CREATE INDEX idx_oferta_precio ON producto_proveedor (precio);
CREATE INDEX idx_oferta_plazo ON producto_proveedor (plazo_entrega_dias);
CREATE INDEX idx_oferta_proveedor ON producto_proveedor (id_proveedor);

-- Tabla: historial_precios
-- Precio de cada oferta en el tiempo: tendencias y "mas barato hoy".
CREATE TABLE historial_precios (
    id BIGSERIAL PRIMARY KEY,
    id_oferta INT NOT NULL,
    precio NUMERIC(12, 2) NOT NULL
        CONSTRAINT chk_historial_precio CHECK (precio >= 0),
    moneda CHAR(3) NOT NULL DEFAULT 'USD',
    iva NUMERIC(5, 2) NOT NULL DEFAULT 0.00
        CONSTRAINT chk_historial_iva CHECK (iva >= 0 AND iva <= 100),
    iva_incluido BOOLEAN,
    descuento NUMERIC(10, 2)
        CONSTRAINT chk_historial_descuento CHECK (descuento IS NULL OR descuento >= 0),
    cantidad_disponible_proveedor INT
        CONSTRAINT chk_historial_disponibilidad CHECK (
            cantidad_disponible_proveedor IS NULL OR cantidad_disponible_proveedor >= 0
        ),
    politica_ventas TEXT,
    registrado_en DATE NOT NULL DEFAULT CURRENT_DATE,
    id_archivo INT,

    CONSTRAINT fk_historial_oferta
        FOREIGN KEY (id_oferta) REFERENCES producto_proveedor(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_historial_archivo
        FOREIGN KEY (id_archivo) REFERENCES archivos_subidos(id_archivo)
        ON DELETE SET NULL
);

CREATE INDEX idx_historial_oferta_fecha
    ON historial_precios (id_oferta, registrado_en DESC);

-- Tabla: compras
-- Ordenes de compra: base objetiva de puntualidad y cumplimiento.
CREATE TABLE compras (
    id_compra SERIAL PRIMARY KEY,
    id_proveedor INT NOT NULL,
    numero_factura VARCHAR(60),
    fecha_compra DATE NOT NULL DEFAULT CURRENT_DATE,
    fecha_entrega_estimada DATE,
    fecha_entrega_real DATE,
    monto_total NUMERIC(14, 2)
        CONSTRAINT chk_compra_monto
        CHECK (monto_total IS NULL OR monto_total >= 0),
    moneda CHAR(3) NOT NULL DEFAULT 'USD',
    estado VARCHAR(20) NOT NULL DEFAULT 'recibida'
        CONSTRAINT chk_compra_estado
        CHECK (estado IN ('pendiente', 'recibida', 'parcial', 'anulada')),
    observacion TEXT,
    id_usuario INT,

    CONSTRAINT fk_compra_proveedor
        FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedores)
        ON DELETE RESTRICT,
    CONSTRAINT chk_compra_fechas CHECK (
        fecha_entrega_real IS NULL OR fecha_entrega_real >= fecha_compra
    )
);

CREATE INDEX idx_compras_proveedor_fecha
    ON compras (id_proveedor, fecha_compra DESC);

-- Tabla: detalle_compra
CREATE TABLE detalle_compra (
    id_detalle SERIAL PRIMARY KEY,
    id_compra INT NOT NULL,
    id_producto INT NOT NULL,
    cantidad_solicitada INT NOT NULL
        CONSTRAINT chk_detalle_solicitada CHECK (cantidad_solicitada > 0),
    cantidad_recibida INT NOT NULL DEFAULT 0
        CONSTRAINT chk_detalle_recibida CHECK (cantidad_recibida >= 0),
    precio_unitario NUMERIC(12, 2) NOT NULL
        CONSTRAINT chk_detalle_precio CHECK (precio_unitario >= 0),

    CONSTRAINT fk_detalle_compra
        FOREIGN KEY (id_compra) REFERENCES compras(id_compra)
        ON DELETE CASCADE,
    CONSTRAINT fk_detalle_producto
        FOREIGN KEY (id_producto) REFERENCES productos(id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_detalle_compra_producto
        UNIQUE (id_compra, id_producto),
    CONSTRAINT chk_detalle_recibida_max
        CHECK (cantidad_recibida <= cantidad_solicitada)
);

CREATE INDEX idx_detalle_producto ON detalle_compra (id_producto);

-- Tabla: evaluacion_proveedor
-- Calidad y cumplimiento percibidos (1 a 5), una por compra.
CREATE TABLE evaluacion_proveedor (
    id SERIAL PRIMARY KEY,
    id_proveedor INT NOT NULL,
    id_compra INT,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    calidad SMALLINT
        CONSTRAINT chk_evaluacion_calidad CHECK (calidad BETWEEN 1 AND 5),
    cumplimiento SMALLINT
        CONSTRAINT chk_evaluacion_cumplimiento
        CHECK (cumplimiento BETWEEN 1 AND 5),
    observacion TEXT,
    id_usuario INT,

    CONSTRAINT fk_evaluacion_proveedor
        FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedores)
        ON DELETE CASCADE,
    CONSTRAINT fk_evaluacion_compra
        FOREIGN KEY (id_compra) REFERENCES compras(id_compra)
        ON DELETE SET NULL,
    CONSTRAINT uq_evaluacion_compra UNIQUE (id_compra)
);

CREATE INDEX idx_evaluacion_proveedor
    ON evaluacion_proveedor (id_proveedor, fecha DESC);

-- Tabla: stock_movimientos
-- Entradas, salidas y ajustes: base del consumo y de las alertas.
CREATE TABLE stock_movimientos (
    id BIGSERIAL PRIMARY KEY,
    id_producto INT NOT NULL,
    tipo VARCHAR(20) NOT NULL
        CONSTRAINT chk_movimiento_tipo
        CHECK (tipo IN ('entrada', 'salida', 'ajuste', 'devolucion')),
    cantidad INT NOT NULL
        CONSTRAINT chk_movimiento_cantidad CHECK (cantidad <> 0),
    motivo VARCHAR(120),
    referencia VARCHAR(60),
    ocurrido_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario INT,

    CONSTRAINT fk_movimiento_producto
        FOREIGN KEY (id_producto) REFERENCES productos(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_movimiento_producto_fecha
    ON stock_movimientos (id_producto, ocurrido_en DESC);
CREATE INDEX idx_movimiento_fecha
    ON stock_movimientos (ocurrido_en DESC);

-- Tabla: configuracion_stock
-- Una sola fila: umbral global y dias de cobertura para la alerta.
CREATE TABLE configuracion_stock (
    id SMALLINT PRIMARY KEY DEFAULT 1
        CONSTRAINT chk_configuracion_unica CHECK (id = 1),
    stock_minimo_global INT NOT NULL DEFAULT 5
        CONSTRAINT chk_configuracion_minimo CHECK (stock_minimo_global >= 0),
    dias_cobertura_alerta SMALLINT NOT NULL DEFAULT 15
        CONSTRAINT chk_configuracion_dias CHECK (dias_cobertura_alerta > 0),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO configuracion_stock (id) VALUES (1);

-- Tabla: producto_alias
-- "mazo" debe encontrar "martillo" sin que el asistente invente productos.
CREATE TABLE producto_alias (
    id SERIAL PRIMARY KEY,
    id_producto INT NOT NULL,
    termino VARCHAR(120) NOT NULL,
    origen VARCHAR(30) NOT NULL DEFAULT 'manual'
        CONSTRAINT chk_alias_origen
        CHECK (origen IN ('manual', 'proveedor', 'catalogo')),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_alias_producto
        FOREIGN KEY (id_producto) REFERENCES productos(id)
        ON DELETE CASCADE,
    CONSTRAINT uq_alias_producto_termino UNIQUE (id_producto, termino)
);

CREATE INDEX idx_alias_termino_trgm
    ON producto_alias USING gin (termino gin_trgm_ops);

-- Tabla: tasa_cambio
-- Los catalogos mezclan precios en Bs. y en USD.
CREATE TABLE tasa_cambio (
    id SERIAL PRIMARY KEY,
    moneda CHAR(3) NOT NULL,
    tasa NUMERIC(14, 6) NOT NULL
        CONSTRAINT chk_tasa_positiva CHECK (tasa > 0),
    vigente_desde DATE NOT NULL DEFAULT CURRENT_DATE,
    CONSTRAINT uq_tasa_moneda_fecha UNIQUE (moneda, vigente_desde)
);

-- Permisos del rol de aplicacion en esta base: solo datos, nunca estructura.
GRANT CONNECT ON DATABASE ferreteria_rag TO app_ferreteria;
GRANT USAGE ON SCHEMA public TO app_ferreteria;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON archivos_subidos, proveedores, categoria, productos,
       producto_proveedor, historial_precios, compras, detalle_compra,
       evaluacion_proveedor, stock_movimientos, producto_alias, tasa_cambio
    TO app_ferreteria;
-- La configuracion de stock se lee y se actualiza, pero no se borra.
GRANT SELECT, INSERT, UPDATE ON configuracion_stock TO app_ferreteria;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_ferreteria;

COMMENT ON DATABASE ferreteria_rag IS
    'Catalogo de productos, proveedores y categorias del sistema RAG';
COMMENT ON TABLE producto_proveedor IS
    'Oferta de un proveedor para un producto: precio, plazo y disponibilidad';
COMMENT ON TABLE historial_precios IS
    'Precio de cada oferta en el tiempo, para comparar y ver tendencias';
COMMENT ON TABLE compras IS
    'Ordenes de compra recibidas: base objetiva de cumplimiento y puntualidad';
COMMENT ON TABLE stock_movimientos IS
    'Entradas, salidas y ajustes: base del consumo y de las alertas de stock';
COMMENT ON COLUMN productos.punto_reorden IS
    'Umbral propio del producto; si es NULL se usa configuracion_stock';
COMMENT ON COLUMN productos.descripcion_vectorial IS
    'Embedding de 384 dimensiones de intfloat/multilingual-e5-small';


-- =====================================================================
-- 3. BASE DE DATOS DE USUARIOS: ferreteria_usuarios
--    Autenticacion, roles y bitacora inmutable de auditoria.
-- =====================================================================

\connect ferreteria_usuarios

-- Tabla: rol (RF-01.2)
CREATE TABLE rol (
    id_rol SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion TEXT,
    protegido BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE UNIQUE INDEX uq_rol_nombre_lower ON rol (LOWER(nombre));

-- Capacidades cerradas que pueden asignarse a roles no administrativos.
CREATE TABLE permiso (
    id_permiso SERIAL PRIMARY KEY,
    clave VARCHAR(80) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT NOT NULL,
    orden SMALLINT NOT NULL DEFAULT 0
);

INSERT INTO permiso (clave, nombre, descripcion, orden) VALUES
    ('usuarios:gestionar', 'Gestionar usuarios', 'Consultar y administrar cuentas del sistema.', 10),
    ('catalogos:ingestar', 'Cargar catalogos', 'Cargar catalogos de productos y consultar su procesamiento.', 20),
    ('catalogos:eliminar', 'Eliminar catalogos', 'Eliminar catalogos y los productos que contienen.', 30),
    ('configuracion:diagnostico', 'Consultar diagnostico', 'Consultar estado de bases de datos y limites tecnicos.', 40),
    ('bitacora:consultar', 'Consultar bitacora', 'Consultar el historial de auditoria del sistema.', 50)
ON CONFLICT (clave) DO UPDATE SET
    nombre = EXCLUDED.nombre,
    descripcion = EXCLUDED.descripcion,
    orden = EXCLUDED.orden;

CREATE TABLE rol_permiso (
    id_rol INT NOT NULL,
    id_permiso INT NOT NULL,
    PRIMARY KEY (id_rol, id_permiso),
    CONSTRAINT fk_rol_permiso_rol
        FOREIGN KEY (id_rol) REFERENCES rol(id_rol) ON DELETE CASCADE,
    CONSTRAINT fk_rol_permiso_permiso
        FOREIGN KEY (id_permiso) REFERENCES permiso(id_permiso) ON DELETE RESTRICT
);

-- Semilla inicial: el rol admin siempre es de sistema y ventas conserva el
-- acceso de consulta que tenia antes de introducir permisos configurables.
INSERT INTO rol (nombre, descripcion, protegido) VALUES
    ('admin', 'Acceso total a las funciones administrativas del sistema', TRUE),
    ('ventas', 'Consulta de productos, chat RAG y disponibilidad', FALSE)
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO rol_permiso (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso
  FROM rol r
 CROSS JOIN permiso p
 WHERE LOWER(r.nombre) = 'admin'
ON CONFLICT (id_rol, id_permiso) DO NOTHING;

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
    imagen_perfil BYTEA,

    CONSTRAINT fk_usuarios_rol
        FOREIGN KEY (id_rol) REFERENCES rol(id_rol)
        ON DELETE RESTRICT,
    CONSTRAINT chk_usuarios_imagen_perfil_tamano
        CHECK (imagen_perfil IS NULL OR octet_length(imagen_perfil) <= 2097152)
);

CREATE UNIQUE INDEX uq_usuarios_usuario_lower ON usuarios (LOWER(usuario));
CREATE UNIQUE INDEX uq_usuarios_correo_lower ON usuarios (LOWER(correo));
CREATE UNIQUE INDEX uq_usuarios_cedula_lower ON usuarios (LOWER(cedula));

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

-- El catalogo de capacidades es de solo lectura para la API. Los roles y su
-- relacion con las capacidades se administran por endpoints autorizados.
GRANT SELECT ON permiso TO app_ferreteria;
GRANT SELECT, INSERT, UPDATE, DELETE ON rol TO app_ferreteria;
GRANT SELECT, INSERT, DELETE ON rol_permiso TO app_ferreteria;

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
