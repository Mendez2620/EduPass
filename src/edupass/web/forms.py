"""Formularios de la interfaz web de EduPass."""

from flask_wtf import FlaskForm
from wtforms import HiddenField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Length


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


class GenerarCredencialForm(FlaskForm):
    alumno_id = HiddenField("Alumno", validators=[DataRequired()])
    submit = SubmitField("Generar credencial")


class RenovarCredencialForm(FlaskForm):
    alumno_id = HiddenField("Alumno", validators=[DataRequired()])
    submit = SubmitField("Renovar credencial")


class ValidarTokenQRForm(FlaskForm):
    token = StringField(
        "Token QR",
        validators=[DataRequired(), Length(max=43)],
        render_kw={"autocomplete": "off"},
    )
    submit = SubmitField("Validar token")