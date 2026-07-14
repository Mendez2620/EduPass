SELECT EXISTS (
    SELECT 1
    FROM alumnos
    WHERE matricula = ?
) AS existe;
