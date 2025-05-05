# proyect/maxdiff/__init__.py
"""
Inicialización del Blueprint 'maxdiff'.
Importa el objeto Blueprint desde routes.py para su registro.
"""

# Importa el objeto Blueprint desde el módulo de rutas local.
from.routes import bp

# Controla qué se exporta con `from proyect.maxdiff import *`.
# Lo importante es exportar 'bp'.
__all__ = ['bp']

# Nota: Asegúrate de que en proyect/maxdiff/routes.py tengas:
# from flask import Blueprint
# bp = Blueprint('maxdiff', __name__, url_prefix='/maxdiff') # Ajusta url_prefix si es necesario
#
# @bp.route('/upload', methods=) # Ejemplo de ruta
# def upload_maxdiff():
#     #... tu vista...
