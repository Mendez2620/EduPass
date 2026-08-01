"""Formularios de la interfaz web de EduPass."""

from flask_wtf import FlaskForm
from wtforms import (
    HiddenField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import DataRequired, EqualTo, Length


class LoginForm(FlaskForm):
    correo = StringField(
        "Correo",
        validators=[DataRequired(), Length(max=254)],
    )
    password = PasswordField(
        "Contrasena",
        validators=[DataRequired(), Length(max=256)],
    )
    submit = SubmitField("Iniciar sesion")


class LogoutForm(FlaskForm):
    submit = SubmitField("Cerrar sesion")


class AlumnoForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired()])
    matricula = StringField("Matrícula", validators=[DataRequired()])
    grado = StringField("Grado", validators=[DataRequired()])
    grupo = StringField("Grupo", validators=[DataRequired()])
    submit = SubmitField("Guardar alumno")


class EstadoAlumnoForm(FlaskForm):
    submit = SubmitField("Confirmar")


class AdministradorCrearForm(FlaskForm):
    nombre = StringField(
        "Nombre",
        validators=[DataRequired(), Length(max=120)],
    )
    correo = StringField(
        "Correo",
        validators=[DataRequired(), Length(max=254)],
    )
    password = PasswordField(
        "Contraseña",
        validators=[DataRequired(), Length(min=8, max=256)],
    )
    confirmar_password = PasswordField(
        "Confirmar contraseña",
        validators=[DataRequired(), EqualTo("password")],
    )
    submit = SubmitField("Guardar administrador")


class AdministradorEditarForm(FlaskForm):
    nombre = StringField(
        "Nombre",
        validators=[DataRequired(), Length(max=120)],
    )
    correo = StringField(
        "Correo",
        validators=[DataRequired(), Length(max=254)],
    )
    submit = SubmitField("Guardar administrador")


class AdministradorPasswordForm(FlaskForm):
    password = PasswordField(
        "Nueva contraseña",
        validators=[DataRequired(), Length(min=8, max=256)],
    )
    confirmar_password = PasswordField(
        "Confirmar nueva contraseña",
        validators=[DataRequired(), EqualTo("password")],
    )
    submit = SubmitField("Actualizar contraseña")


class EscanerCrearForm(AdministradorCrearForm):
    submit = SubmitField("Guardar escáner")


class EscanerEditarForm(AdministradorEditarForm):
    submit = SubmitField("Guardar escáner")


class EscanerPasswordForm(AdministradorPasswordForm):
    submit = SubmitField("Actualizar contraseña")

class CuentaAlumnoCrearForm(FlaskForm):
    alumno_id = SelectField(
        "Alumno",
        choices=[],
        coerce=int,
        validators=[DataRequired()],
    )
    correo = StringField(
        "Correo",
        validators=[DataRequired(), Length(max=254)],
    )
    password = PasswordField(
        "Contraseña",
        validators=[DataRequired(), Length(min=8, max=256)],
    )
    confirmar_password = PasswordField(
        "Confirmar contraseña",
        validators=[DataRequired(), EqualTo("password")],
    )
    submit = SubmitField("Crear cuenta")


class CuentaAlumnoEditarForm(FlaskForm):
    correo = StringField(
        "Correo",
        validators=[DataRequired(), Length(max=254)],
    )
    submit = SubmitField("Guardar cuenta")


class CuentaAlumnoPasswordForm(FlaskForm):
    password = PasswordField(
        "Nueva contraseña",
        validators=[DataRequired(), Length(min=8, max=256)],
    )
    confirmar_password = PasswordField(
        "Confirmar nueva contraseña",
        validators=[DataRequired(), EqualTo("password")],
    )
    submit = SubmitField("Actualizar contraseña")

class EstadoUsuarioForm(FlaskForm):
    submit = SubmitField("Confirmar")

class AlumnoGenerarCredencialForm(FlaskForm):
    submit = SubmitField("Generar QR")


class AlumnoRenovarCredencialForm(FlaskForm):
    submit = SubmitField("Renovar QR")

class GenerarCredencialForm(FlaskForm):
    alumno_id = HiddenField("Alumno", validators=[DataRequired()])
    submit = SubmitField("Generar credencial")


class RenovarCredencialForm(FlaskForm):
    alumno_id = HiddenField("Alumno", validators=[DataRequired()])
    submit = SubmitField("Renovar credencial")


class ValidarTokenQRForm(FlaskForm):
    tipo_movimiento = SelectField(
        "Tipo de movimiento",
        choices=[
            ("", "Selecciona una opcion"),
            ("entrada", "Entrada"),
            ("salida", "Salida"),
        ],
        validators=[DataRequired()],
    )
    token = StringField(
        "Token QR",
        validators=[DataRequired(), Length(max=43)],
        render_kw={"autocomplete": "off"},
    )
    submit = SubmitField("Registrar movimiento")
