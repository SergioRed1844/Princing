# proyect/main/__init__.py

from flask import Blueprint

# 1) Defino el Blueprint antes de cualquier importación de rutas
bp = Blueprint('main', __name__)

# 2) Importo el módulo de rutas, que a su vez usará este mismo `bp`
from proyect.main import routes  # noqa
