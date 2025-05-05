# pricing_dashboard/config.py
# -*- coding: utf-8 -*-
"""
Archivo de Configuración Centralizado para la Aplicación Flask.

Define clases de configuración para diferentes entornos.
Incluye validación temprana para variables críticas en producción.
"""

import os
import logging
from pathlib import Path
from typing import Set, Optional, List
from dotenv import load_dotenv

# Carga temprana de.env para que esté disponible al importar este módulo
# Asegúrate de que python-dotenv esté instalado (`pip install python-dotenv`)
# Coloca este archivo.env en la raíz del proyecto (pricing_dashboard/)
try:
    # load_dotenv() buscará un archivo.env en el directorio actual o superiores
    dotenv_path = Path('.') / '.env' # Asume que.env está en la raíz del proyecto
    if dotenv_path.is_file():
        load_dotenv(dotenv_path=dotenv_path, verbose=True) # verbose=True ayuda a depurar la carga
        print(f"[Config] Archivo.env cargado desde: {dotenv_path.resolve()}")
    else:
        print("[Config] Advertencia: No se encontró archivo.env en la ruta esperada.")
except ImportError:
    print("[Config] Advertencia: python-dotenv no está instalado. No se cargarán variables desde.env.")
except Exception as e:
    print(f"[Config] Error al cargar.env: {e}")


# Logger específico para la configuración
config_logger = logging.getLogger(__name__)
# Configuración básica si no hay handlers (útil si se ejecuta config.py directamente)
if not logging.root.handlers:
    logging.basicConfig(level=logging.INFO, format='%(levelname)-8s [%(name)s] %(message)s')

# Rutas Base calculadas una vez
BASE_DIR: Path = Path(__file__).resolve().parent.parent # Sube un nivel para estar en pricing_dashboard/
INSTANCE_DIR: Path = BASE_DIR / 'instance'
# Asegúrate de que la carpeta 'instance' exista si la necesitas para SQLite o uploads
INSTANCE_DIR.mkdir(exist_ok=True)

# Excepción Personalizada (Opcional, pero útil para errores específicos de config)
class ConfigError(ValueError):
    """Excepción para errores críticos de configuración."""
    pass

# Clase Base de Configuración
class Config:
    """
    Configuración base compartida. Lee valores clave del entorno una vez.
    Las clases específicas de entorno heredan y pueden sobrescribir estos valores.
    """
    ENV: str = "base"
    SECRET_KEY: Optional[str] = os.environ.get('SECRET_KEY')
    WTF_CSRF_ENABLED: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = 'Lax'
    SESSION_COOKIE_SECURE: bool = False
    DEFAULT_UPLOAD_PATH: Path = INSTANCE_DIR / 'uploads'
    UPLOAD_FOLDER: str = os.environ.get('UPLOAD_FOLDER', str(DEFAULT_UPLOAD_PATH))
    Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
    try:
        max_content_env = os.environ.get('MAX_CONTENT_LENGTH', '16777216') # 16 MB
        MAX_CONTENT_LENGTH: int = int(max_content_env)
        if MAX_CONTENT_LENGTH <= 0:
                raise ValueError("MAX_CONTENT_LENGTH debe ser positivo.")
    except (ValueError, TypeError) as e:
        config_logger.warning(f"Valor inválido para MAX_CONTENT_LENGTH ('{os.environ.get('MAX_CONTENT_LENGTH')}') en.env: {e}. Usando default 16MB.")
        MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS: Set[str] = {'xlsx', 'xls', 'csv'}
    # DATABASE_URL: Optional[str] = os.environ.get('DATABASE_URL') or f"sqlite:///{INSTANCE_DIR / 'pricing_data.db'}"
    # SQLALCHEMY_DATABASE_URI: Optional[str] = DATABASE_URL
    # SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    DEBUG: bool = False
    TESTING: bool = False
    HOST: str = os.environ.get('HOST', '127.0.0.1')
    try:
        PORT: int = int(os.environ.get('PORT', '5000'))
    except (ValueError, TypeError):
        config_logger.warning(f"Valor inválido para PORT ('{os.environ.get('PORT')}') en.env. Usando default 5000.")
        PORT: int = 5000
    APP_VERSION: str = os.environ.get('APP_VERSION', '0.1.0-dev')
    REQUIRED_VARS: List[str] = [] # Base class has no required vars itself

    @classmethod
    def validate(cls):
        """
        Valida que las variables listadas en REQUIRED_VARS estén presentes y no vacías.
        Lanza ConfigError si falta alguna variable crítica para el entorno actual.
        """
        missing = []
        for var_name in cls.REQUIRED_VARS:
            value = getattr(cls, var_name, None)
            if not value: # Checks for None or empty string
                missing.append(var_name)

        if missing:
            error_message = f"Configuración inválida para el entorno '{cls.ENV}'. Faltan variables críticas: {missing}"
            config_logger.error(error_message)
            raise ConfigError(error_message) # Stop app startup if critical config is missing
        else:
            if cls.REQUIRED_VARS:
                config_logger.info(f"[Config] Validación para entorno '{cls.ENV}' completada. Variables requeridas ({cls.REQUIRED_VARS}) presentes.")

# Configuración de Desarrollo
class DevelopmentConfig(Config):
    """Configuración para desarrollo: DEBUG=True, SECRET_KEY insegura por defecto (con warning)."""
    ENV = "development"
    DEBUG = True
    SECRET_KEY = Config.SECRET_KEY or 'change-this-insecure-default-secret-key-in-.env'
    if SECRET_KEY == 'change-this-insecure-default-secret-key-in-.env':
        print("\n" + "*"*70)
        print(" ADVERTENCIA DE SEGURIDAD: Estás usando la SECRET_KEY por defecto en DESARROLLO.")
        print(" -> Define la variable SECRET_KEY en tu archivo.env para testing local seguro.")
        print(" -> ¡NUNCA USES ESTA CLAVE POR DEFECTO EN PRODUCCIÓN!")
        print("*"*70 + "\n")
        config_logger.warning("SECRET_KEY por defecto insegura en uso para desarrollo. Define SECRET_KEY en.env.")
    try:
        PORT = int(os.environ.get('DEV_PORT', Config.PORT))
    except (ValueError, TypeError):
        config_logger.warning(f"Valor inválido para DEV_PORT ('{os.environ.get('DEV_PORT')}') en.env. Usando puerto {Config.PORT}.")
        PORT = Config.PORT
    REQUIRED_VARS = [] # No specific vars strictly required to *start* in dev

# Configuración de Pruebas
class TestingConfig(Config):
    """Configuración para pruebas: TESTING=True, CSRF desactivado, SECRET_KEY fija."""
    ENV = "testing"
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'testing-secret-key-for-consistency' # Fixed key for tests
    # DATABASE_URL = 'sqlite:///:memory:' # Example: In-memory DB for fast tests
    # SQLALCHEMY_DATABASE_URI = DATABASE_URL
    # MAX_CONTENT_LENGTH = 5 * 1024 * 1024 # Example: Specific limit for tests
    # REFINED: No need to validate the hardcoded SECRET_KEY here.
    # REQUIRED_VARS exists mainly to check for external (env) variables.
    REQUIRED_VARS = []

# Configuración de Producción
class ProductionConfig(Config):
    """Configuración para producción: DEBUG=False, Cookies seguras, requiere SECRET_KEY."""
    ENV = "production"
    DEBUG = False
    TESTING = False
    # --- Critical Variables Required for Production ---
    REQUIRED_VARS = ['SECRET_KEY'] # SECRET_KEY MUST be set via environment
    SECRET_KEY = Config.SECRET_KEY # Inherited from base, checked by validation
    # --- Enhanced Security for Production ---
    SESSION_COOKIE_SECURE = True  # Require HTTPS
    SESSION_COOKIE_SAMESITE = 'Strict'
    # --- WSGI Server Configuration ---
    HOST = os.environ.get('HOST', '0.0.0.0') # Listen on all available interfaces
    try:
        PORT = int(os.environ.get('PORT', '8000')) # Common port for Gunicorn/uWSGI
    except (ValueError, TypeError):
        config_logger.warning(f"Valor inválido para PORT ('{os.environ.get('PORT')}') en producción. Usando default 8000.")
        PORT = 8000
    # Note: Validation (ProductionConfig.validate()) should be called from create_app

# Alias para DevelopmentConfig como fallback
class DefaultConfig(DevelopmentConfig):
    """Alias for DevelopmentConfig, used as fallback."""
    pass

# Mapeo para carga por nombre
config_by_name = dict(
    development=DevelopmentConfig,
    testing=TestingConfig,
    production=ProductionConfig,
    default=DefaultConfig
)

# --- Bloque de prueba (si se ejecuta python config.py) ---
if __name__ == '__main__':
    print(f"\n" + "="*70)
    print(f"** Verificación de Configuración Ejecutando config.py Directamente **")
    print(f"Directorio Base (BASE_DIR): {BASE_DIR}")
    print(f"Directorio Instancia (INSTANCE_DIR): {INSTANCE_DIR}")
    print(f"Carpeta de Subidas (UPLOAD_FOLDER): {Config.UPLOAD_FOLDER}")
    print(f"Intentando cargar desde.env: {'Sí' if 'dotenv_path' in locals() and dotenv_path.is_file() else 'No'}")
    print("="*70)

    for name, config_class in config_by_name.items():
        print(f"\n--- Verificando: {name} ({config_class.__name__}) ---")
        try:
            # Simula la validación que haría create_app
            Config.validate.__func__(config_class) # Llama validate de Config en la clase específica
            print(f"-> Validación OK (basada en REQUIRED_VARS: {config_class.REQUIRED_VARS})")

            key_display = f"{str(config_class.SECRET_KEY)[:10]}..." if config_class.SECRET_KEY else "None/Vacío"
            print(f"    ENV: {config_class.ENV}, DEBUG: {config_class.DEBUG}, TESTING: {config_class.TESTING}")
            print(f"    SECRET_KEY: {key_display}")
            print(f"    PORT: {config_class.PORT}, HOST: {config_class.HOST}")
            if name == 'production':
                print(f"    COOKIE_SECURE: {config_class.SESSION_COOKIE_SECURE}, COOKIE_SAMESITE: {config_class.SESSION_COOKIE_SAMESITE}")
            if name == 'development' and config_class.SECRET_KEY == 'change-this-insecure-default-secret-key-in-.env':
                    print("    *** ADVERTENCIA: Usando SECRET_KEY insegura por defecto ***")

        except ConfigError as e:
            print(f"-> FALLO DE VALIDACIÓN: {e}")
        except Exception as e:
            print(f"-> Ocurrió un error inesperado al verificar {name}: {e}")

    print("\n" + "="*70)
    print("** Verificación Completada **")
    print("Recuerda definir las variables de entorno necesarias en tu archivo.env")
    print("o directamente en el entorno del sistema, especialmente para producción.")
    print("="*70)
