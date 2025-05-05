# proyect/__init__.py
"""
Paquete principal 'proyect'.
Define qué sub-módulos se consideran parte de la interfaz pública del paquete.
"""

# Esto permite hacer 'from proyect import main, maxdiff', etc.
# Asegúrate de que estos nombres coincidan exactamente con los nombres de las carpetas (subpaquetes).
__all__ = [
    "common",
    "main",
    "maxdiff",
    "comstrat",
    "moca",
]

# Nota: Este archivo NO define un Blueprint, lo cual es correcto.
# Solo organiza el paquete principal.
