# proyect/comstrat/__init__.py
"""
Inicialización del Blueprint 'comstrat'.
Importa el objeto Blueprint desde routes.py para su registro.
"""

# Importa únicamente el objeto Blueprint definido en routes.py
from.routes import bp

# Controla qué se exporta con "from proyect.comstrat import *"
__all__ = ['bp']

# Nota: Asegúrate de que en proyect/comstrat/routes.py tengas:
# from flask import Blueprint
# bp = Blueprint('comstrat', __name__, url_prefix='/comstrat') # Ajusta url_prefix si es necesario
#
# @bp.route('/strategy') # Ejemplo de ruta
# def get_strategy():
#     #... tu vista...
