-- Migracion 7.0 - Modelo de consulta para el asistente (precios por
-- proveedor, tiempos de entrega, historial de compras y alertas de stock).
--
-- Se aplica sobre ferreteria_rag sin borrar datos y puede repetirse.
-- Es aditiva: no elimina ni renombra columnas existentes. Las columnas y
-- tablas nuevas son opcionales para el ETL actual; el sistema sigue
-- funcionando si aun no se cargan compras ni evaluaciones.
--
-- Aplicar con:
--     venv\Scripts\python.exe scripts\aplicar_migracion.py 7_0

-- =====================================================================
-- 1. PROVEEDORES: identidad, contacto y condiciones comerciales
-- =====================================================================

ALTER TABLE proveedores
    ADD COLUMN IF NOT EXISTS rif VARCHAR(20),
    ADD COLUMN IF NOT EXISTS telefono VARCHAR(40),
    ADD COLUMN IF NOT EXISTS correo VARCHAR(255),
    ADD COLUMN IF NOT EXISTS vendedor VARCHAR(255),
    ADD COLUMN IF NOT EXISTS telefono_vendedor VARCHAR(40),
    ADD COLUMN IF NOT EXISTS correo_vendedor VARCHAR(255),
    ADD COLUMN IF NOT EXISTS moneda CHAR(3) NOT NULL DEFAULT 'USD',
    ADD COLUMN IF NOT EXISTS plazo_entrega_dias SMALLINT,
    ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE archivos_subidos
    ADD COLUMN IF NOT EXISTS id_proveedor INT,
    ADD COLUMN IF NOT EXISTS vendedor_nombre VARCHAR(255),
    ADD COLUMN IF NOT EXISTS vendedor_telefono VARCHAR(40),
    ADD COLUMN IF NOT EXISTS vendedor_correo VARCHAR(255),
    ADD COLUMN IF NOT EXISTS moneda CHAR(3) NOT NULL DEFAULT 'USD',
    ADD COLUMN IF NOT EXISTS nota_proveedor TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'fk_archivos_proveedor'
           AND conrelid = 'archivos_subidos'::regclass
    ) THEN
        ALTER TABLE archivos_subidos
            ADD CONSTRAINT fk_archivos_proveedor
            FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedores)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_archivos_proveedor
    ON archivos_subidos (id_proveedor, fecha_de_subida DESC);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'chk_proveedores_plazo'
           AND conrelid = 'proveedores'::regclass
    ) THEN
        ALTER TABLE proveedores
            ADD CONSTRAINT chk_proveedores_plazo
            CHECK (plazo_entrega_dias IS NULL OR plazo_entrega_dias >= 0);
    END IF;
END
$$;

-- Evita proveedores duplicados por diferencias de mayusculas. Solo se crea
-- si los datos actuales no tienen duplicados: la migracion no adivina cual
-- de dos fichas es la buena.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_class WHERE relname = 'uq_proveedores_nombre_lower'
    ) AND NOT EXISTS (
        SELECT 1 FROM proveedores GROUP BY LOWER(nombre) HAVING COUNT(*) > 1
    ) THEN
        CREATE UNIQUE INDEX uq_proveedores_nombre_lower
            ON proveedores (LOWER(nombre));
    END IF;
END
$$;

-- =====================================================================
-- 2. CATEGORIA: jerarquia y sinonimos de busqueda
-- =====================================================================

ALTER TABLE categoria
    ADD COLUMN IF NOT EXISTS id_padre INT,
    ADD COLUMN IF NOT EXISTS sinonimos TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'fk_categoria_padre'
           AND conrelid = 'categoria'::regclass
    ) THEN
        ALTER TABLE categoria
            ADD CONSTRAINT fk_categoria_padre
            FOREIGN KEY (id_padre) REFERENCES categoria(id_categoria)
            ON DELETE SET NULL;
    END IF;
END
$$;

-- =====================================================================
-- 3. PRODUCTOS: moneda, presentacion, politica de stock y estado del vector
-- =====================================================================

ALTER TABLE productos
    ADD COLUMN IF NOT EXISTS codigo_interno VARCHAR(50),
    ADD COLUMN IF NOT EXISTS moneda CHAR(3) NOT NULL DEFAULT 'USD',
    ADD COLUMN IF NOT EXISTS unidad_medida VARCHAR(30),
    ADD COLUMN IF NOT EXISTS presentacion VARCHAR(120),
    ADD COLUMN IF NOT EXISTS punto_reorden INT,
    ADD COLUMN IF NOT EXISTS ubicacion VARCHAR(80),
    ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS modelo_embedding VARCHAR(80),
    ADD COLUMN IF NOT EXISTS vectorizado_en TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'chk_productos_punto_reorden'
           AND conrelid = 'productos'::regclass
    ) THEN
        ALTER TABLE productos
            ADD CONSTRAINT chk_productos_punto_reorden
            CHECK (punto_reorden IS NULL OR punto_reorden >= 0);
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_productos_codigo_interno
    ON productos (codigo_interno)
    WHERE codigo_interno IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_productos_proveedor
    ON productos (id_proveedor);
CREATE INDEX IF NOT EXISTS idx_productos_categoria
    ON productos (id_categoria);

-- Reconciliacion de la vectorizacion: encontrar rapido lo que falta.
CREATE INDEX IF NOT EXISTS idx_productos_sin_vector
    ON productos (id)
    WHERE descripcion_vectorial IS NULL;

-- =====================================================================
-- 4. OFERTAS POR PROVEEDOR: la tabla que falta para comparar precios,
--    plazos de entrega y disponibilidad del mismo producto.
-- =====================================================================

CREATE TABLE IF NOT EXISTS producto_proveedor (
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
        CONSTRAINT chk_oferta_plazo CHECK (
            plazo_entrega_dias IS NULL OR plazo_entrega_dias >= 0
        ),
    tiempo_reposicion_dias SMALLINT
        CONSTRAINT chk_oferta_reposicion CHECK (
            tiempo_reposicion_dias IS NULL OR tiempo_reposicion_dias >= 0
        ),
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

ALTER TABLE producto_proveedor
    ALTER COLUMN iva SET DEFAULT 0.00,
    ALTER COLUMN descuento DROP NOT NULL,
    ALTER COLUMN descuento DROP DEFAULT,
    ALTER COLUMN disponible DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS iva_incluido BOOLEAN,
    ADD COLUMN IF NOT EXISTS cantidad_disponible_proveedor INT
        CONSTRAINT chk_oferta_disponibilidad CHECK (
            cantidad_disponible_proveedor IS NULL OR cantidad_disponible_proveedor >= 0
        ),
    ADD COLUMN IF NOT EXISTS politica_ventas TEXT;

ALTER TABLE producto_proveedor
    ALTER COLUMN iva_incluido DROP NOT NULL,
    ALTER COLUMN iva_incluido DROP DEFAULT;

CREATE INDEX IF NOT EXISTS idx_oferta_producto_precio
    ON producto_proveedor (id_producto, precio);
CREATE INDEX IF NOT EXISTS idx_oferta_precio
    ON producto_proveedor (precio);
CREATE INDEX IF NOT EXISTS idx_oferta_plazo
    ON producto_proveedor (plazo_entrega_dias);
CREATE INDEX IF NOT EXISTS idx_oferta_proveedor
    ON producto_proveedor (id_proveedor);

-- =====================================================================
-- 5. HISTORIAL DE PRECIOS: "mas barato hoy" y evolucion del precio
-- =====================================================================

CREATE TABLE IF NOT EXISTS historial_precios (
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

ALTER TABLE historial_precios
    ALTER COLUMN moneda SET DEFAULT 'USD',
    ADD COLUMN IF NOT EXISTS iva NUMERIC(5, 2) NOT NULL DEFAULT 0.00
        CONSTRAINT chk_historial_iva CHECK (iva >= 0 AND iva <= 100),
    ADD COLUMN IF NOT EXISTS iva_incluido BOOLEAN,
    ADD COLUMN IF NOT EXISTS descuento NUMERIC(10, 2)
        CONSTRAINT chk_historial_descuento CHECK (descuento IS NULL OR descuento >= 0),
    ADD COLUMN IF NOT EXISTS cantidad_disponible_proveedor INT
        CONSTRAINT chk_historial_disponibilidad CHECK (
            cantidad_disponible_proveedor IS NULL OR cantidad_disponible_proveedor >= 0
        ),
    ADD COLUMN IF NOT EXISTS politica_ventas TEXT;

ALTER TABLE historial_precios
    ALTER COLUMN iva_incluido DROP NOT NULL,
    ALTER COLUMN iva_incluido DROP DEFAULT;

CREATE INDEX IF NOT EXISTS idx_historial_oferta_fecha
    ON historial_precios (id_oferta, registrado_en DESC);

-- =====================================================================
-- 6. COMPRAS Y RECEPCIONES: "quien me ha surtido" con hechos, no opiniones
-- =====================================================================

CREATE TABLE IF NOT EXISTS compras (
    id_compra SERIAL PRIMARY KEY,
    id_proveedor INT NOT NULL,
    numero_factura VARCHAR(60),
    fecha_compra DATE NOT NULL DEFAULT CURRENT_DATE,
    fecha_entrega_estimada DATE,
    fecha_entrega_real DATE,
    monto_total NUMERIC(14, 2)
        CONSTRAINT chk_compra_monto CHECK (monto_total IS NULL OR monto_total >= 0),
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

-- Backfill opcional: si ya habia productos con proveedor asignado a mano, se
-- crea su oferta inicial. Sin proveedor ni codigo no hay oferta que crear.
INSERT INTO producto_proveedor
    (id_producto, id_proveedor, codigo_proveedor, precio, moneda, iva,
     descuento, id_archivo, fecha_cotizacion)
SELECT p.id, p.id_proveedor, p.codigo, p.precio, p.moneda, p.iva,
       p.descuentos, p.id_archivo, CURRENT_DATE
  FROM productos AS p
 WHERE p.id_proveedor IS NOT NULL
   AND p.codigo IS NOT NULL
ON CONFLICT (id_producto, id_proveedor) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_compras_proveedor_fecha
    ON compras (id_proveedor, fecha_compra DESC);

CREATE TABLE IF NOT EXISTS detalle_compra (
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
    CONSTRAINT uq_detalle_compra_producto UNIQUE (id_compra, id_producto),
    CONSTRAINT chk_detalle_recibida_max CHECK (
        cantidad_recibida <= cantidad_solicitada
    )
);

CREATE INDEX IF NOT EXISTS idx_detalle_producto
    ON detalle_compra (id_producto);

-- =====================================================================
-- 7. EVALUACION DEL PROVEEDOR: calidad percibida (1 a 5)
-- =====================================================================

CREATE TABLE IF NOT EXISTS evaluacion_proveedor (
    id SERIAL PRIMARY KEY,
    id_proveedor INT NOT NULL,
    id_compra INT,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    calidad SMALLINT
        CONSTRAINT chk_evaluacion_calidad CHECK (calidad BETWEEN 1 AND 5),
    cumplimiento SMALLINT
        CONSTRAINT chk_evaluacion_cumplimiento CHECK (
            cumplimiento BETWEEN 1 AND 5
        ),
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

CREATE INDEX IF NOT EXISTS idx_evaluacion_proveedor
    ON evaluacion_proveedor (id_proveedor, fecha DESC);

-- =====================================================================
-- 8. MOVIMIENTOS DE STOCK Y REGLA DE ALERTA
--    "Que se esta acabando" necesita consumo, no solo una foto del stock.
-- =====================================================================

CREATE TABLE IF NOT EXISTS stock_movimientos (
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

CREATE INDEX IF NOT EXISTS idx_movimiento_producto_fecha
    ON stock_movimientos (id_producto, ocurrido_en DESC);
CREATE INDEX IF NOT EXISTS idx_movimiento_fecha
    ON stock_movimientos (ocurrido_en DESC);

-- Una sola fila de configuracion: umbral global y dias de cobertura.
CREATE TABLE IF NOT EXISTS configuracion_stock (
    id SMALLINT PRIMARY KEY DEFAULT 1
        CONSTRAINT chk_configuracion_unica CHECK (id = 1),
    stock_minimo_global INT NOT NULL DEFAULT 5
        CONSTRAINT chk_configuracion_minimo CHECK (stock_minimo_global >= 0),
    dias_cobertura_alerta SMALLINT NOT NULL DEFAULT 15
        CONSTRAINT chk_configuracion_dias CHECK (dias_cobertura_alerta > 0),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO configuracion_stock (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

-- =====================================================================
-- 9. ALIAS DE BUSQUEDA: "mazo" debe encontrar "martillo" sin inventar
-- =====================================================================

CREATE TABLE IF NOT EXISTS producto_alias (
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

CREATE INDEX IF NOT EXISTS idx_alias_termino_trgm
    ON producto_alias USING gin (termino gin_trgm_ops);

-- =====================================================================
-- 10. TASA DE CAMBIO: los catalogos traen precios en Bs. y en USD
-- =====================================================================

CREATE TABLE IF NOT EXISTS tasa_cambio (
    id SERIAL PRIMARY KEY,
    moneda CHAR(3) NOT NULL,
    tasa NUMERIC(14, 6) NOT NULL
        CONSTRAINT chk_tasa_positiva CHECK (tasa > 0),
    vigente_desde DATE NOT NULL DEFAULT CURRENT_DATE,
    CONSTRAINT uq_tasa_moneda_fecha UNIQUE (moneda, vigente_desde)
);

-- =====================================================================
-- 11. PERMISOS Y COMENTARIOS
-- =====================================================================

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proveedores, categoria, productos, producto_proveedor,
       historial_precios, compras, detalle_compra, evaluacion_proveedor,
       stock_movimientos, producto_alias, tasa_cambio
    TO app_ferreteria;

GRANT SELECT, INSERT, UPDATE ON configuracion_stock TO app_ferreteria;

GRANT USAGE, SELECT
    ON SEQUENCE producto_proveedor_id_seq, historial_precios_id_seq,
                 compras_id_compra_seq, detalle_compra_id_detalle_seq,
                 evaluacion_proveedor_id_seq, stock_movimientos_id_seq,
                 producto_alias_id_seq, tasa_cambio_id_seq
    TO app_ferreteria;

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
