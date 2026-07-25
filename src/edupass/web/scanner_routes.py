"""Vista inicial para personal autorizado de escaneo."""

from flask import Blueprint, render_template

from edupass.shared.constants import ROL_ESCANER
from edupass.web.security import role_required


scanner_blueprint = Blueprint("scanner", __name__, url_prefix="/scanner")


@scanner_blueprint.get("")
@role_required(ROL_ESCANER)
def dashboard():
    return render_template("scanner/dashboard.html", title="Escaneo")
