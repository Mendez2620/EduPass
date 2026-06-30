CREATE TABLE IF NOT EXISTS roles (
    rol_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS usuarios (
    usuario_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    correo TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    estado TEXT NOT NULL,
    rol_id INTEGER NOT NULL,
    FOREIGN KEY (rol_id) REFERENCES roles (rol_id)
);

CREATE TABLE IF NOT EXISTS alumnos (
    alumno_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    matricula TEXT NOT NULL UNIQUE,
    grado TEXT NOT NULL,
    grupo TEXT NOT NULL,
    fotografia TEXT,
    estado TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tutores (
    tutor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    parentesco TEXT NOT NULL,
    telefono TEXT,
    correo TEXT,
    estado TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alumno_tutor (
    alumno_tutor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alumno_id INTEGER NOT NULL,
    tutor_id INTEGER NOT NULL,
    UNIQUE (alumno_id, tutor_id),
    FOREIGN KEY (alumno_id) REFERENCES alumnos (alumno_id),
    FOREIGN KEY (tutor_id) REFERENCES tutores (tutor_id)
);

CREATE TABLE IF NOT EXISTS areas_internas (
    area_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    descripcion TEXT,
    estado TEXT NOT NULL,
    metodo_escaneo TEXT NOT NULL,
    notificaciones_activas INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS usuario_area_permiso (
    permiso_id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    area_id INTEGER NOT NULL,
    UNIQUE (usuario_id, area_id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios (usuario_id),
    FOREIGN KEY (area_id) REFERENCES areas_internas (area_id)
);

CREATE TABLE IF NOT EXISTS dispositivos_fijos (
    dispositivo_id INTEGER PRIMARY KEY AUTOINCREMENT,
    identificador TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    estado TEXT NOT NULL,
    area_id INTEGER,
    punto_plantel TEXT,
    FOREIGN KEY (area_id) REFERENCES areas_internas (area_id)
);

CREATE TABLE IF NOT EXISTS qr_tokens (
    qr_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alumno_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    generado_en TEXT NOT NULL,
    expira_en TEXT NOT NULL,
    usado_en TEXT,
    estado TEXT NOT NULL,
    FOREIGN KEY (alumno_id) REFERENCES alumnos (alumno_id)
);

CREATE TABLE IF NOT EXISTS movimientos (
    movimiento_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alumno_id INTEGER NOT NULL,
    tipo_movimiento TEXT NOT NULL,
    fecha_hora TEXT NOT NULL,
    area_id INTEGER,
    punto_plantel TEXT,
    usuario_id INTEGER,
    dispositivo_id INTEGER,
    FOREIGN KEY (alumno_id) REFERENCES alumnos (alumno_id),
    FOREIGN KEY (area_id) REFERENCES areas_internas (area_id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios (usuario_id),
    FOREIGN KEY (dispositivo_id) REFERENCES dispositivos_fijos (dispositivo_id)
);

CREATE TABLE IF NOT EXISTS notificaciones_push (
    notificacion_id INTEGER PRIMARY KEY AUTOINCREMENT,
    movimiento_id INTEGER NOT NULL,
    tutor_id INTEGER NOT NULL,
    estado TEXT NOT NULL,
    fecha_hora TEXT NOT NULL,
    contenido TEXT NOT NULL,
    FOREIGN KEY (movimiento_id) REFERENCES movimientos (movimiento_id),
    FOREIGN KEY (tutor_id) REFERENCES tutores (tutor_id)
);

CREATE TABLE IF NOT EXISTS intentos_rechazados (
    intento_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alumno_id INTEGER,
    qr_id INTEGER,
    motivo TEXT NOT NULL,
    fecha_hora TEXT NOT NULL,
    usuario_id INTEGER,
    dispositivo_id INTEGER,
    area_id INTEGER,
    FOREIGN KEY (alumno_id) REFERENCES alumnos (alumno_id),
    FOREIGN KEY (qr_id) REFERENCES qr_tokens (qr_id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios (usuario_id),
    FOREIGN KEY (dispositivo_id) REFERENCES dispositivos_fijos (dispositivo_id),
    FOREIGN KEY (area_id) REFERENCES areas_internas (area_id)
);

