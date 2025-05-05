# proyect/moca/__init__.py
"""
Inicialización del Blueprint 'moca'.
Importa el objeto Blueprint desde routes.py para su registro.
"""

# Importa el objeto Blueprint desde el módulo de rutas local.
# ¡Asegúrate de que este import sea desde '.routes' dentro de la carpeta 'moca'!
from.routes import bp

# Controla qué se exporta con `from proyect.moca import *`.
__all__ = ['bp']

# Nota: Asegúrate de que en proyect/moca/routes.py tengas:
# from flask import Blueprint
# bp = Blueprint('moca', __name__, url_prefix='/moca') # Ajusta url_prefix si es necesario
#
# @bp.route('/analyze') # Ejemplo de ruta
# def analyze_moca():
#     #... tu vista...
