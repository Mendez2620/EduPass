"""Formularios de la interfaz web de EduPass."""

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
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
