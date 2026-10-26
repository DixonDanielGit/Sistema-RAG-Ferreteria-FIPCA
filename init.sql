-- =====================================================================
-- 1. BASE DE DATOS PRINCIPAL (SISTEMA RAG)[cite: 1]
-- =====================================================================

-- Extensión opcional recomendada para campos vectoriales en IA (pgvector)
CREATE EXTENSION IF NOT EXISTS vector;

-- Tabla: archivos_subidos[cite: 1]
CREATE TABLE archivos_subidos (
    id_archivo SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    tipo VARCHAR(100) NOT NULL,
    fecha_de_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla: proveedores[cite: 1]
CREATE TABLE proveedores (
    id_proveedores SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    direccion TEXT,
    vendedor VARCHAR(255)
);

-- Tabla: categoria[cite: 1]
CREATE TABLE categoria (
    id_categoria SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL
);

-- Tabla: productos[cite: 1]
CREATE TABLE productos (
    id SERIAL PRIMARY KEY,
    id_archivo INT,
    id_proveedor INT,
    id_categoria INT,
    nombre VARCHAR(255) NOT NULL,
    marca VARCHAR(100),
    precio DECIMAL(10, 2) NOT NULL,
    IVA DECIMAL(5, 2),
    descuentos DECIMAL(10, 2) DEFAULT 0.00, -- (opcional)[cite: 1]
    descripcion TEXT,
    stock INT NOT NULL DEFAULT 0,
    descripcion_vectorial vector(1536), -- Nota: Si usas pgvector, puedes cambiar el tipo a 'vector(1536)' u otra dimensión según el modelo de IA.
    
    -- Restricciones de Llaves Foráneas
    CONSTRAINT fk_productos_archivo FOREIGN KEY (id_archivo) REFERENCES archivos_subidos(id_archivo) ON DELETE SET NULL,
    CONSTRAINT fk_productos_proveedor FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedores) ON DELETE SET NULL,
    CONSTRAINT fk_productos_categoria FOREIGN KEY (id_categoria) REFERENCES categoria(id_categoria) ON DELETE SET NULL
);


-- =====================================================================
-- 2. BASE DE DATOS DE USUARIOS[cite: 1]
-- =====================================================================

-- Tabla: Rol[cite: 1]
CREATE TABLE rol (
    id_rol SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    descripcion TEXT
);

-- Tabla: Usuarios[cite: 1]
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    id_rol INT NOT NULL,
    cedula VARCHAR(20) UNIQUE NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    usuario VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    correo VARCHAR(255) UNIQUE NOT NULL,
    
    -- Restricción de Llave Foránea
    CONSTRAINT fk_usuarios_rol FOREIGN KEY (id_rol) REFERENCES rol(id_rol) ON DELETE RESTRICT
);

-- Tabla: bitacora[cite: 1]
CREATE TABLE bitacora (
    id_bitacora SERIAL PRIMARY KEY,
    id_usuario INT NOT NULL,
    fecha DATE DEFAULT CURRENT_DATE,
    hora TIME DEFAULT CURRENT_TIME,
    accion TEXT NOT NULL,
    
    -- Restricción de Llave Foránea
    CONSTRAINT fk_bitacora_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios(id) ON DELETE CASCADE
);