# pricing_dashboard/app.py
# -*- coding: utf-8 -*-
"""
Application Factory para el Dashboard de Pricing Automatizado. (Versión Final Revisada v4)

Orquesta la creación y configuración de la aplicación Flask, incorporando:
- Carga de configuración multi-entorno y validación avanzada.
- Configuración de logging robusta.
- Inicialización de extensiones Flask.
- Registro explícito de Blueprints con importaciones absolutas desde 'proyect'.
- Definición de manejadores de errores y hooks de petición con seguridad mejorada (CSP, HSTS).
- Inyección de contexto para plantillas.
- Chequeos críticos de arranque (permisos, endpoints, configuración).
- Soporte opcional para despliegues detrás de proxy inverso (ProxyFix).
"""

# 1. Standard Library Imports
import os
import logging
import logging.config
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# 2. Third-Party Imports
from dotenv import load_dotenv, find_dotenv
from flask import (Flask, render_template, session, redirect, url_for,
                   request, current_app, g, flash, jsonify)
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix # Para detectar HTTPS detrás de proxy (R4 - C2)
from flask_wtf.csrf import CSRFProtect

# 3. Local Application Imports
try:
    # *** CORREGIDO (R4.1 - C1): Importar TODAS las clases de config usadas ***
    from config import (
        config_by_name,
        ConfigError,
        DefaultConfig,   # <-- Añadida
        TestingConfig,   # <-- Añadida
        DevelopmentConfig,
        ProductionConfig
    )
except ImportError as e:
    logging.basicConfig(level=logging.CRITICAL)
    logging.critical(f"CRÍTICO: No se pudo importar desde 'config'. ¿Existe 'config.py'? ¿Clases definidas? Error: {e}")
    raise SystemExit(f"Fallo crítico al importar 'config': {e}") from e

# --- Configuración inicial de Logging (ANTES de crear la app) ---
logging_conf_path = Path(__file__).parent / 'logging.conf'
if logging_conf_path.exists() and logging_conf_path.is_file():
    try:
        logging.config.fileConfig(str(logging_conf_path), disable_existing_loggers=False)
        initial_logger = logging.getLogger(__name__)
        initial_logger.info(f"Bootstrap: Logging configurado desde: {logging_conf_path}")
    except Exception as e:
        logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(levelname)-5s] %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        initial_logger = logging.getLogger(__name__)
        initial_logger.error(f"Bootstrap: Error configurando logging desde {logging_conf_path}: {e}. Usando config básica.", exc_info=True)
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-5s] %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    initial_logger = logging.getLogger(__name__)
    initial_logger.warning(f"Bootstrap: Archivo '{logging_conf_path}' no encontrado. Usando config básica de logging.")

# --- Carga temprana de variables de entorno ---
env_file_path = find_dotenv("project.env", raise_error_if_not_found=False) or \
                find_dotenv(".env", raise_error_if_not_found=False)
if env_file_path:
    initial_logger.info(f"Bootstrap: Cargando variables de entorno desde: {env_file_path}")
    load_dotenv(dotenv_path=env_file_path, override=True)
else:
    initial_logger.info("Bootstrap: No se encontró archivo .env o project.env. Procediendo sin él.")

# --- Instancia Global de Extensiones ---
csrf = CSRFProtect()
initial_logger.debug("Bootstrap: Instancias globales de extensiones creadas (inicialización diferida).")


# ==================================
# SECCIÓN 1: Application Factory
# ==================================
def create_app(config_name_override: Optional[str] = None) -> Flask:
    """Crea, configura y retorna la instancia de la aplicación Flask."""
    initial_logger.info("Iniciando proceso create_app...")

    app = Flask(__name__,
                instance_relative_config=True,
                static_folder='static',
                template_folder='templates'
               )
    logger = app.logger
    logger.info("Instancia Flask creada. Usando app.logger a partir de ahora.")

    # --- Fase 1: Carga y Validación de Configuración ---
    logger.debug("Iniciando carga y validación de configuración...")
    chosen_config_name = config_name_override or os.getenv('FLASK_CONFIG') or 'default'
    app.config['CONFIG_NAME'] = chosen_config_name
    # Asegúrate que config.py define 'default' en config_by_name
    logger.info(f"Configuración solicitada: '{chosen_config_name}'")

    # 1. Cargar config desde clase (Ahora todas las clases están importadas R4.1)
    try: config_class_to_load = config_by_name[chosen_config_name]
    except KeyError:
        logger.warning(f"Nombre de config '{chosen_config_name}' inválido. Usando 'default'.")
        chosen_config_name = 'default'
        config_class_to_load = config_by_name[chosen_config_name]
        app.config['CONFIG_NAME'] = chosen_config_name

    try:
        config_object = config_class_to_load()
        app.config.from_object(config_object)
        logger.info(f"Config base cargada desde clase: {config_class_to_load.__name__}")
    except Exception as e:
        logger.critical(f"CRÍTICO: Error al cargar config desde {config_class_to_load.__name__}: {e}", exc_info=True)
        raise SystemExit(f"Fallo crítico al cargar config base {config_class_to_load.__name__}")

    # 2. Crear directorio 'instance'
    try: Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    except OSError as e: logger.warning(f"No se pudo crear/acceder dir instancia '{app.instance_path}': {e}.")

    # 3. Cargar config desde instance/config.py (si existe)
    instance_config_py_path = Path(app.instance_path) / 'config.py'
    if instance_config_py_path.is_file():
        logger.info(f"Intentando cargar config desde: {instance_config_py_path}")
        try:
            app.config.from_pyfile(str(instance_config_py_path), silent=False)
            logger.info(f"Config adicional aplicada desde: {instance_config_py_path}")
        except Exception as e: logger.error(f"Error al cargar config desde {instance_config_py_path}: {e}.", exc_info=True)
    else: logger.debug(f"Archivo '{instance_config_py_path}' no encontrado, omitiendo.")

    # 4. Aplicar overrides desde variables de entorno (prefijo FLASK_)
    #    (R4.5 - C1) Bucle manual para compatibilidad con Flask < 2.2.
    #    Si necesitas Flask >= 2.2, puedes reemplazar esto por: app.config.from_prefixed_env()
    logger.info("Aplicando overrides desde variables de entorno (prefijo FLASK_)...")
    prefix = 'FLASK_'
    applied_overrides = 0
    for key, value in os.environ.items():
        if key.startswith(prefix):
            config_key = key[len(prefix):]
            processed_value: Any
            if value.lower() in ('true', 'false'): processed_value = value.lower() == 'true'
            elif value.isdigit(): processed_value = int(value)
            else:
                try: processed_value = float(value)
                except ValueError: processed_value = value
            app.config[config_key] = processed_value
            logger.debug(f"  Override aplicado: FLASK_{config_key} -> {config_key} = {processed_value} (Tipo: {type(processed_value).__name__})")
            applied_overrides += 1
    logger.info(f"Se aplicaron {applied_overrides} overrides desde variables de entorno.")

    # 5. Asegurar directorio de UPLOADS y guardar Path object
    try:
        upload_folder_str = app.config['UPLOAD_FOLDER']
        upload_folder = Path(upload_folder_str)
        if not upload_folder.is_absolute():
            base_dir = Path(__file__).resolve().parent
            upload_folder = (base_dir / upload_folder_str).resolve()
            app.config['UPLOAD_FOLDER'] = str(upload_folder)
        logger.info(f"Directorio de subidas configurado: {upload_folder}")
        upload_folder.mkdir(parents=True, exist_ok=True)
        app.config['UPLOAD_FOLDER_PATH'] = upload_folder
    except KeyError:
        logger.critical("CRÍTICO: 'UPLOAD_FOLDER' no definida en la configuración final.")
        raise SystemExit("Error crítico: Falta la configuración UPLOAD_FOLDER.")
    except OSError as e:
        logger.critical(f"CRÍTICO: No se pudo crear UPLOAD_FOLDER '{upload_folder}'. Error: {e}", exc_info=True)
        raise SystemExit(f"Error crítico: No se puede crear UPLOAD_FOLDER: {e}")

    # 6. VALIDACIÓN DE CONFIGURACIÓN CRÍTICA desde el objeto config
    logger.info(f"Validando configuración crítica (método validate) para entorno '{chosen_config_name}'...")
    try:
        config_object.validate() # Llama al método validate() de la clase Config
        logger.info("Validación de configuración (método validate) completada con éxito.")
    except ConfigError as e:
        logger.critical(f"FALLO VALIDACIÓN CONFIG (validate): {e}")
        raise SystemExit(f"Configuración inválida para entorno '{chosen_config_name}': {e}") from e
    except AttributeError:
         logger.warning(f"Clase config '{config_class_to_load.__name__}' no tiene método 'validate'. Se omite este paso.")
    except Exception as e:
         logger.critical(f"Error inesperado validando configuración (validate): {e}", exc_info=True)
         raise SystemExit(f"Error inesperado validando configuración: {e}") from e

    logger.info("Carga y validación de configuración completada.")
    # --- Fin Fase 1 ---

    # --- Fase 2: Logging Definitivo ---
    configure_logging(app)
    logger.info(f"Sistema de logging operativo (Entorno: {app.config.get('CONFIG_NAME', 'N/A')})")

    # --- Fase 3: Inicialización de Extensiones ---
    initialize_extensions(app)

    # --- Fase 4: Registro de Blueprints ---
    register_blueprints(app)

    # --- Fase 4.1: Verificación de Endpoints Críticos (Post-Registro) ---
    check_critical_endpoints(app) # (R4.4 - C1) Verificado que se llama aquí

    # --- Fases 5-8: Registro de Handlers, Hooks y Chequeos Finales ---
    register_error_handlers(app)
    register_request_hooks(app)
    register_context_processors(app)
    perform_critical_checks(app)

    # --- Fase 9: Aplicar Middlewares Adicionales (Ej: ProxyFix) ---
    # (R4 - C2) Aplicar ProxyFix si está configurado (para despliegues detrás de proxy)
    if app.config.get('USE_PROXY_FIX', False):
        # x_proto=1: Confía en X-Forwarded-Proto para detectar HTTPS
        # x_host=1: Confía en X-Forwarded-Host para determinar el host correcto
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
        logger.info("ProxyFix middleware aplicado (x_proto=1, x_host=1). Asegúrate que tu proxy envía estas cabeceras.")
    else:
        logger.debug("ProxyFix middleware no aplicado (USE_PROXY_FIX no establecido o False en config).")


    # --- Finalización ---
    final_config_name = app.config.get('CONFIG_NAME', 'Desconocida')
    logger.info(f"App '{app.name}' creada y configurada exitosamente (Entorno: {final_config_name}).")
    logger.info("="*40 + " Factoría Completada " + "="*40)
    return app


# ==================================
# SECCIÓN 3: Configuración de Logging (Auxiliar)
# ==================================
# (Sin cambios respecto a la versión anterior, ya era robusta)
def configure_logging(app: Flask):
    """Asegura que el logger de Flask tenga handlers configurados post-config."""
    logger = app.logger
    if not logger.handlers:
        logger.warning("El logger de Flask no tenía handlers post-config. Configurando logging básico.")
        _setup_basic_logging(app)
    else:
        logger.debug("El logger de Flask ya tiene handlers.")

def _setup_basic_logging(app: Flask):
    """Configura un logging básico a consola y opcionalmente a archivo."""
    logger = app.logger
    log_level_name = 'DEBUG' if app.debug else app.config.get('LOG_LEVEL', 'INFO')
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)
    log_format = app.config.get('LOG_FORMAT',
                                '%(asctime)s [%(levelname)-5s] %(name)s: %(message)s [in %(pathname)s:%(lineno)d]')
    date_format = app.config.get('LOG_DATE_FORMAT', '%Y-%m-%d %H:%M:%S')
    formatter = logging.Formatter(log_format, date_format)

    for handler in logger.handlers[:]: logger.removeHandler(handler)

    handlers = []
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    handlers.append(stream_handler)

    log_file_status = "Archivo: No configurado"
    if app.config.get('LOG_TO_FILE', True):
        log_filename_str = app.config.get('LOG_FILENAME', 'app.log')
        log_filename = Path(app.instance_path) / log_filename_str
        try:
            log_filename.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_filename, encoding='utf-8')
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
            log_file_status = f"Archivo: {log_filename}"
        except OSError as e:
            logger.error(f"No se pudo crear/acceder archivo log '{log_filename}'. Error: {e}")
            log_file_status = f"Archivo: Deshabilitado (Error: {e})"
    else: log_file_status = "Archivo: Deshabilitado (Configuración)"

    logger.setLevel(log_level)
    for handler in handlers: logger.addHandler(handler)
    logger.propagate = False
    logger.info(f"Logging básico configurado (Nivel: {log_level_name}, Consola: Activa, {log_file_status})")


# ==================================
# SECCIÓN 4: Inicialización de Extensiones
# ==================================
# (Sin cambios)
def initialize_extensions(app: Flask):
    """Inicializa las extensiones Flask con la instancia de la app."""
    logger = app.logger
    logger.info("Inicializando extensiones Flask...")
    try:
        csrf.init_app(app)
        logger.info(" - CSRFProtect inicializado.")
        # Inicializar otras extensiones aquí si es necesario
        logger.info("Inicialización de extensiones completada.")
    except Exception as e:
        logger.critical(f"Error CRÍTICO inicializando extensiones: {e}", exc_info=True)
        raise RuntimeError(f"Fallo crítico inicializando extensiones: {e}") from e


# ==================================
# SECCIÓN 5: Registro de Blueprints (Absoluto desde 'proyect')
# ==================================
def register_blueprints(app: Flask):
    """Registra los Blueprints de la aplicación usando importaciones absolutas desde 'proyect'."""
    logger = app.logger
    logger.info("Registrando Blueprints (importaciones absolutas desde 'proyect')...")
    try:
        # *** CORREGIDO (R4.2 - C1): Usar importaciones absolutas desde 'proyect' ***
        # Asume la estructura:
        # pricing_dashboard/
        #  ├─ app.py        <-- Este archivo
        #  ├─ proyect/      <-- Subcarpeta con blueprints
        #  │  ├─ main/
        #  │  ├─ maxdiff/
        #  │  └─ ...
        #  └─ __init__.py   <-- Necesario para que 'proyect' sea paquete
        # También asume que cada subpaquete (main, maxdiff) tiene un __init__.py
        # que expone la variable 'bp' (e.g., from .routes import bp)
        from proyect.main import bp as main_bp
        from proyect.maxdiff import bp as maxdiff_bp
        from proyect.comstrat import bp as comstrat_bp
        from proyect.moca import bp as moca_bp
        # from proyect.series import bp as series_bp # Descomentar cuando exista

        app.register_blueprint(main_bp)
        logger.info(f" - Blueprint '{main_bp.name}' registrado en '{main_bp.url_prefix or '/'}'")
        app.register_blueprint(maxdiff_bp, url_prefix='/maxdiff')
        logger.info(f" - Blueprint '{maxdiff_bp.name}' registrado en '{maxdiff_bp.url_prefix}'")
        app.register_blueprint(comstrat_bp, url_prefix='/comstrat')
        logger.info(f" - Blueprint '{comstrat_bp.name}' registrado en '{comstrat_bp.url_prefix}'")
        app.register_blueprint(moca_bp, url_prefix='/moca')
        logger.info(f" - Blueprint '{moca_bp.name}' registrado en '{moca_bp.url_prefix}'")
        # Registrar otros blueprints aquí...

        logger.info("Registro de Blueprints finalizado.")

    except ImportError as e:
        logger.critical(f"CRÍTICO: Fallo al importar módulo Blueprint desde 'proyect': {e}. ¿Existe 'proyect/'? ¿Tiene '__init__.py'? ¿Submódulos correctos?", exc_info=True)
        raise SystemExit(f"Arranque abortado: No se pudo importar módulo Blueprint {e}") from e
    except AttributeError as e:
         logger.critical(f"CRÍTICO: Fallo al encontrar 'bp' en módulo Blueprint importado desde 'proyect': {e}. Asegúrate que cada '__init__.py' del blueprint expone 'bp'.", exc_info=True)
         raise SystemExit(f"Arranque abortado: Falta 'bp' en módulo Blueprint {e}") from e
    except Exception as e:
        logger.critical(f"CRÍTICO: Error inesperado registrando blueprints: {e}", exc_info=True)
        raise SystemExit(f"Arranque abortado: Error inesperado registrando blueprints: {e}") from e

# ==================================
# SECCIÓN 5.1: Verificación de Endpoints Críticos
# ==================================
# (Sin cambios)
def check_critical_endpoints(app: Flask):
    """Verifica la existencia de endpoints críticos después de registrar blueprints."""
    logger = app.logger
    logger.info("Verificando existencia de endpoints críticos...")
    critical_endpoints = ['main.upload']
    missing = []
    for endpoint in critical_endpoints:
        if endpoint not in app.view_functions:
            missing.append(endpoint)
            logger.error(f"Endpoint crítico '{endpoint}' NO encontrado después de registrar blueprints. ¡Esto puede causar errores!")
    if missing:
        raise SystemExit(f"Arranque abortado: Faltan endpoints críticos: {', '.join(missing)}")
    else:
        logger.info("Endpoints críticos verificados con éxito.")


# ==================================
# SECCIÓN 6: Manejadores de Errores
# ==================================
# (Sin cambios)
def register_error_handlers(app: Flask):
    """Registra manejadores para errores HTTP comunes y excepciones generales."""
    logger = app.logger
    logger.info("Registrando manejadores de errores...")

    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException):
        log_level = logging.WARNING if 400 <= e.code < 500 else logging.ERROR
        remote_addr = request.remote_addr or 'Desconocida'
        logger.log(log_level,
                   f"Error HTTP {e.code} {e.name} para {request.method} {request.path} [IP: {remote_addr}]: {getattr(e, 'description', 'N/A')}",
                   exc_info=(e.code >= 500))
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            response = jsonify(error=e.name, message=getattr(e, 'description', "Error HTTP"), code=e.code)
            response.status_code = e.code
            return response
        return render_template('error.html', error_code=e.code, error_name=e.name.replace("'", ""), error_description=getattr(e, 'description', "Ocurrió un error.")), e.code

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_entity_too_large(e: RequestEntityTooLarge):
        max_size_mb = 0
        try:
            max_size_bytes = app.config.get('MAX_CONTENT_LENGTH', 0)
            if max_size_bytes: max_size_mb = max_size_bytes / (1024 * 1024)
            message = f"El archivo enviado es demasiado grande. El límite es {max_size_mb:.1f} MB."
        except Exception: message = "El archivo enviado es demasiado grande."
        logger.warning(f"Intento de subida demasiado grande (413). Límite: {max_size_mb:.1f} MB. URL: {request.url}, IP: {request.remote_addr}")
        flash(message, 'danger')
        redirect_url = url_for('main.upload')
        return redirect(redirect_url, code=303)

    @app.errorhandler(Exception)
    def handle_generic_exception(e: Exception):
        remote_addr = request.remote_addr or 'Desconocida'
        logger.critical(f"Excepción NO MANEJADA: {request.method} {request.path} [IP: {remote_addr}]: {type(e).__name__}: {e}", exc_info=True)
        error_description = "Ocurrió un error inesperado en el servidor. Por favor, inténtalo de nuevo más tarde."
        if app.debug:
            import traceback
            error_description = f"Error interno: {type(e).__name__}: {e}\n<pre>{traceback.format_exc()}</pre>"
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            response = jsonify(error="Internal Server Error", message="Ocurrió un error inesperado.", code=500)
            response.status_code = 500
            return response
        return render_template('error.html', error_code=500, error_name="Internal Server Error", error_description=error_description), 500

    logger.info("Manejadores de errores registrados.")


# ==================================
# SECCIÓN 7: Hooks de Petición (con CSP Actualizado)
# ==================================
def register_request_hooks(app: Flask):
    """Registra funciones que se ejecutan antes y después de cada petición."""
    logger = app.logger
    logger.info("Registrando hooks de petición (before/after_request)...")

    @app.before_request
    def before_request_tasks():
        g.request_start_time = time.monotonic()

    @app.after_request
    def after_request_tasks(response):
        duration_ms = -1
        if hasattr(g, 'request_start_time') and g.request_start_time:
            duration_ms = (time.monotonic() - g.request_start_time) * 1000
        logger.info(f"{request.method} {request.path} [{request.remote_addr or 'N/A'}] -> {response.status_code} ({duration_ms:.2f} ms)")
        clear_temporary_session_keys(app)

        # --- Cabeceras de Seguridad ---
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Content Security Policy (CSP) - *** EJEMPLO ACTUALIZADO (R4 - C2) ***
        # ¡¡¡ ESTA POLÍTICA ES UN EJEMPLO Y DEBE SER AJUSTADA !!!
        # Analiza las dependencias de tu frontend (JS/CSS/Fuentes de CDNs, etc.)
        # y modifica las directivas ('script-src', 'style-src', etc.) para permitirlas.
        # Una CSP demasiado restrictiva romperá tu sitio. Una demasiado laxa no protege.
        # Herramientas como https://report-uri.com/home/generate o la consola del navegador ayudan.
        # Este ejemplo permite self, inline styles (riesgoso pero común) y un CDN popular.
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; " # Por defecto, solo permite recursos del mismo origen
            "script-src 'self' https://cdn.jsdelivr.net; " # Permite JS propio y de jsdelivr
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; " # Permite CSS propio, inline (¡cuidado!) y de jsdelivr
            "img-src 'self' data: https://*; " # Permite imágenes propias, data URIs, y de cualquier HTTPS
            "font-src 'self' https://*; " # Permite fuentes propias y de cualquier HTTPS
            "object-src 'none'; " # Deshabilita plugins
            "frame-ancestors 'self'; " # Evita clickjacking
            "form-action 'self'; " # Permite enviar formularios solo a self
            "base-uri 'self';"
            # "report-uri /csp-report-endpoint;" # Opcional: para recibir reportes de violaciones CSP
        )
        logger.debug(f"Cabecera CSP establecida (¡Revisar y ajustar política!): {response.headers['Content-Security-Policy'][:100]}...")


        # HTTP Strict Transport Security (HSTS)
        if not app.debug and request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            logger.debug("Cabecera HSTS añadida (Producción + HTTPS).")
        elif not request.is_secure and not app.debug:
             logger.warning("Petición HTTP recibida en producción. Considera forzar HTTPS y habilitar HSTS.")

        return response

    logger.info("Hooks de petición registrados.")


# ==================================
# SECCIÓN 8: Funciones Auxiliares (Limpieza Sesión)
# ==================================
# (Sin cambios)
def clear_temporary_session_keys(app: Flask):
    """Limpia claves específicas de la sesión al salir de flujos de análisis."""
    try:
        if not request or not request.endpoint: return
        current_endpoint = request.endpoint
    except RuntimeError: return

    exempt_bp_prefixes = ('maxdiff.', 'comstrat.', 'moca.', 'series.')
    always_exempt_eps = {'main.dashboard', 'main.upload', 'main.preview', 'main.export_options', 'static'}
    is_exempt = current_endpoint in always_exempt_eps or \
                any(current_endpoint.startswith(pfx) for pfx in exempt_bp_prefixes)

    if is_exempt: return

    keys_to_clear = ['uploaded_file_path', 'original_filename', 'analysis_type',
                     'preview_data', 'dataframe_schema', 'job_id', 'task_id',
                     'analysis_results_summary']
    cleared_keys = []
    if session:
        for key in keys_to_clear:
            if key in session:
                session.pop(key, None)
                cleared_keys.append(key)
        if cleared_keys:
            app.logger.debug(f"Limpiando {len(cleared_keys)} claves de sesión al salir del flujo (Endpoint: {current_endpoint}): {', '.join(cleared_keys)}")


# ==================================
# SECCIÓN 9: Procesadores de Contexto
# ==================================
# (Sin cambios)
def register_context_processors(app: Flask):
    """Registra funciones que inyectan variables en el contexto de las plantillas Jinja2."""
    logger = app.logger
    logger.info("Registrando procesadores de contexto para plantillas...")

    @app.context_processor
    def inject_global_template_variables() -> Dict[str, Any]:
        def _safe_url_for(endpoint: str, **values) -> str:
            try: return url_for(endpoint, **values)
            except Exception as e:
                current_app.logger.warning(f"Fallo al generar URL para endpoint '{endpoint}' con valores {values}: {e}", exc_info=False)
                return "#"
        def _get_analysis_base_url(bp_name: str) -> str: return _safe_url_for(f"{bp_name}.index")
        key_endpoints = {
            'home': _safe_url_for('main.dashboard'), 'upload': _safe_url_for('main.upload'),
            'export_base': _safe_url_for('main.export_options'),
            'maxdiff_base': _get_analysis_base_url('maxdiff'),
            'comstrat_base': _get_analysis_base_url('comstrat'),
            'moca_base': _get_analysis_base_url('moca'),
        }
        return dict(
            config=current_app.config,
            endpoints=key_endpoints,
            now=datetime.utcnow,
            safe_url_for=_safe_url_for
        )

    logger.info("Procesadores de contexto registrados.")


# ==================================
# SECCIÓN 10: Validaciones de Arranque (Sistema y Configuración Final)
# ==================================
# (Sin cambios en la lógica, ya usaba touch/unlink)
def perform_critical_checks(app: Flask):
    """Realiza validaciones críticas (permisos, config final) antes de arrancar."""
    logger = app.logger
    logger.info("Realizando validaciones críticas de sistema y configuración final...")
    errors_found = []
    insecure_secrets = {
        'dev', 'secret', 'password', 'change-this-insecure-default-secret-key-in-.env',
        '123456789', 'admin', 'root', None, '', 'configurestrongsecretkey'
    }

    # 1. Chequeo de SECRET_KEY (Final)
    secret_key = app.config.get('SECRET_KEY')
    is_prod = not app.debug and not app.testing
    logger.info(f"Verificando SECRET_KEY final (Entorno prod: {is_prod})...")
    if not secret_key:
        msg = "CRÍTICO: SECRET_KEY no está definida en la configuración final."
        logger.critical(msg); errors_found.append(msg)
    elif is_prod:
        if secret_key in insecure_secrets:
             msg = f"CRÍTICO: SECRET_KEY es insegura ('{str(secret_key)[:10]}...') en producción."
             logger.critical(msg); errors_found.append(msg)
        elif len(secret_key) < 32:
            msg = f"ADVERTENCIA FUERTE: SECRET_KEY en producción es corta ({len(secret_key)} chars). Se recomienda >= 32."
            logger.warning(msg)
        else:
            logger.info(" - SECRET_KEY parece segura para producción.")
    else: # Dev/Test
        if secret_key in insecure_secrets:
            logger.warning(f" - ADVERTENCIA (Dev/Test): SECRET_KEY es insegura ('{str(secret_key)[:10]}...').")
        elif len(secret_key) < 16:
             logger.warning(f" - ADVERTENCIA (Dev/Test): SECRET_KEY es corta ({len(secret_key)} chars).")
        else:
            logger.info(" - SECRET_KEY configurada para desarrollo/testing.")

    # 2. Chequeo de UPLOAD_FOLDER (Permisos Robustos con touch/unlink)
    upload_folder = app.config.get('UPLOAD_FOLDER_PATH')
    logger.info(f"Verificando permisos R/W en UPLOAD_FOLDER: {upload_folder}")
    if upload_folder and isinstance(upload_folder, Path) and upload_folder.is_dir():
        test_filename = f"permission_test_{os.getpid()}.tmp"
        test_file = upload_folder / test_filename
        try:
            test_file.touch()
            logger.debug(f" - Permiso de escritura verificado (touch {test_file})")
            test_file.unlink()
            logger.debug(f" - Permiso de lectura/borrado verificado (unlink {test_file})")
            logger.info(f" - UPLOAD_FOLDER '{upload_folder}' operativo (permisos R/W verificados con touch/unlink).")
        except OSError as e:
            msg = f"FALLO DE PERMISOS en UPLOAD_FOLDER '{upload_folder}'. Error: {e}"
            logger.critical(msg, exc_info=True); errors_found.append(msg)
            if test_file.exists():
                try: test_file.unlink()
                except OSError: logger.warning(f"No se pudo limpiar archivo de test {test_file}")
        except Exception as e:
            msg = f"Error inesperado verificando permisos en UPLOAD_FOLDER '{upload_folder}'. Error: {e}"
            logger.critical(msg, exc_info=True); errors_found.append(msg)
    elif not upload_folder or not isinstance(upload_folder, Path):
        msg = "Configuración de UPLOAD_FOLDER inválida o no es un objeto Path."
        logger.critical(msg); errors_found.append(msg)
    elif not upload_folder.is_dir():
        msg = f"Ruta UPLOAD_FOLDER NO ES UN DIRECTORIO: {upload_folder}"
        logger.critical(msg); errors_found.append(msg)

    # 3. Chequeo de otras claves obligatorias post-overrides
    mandatory_keys = ['MAX_CONTENT_LENGTH'] # Añadir otras si aplica
    logger.info(f"Verificando existencia de claves de config obligatorias: {mandatory_keys}...")
    missing_keys = [key for key in mandatory_keys if key not in app.config]
    if missing_keys:
        msg = f"Faltan claves de configuración obligatorias: {', '.join(missing_keys)}"
        logger.critical(msg); errors_found.append(msg)
    else: logger.info(" - Claves obligatorias presentes.")

    # Resultado final
    if errors_found:
        logger.critical("*" * 80 + "\nFALLARON LAS VALIDACIONES CRÍTICAS DEL SISTEMA/CONFIG:")
        for i, error in enumerate(errors_found, 1): logger.critical(f"  {i}. {error}")
        logger.critical("La aplicación no puede continuar de forma segura.\n" + "*" * 80)
        raise SystemExit("Arranque abortado debido a errores críticos del sistema/configuración.")
    else: logger.info("Validaciones críticas de sistema y configuración superadas con éxito.")


# ==================================
# SECCIÓN 11: Punto de Entrada (Solo para Desarrollo Local)
# ==================================
# (Sin cambios, ya tenía la advertencia WSGI)
if __name__ == '__main__':
    # --- ADVERTENCIA MUY IMPORTANTE ---
    # Este bloque es SOLO para desarrollo local fácil.
    # NUNCA uses `flask run` o este script directamente en PRODUCCIÓN.
    # Usa un servidor WSGI como Gunicorn o uWSGI.
    # ----------------------------------------------------
    entry_logger = logging.getLogger(__name__)
    entry_logger.warning("="*80 + "\n*** EJECUTANDO EN MODO SCRIPT DIRECTO (SOLO DESARROLLO) ***\n" + "="*80)
    try:
        app = create_app()
    except SystemExit as e:
        entry_logger.critical(f"La creación de la aplicación falló con SystemExit: {e}. Revisa logs anteriores.")
        exit(1)
    except Exception as e:
        entry_logger.critical(f"Error CRÍTICO inesperado durante create_app(): {e}", exc_info=True)
        exit(1)

    host = app.config.get('HOST', '127.0.0.1')
    port = int(app.config.get('PORT', 5001))
    debug = app.debug
    reloader = app.config.get('USE_RELOADER', debug)
    cfg_name = app.config.get('CONFIG_NAME', 'N/A')

    app.logger.info("*" * 80 + f"\n** INICIANDO SERVIDOR DE DESARROLLO FLASK (NO PARA PRODUCCIÓN) **\n"
                 f"** Config: '{cfg_name}' {'(MODO DEBUG ACTIVO)' if debug else ''} | Recarga: {'Activada' if reloader else 'Desactivada'} **\n"
                 f"** Escuchando en: http://{host}:{port}/ **\n"
                 f"** Presiona CTRL+C para detener. **\n" + "*" * 80)
    try:
        app.run(host=host, port=port, debug=debug, use_reloader=reloader, threaded=True)
    except RuntimeError as e:
        app.logger.critical(f"Error al intentar iniciar servidor de desarrollo: {e}", exc_info=False)
        if "Address already in use" in str(e):
            app.logger.critical(f"--> Puerto {port} ya está en uso. Detén el otro proceso o cambia el puerto en la config.")
        exit(1)
    except KeyboardInterrupt:
        app.logger.info("\n---> Servidor de desarrollo detenido manualmente (CTRL+C).")
        exit(0)
    except Exception as e:
        app.logger.critical(f"Error fatal inesperado al ejecutar servidor de desarrollo: {e}", exc_info=True)
        exit(1)
