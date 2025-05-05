# proyect/comstrat/routes.py (FINAL - Pulido con comentarios finales)

from pathlib import Path
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, current_app
)
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
# Import pandas si vas a usarlo para manejar DataFrames, por ejemplo en los defaults
# import pandas as pd # Descomenta si es necesario

# Importaciones de utilidades
from proyect.common.utils import allowed_file, read_data_file, update_history_status
# Asume que existe la función run_comstrat en el utils de este módulo
from proyect.comstrat.utils import run_comstrat

# --- Definición única de Blueprint con prefijo y nombre consistente ---
bp = Blueprint('comstrat', __name__, url_prefix='/comstrat')


# --- Ruta índice para el blueprint ComStrat ---
@bp.route('/', endpoint='index')
def index():
    """
    Punto de entrada principal para ComStrat. Redirige a la subida de archivos.
    """
    return redirect(url_for('comstrat.upload'))


# --- Endpoint explícito para subir archivos ---
@bp.route('/upload', methods=['GET', 'POST'], endpoint='upload')
def upload():
    """
    Endpoint para subir archivos específicos para ComStrat.
    Accesible en /comstrat/upload
    """
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No se encontró el archivo en la solicitud.', 'danger')
            return redirect(request.url)
        file = request.files['file']

        if file.filename == '' or not allowed_file(file.filename):
            flash('Archivo inválido o extensión no permitida.', 'warning')
            return redirect(request.url)

        filename = secure_filename(file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        filepath = Path(upload_folder) / filename
        try:
            file.save(filepath)
            session['uploaded_file_path'] = str(filepath)
            session['original_filename'] = filename
            session['analysis_type'] = 'comstrat'

            update_history_status(filename, 'Subido (ComStrat)')

            flash(f"Archivo '{filename}' para ComStrat subido exitosamente.", 'success')
            return redirect(url_for('comstrat.preview'))

        except RequestEntityTooLarge:
            flash(f"El archivo '{filename}' es demasiado grande.", 'danger')
            return redirect(request.url)
        except Exception as e:
            current_app.logger.error(f"Error guardando '{filename}' para ComStrat: {e}", exc_info=True)
            flash('Ocurrió un error al guardar el archivo para ComStrat.', 'danger')
            return redirect(request.url)

    # GET: Renderiza upload.html. Asegúrate que action="{{ url_for('comstrat.upload') }}"
    return render_template('upload.html', analysis_type='comstrat')


# --- Endpoint explícito para vista previa ---
@bp.route('/preview', endpoint='preview')
def preview():
    """
    Muestra tabla preview del archivo subido para ComStrat.
    Accesible en /comstrat/preview
    """
    filepath = session.get('uploaded_file_path')
    analysis_type = session.get('analysis_type')

    if not filepath:
        flash('No se encontró archivo en sesión. Por favor, sube uno primero desde ComStrat.', 'warning')
        return redirect(url_for('comstrat.upload'))
    if analysis_type != 'comstrat':
         flash(f'El archivo en sesión es para {analysis_type}, no para ComStrat. Sube uno nuevo para ComStrat.', 'warning')
         return redirect(url_for('comstrat.upload'))

    try:
        df = read_data_file(filepath)
        table_html = df.head().to_html(
            classes='table table-striped table-hover table-sm',
            border=0, index=False
        )
        # Asegúrate que preview.html tenga enlace/botón a href="{{ url_for('comstrat.process') }}"
        return render_template('preview.html', table_html=table_html, analysis_type='comstrat')

    except FileNotFoundError:
         current_app.logger.error(f"Archivo '{filepath}' no encontrado para preview de ComStrat.")
         flash('Error: El archivo subido no se encuentra en el servidor.', 'danger')
         session.pop('uploaded_file_path', None)
         session.pop('original_filename', None)
         session.pop('analysis_type', None)
         return redirect(url_for('comstrat.upload'))
    except Exception as e:
        current_app.logger.error(f"Error al leer archivo para vista previa de ComStrat: {e}", exc_info=True)
        flash('Error al generar vista previa para ComStrat. Comprueba el formato del archivo.', 'danger')
        session.pop('uploaded_file_path', None)
        session.pop('original_filename', None)
        session.pop('analysis_type', None)
        return redirect(url_for('comstrat.upload'))


# --- Endpoint explícito para procesar ---
# --- NOTA sobre GET/POST ---
# Se mantiene como GET porque se invoca desde un enlace simple en preview.
# OPCIONAL: Si se prefiere mayor seguridad contra recargas accidentales o
# si la acción es compleja, cambiar a methods=['POST'] y usar un
# <form method="post" action="{{ url_for('comstrat.process') }}"> en preview.html.
@bp.route('/process', endpoint='process', methods=['GET'])
def process():
    """
    Procesa los datos para ComStrat y muestra resultados.
    Limpia la sesión relacionada con el archivo tras procesar con éxito.
    Accesible en /comstrat/process
    """
    filepath = session.get('uploaded_file_path')
    filename = session.get('original_filename')
    analysis_type = session.get('analysis_type')

    # Validaciones de sesión
    if not filepath or not filename:
        flash('Falta información de subida en sesión. Por favor, sube el archivo de nuevo.', 'warning')
        return redirect(url_for('comstrat.upload'))
    if analysis_type != 'comstrat':
         flash(f'Se esperaba procesar ComStrat pero el tipo en sesión es {analysis_type}.', 'danger')
         return redirect(url_for('comstrat.upload'))

    try:
        current_app.logger.info(f"Iniciando procesamiento ComStrat para archivo: {filename}")
        df = read_data_file(filepath)
        results = run_comstrat(df) # Llama a la lógica de análisis

        update_history_status(filename, 'Procesado (ComStrat)') # Actualiza historial
        current_app.logger.info(f"Procesamiento ComStrat para {filename} completado con éxito.")

        # Limpieza de sesión tras éxito
        session.pop('uploaded_file_path', None)
        session.pop('original_filename', None)
        session.pop('analysis_type', None)

        # --- Pasar claves explícitas a la plantilla ---
        # (Ajusta 'comstrat_table_df' y 'chart_json' según lo que devuelva run_comstrat)
        comstrat_table_df = results.get('comstrat_table_df')
        comstrat_table_html = (comstrat_table_df.to_html(classes='table table-hover table-sm', border=0, index=False)
                               if comstrat_table_df is not None and not comstrat_table_df.empty
                               else "<p>No hay datos de tabla ComStrat para mostrar.</p>")

        # Asegúrate que results_comstrat.html espera 'filename', 'comstrat_table', 'comstrat_chart_json'
        return render_template(
            'results_comstrat.html',
            filename=filename,
            comstrat_table=comstrat_table_html,
            comstrat_chart_json=results.get('chart_json', '{}')
        )

    # Manejo de Errores
    except FileNotFoundError:
        current_app.logger.error(f"Archivo '{filepath}' no encontrado durante el procesamiento ComStrat.")
        flash('Error crítico: El archivo a procesar no se encuentra.', 'danger')
        update_history_status(filename, 'Error - Archivo no encontrado (ComStrat)')
        session.pop('uploaded_file_path', None); session.pop('original_filename', None); session.pop('analysis_type', None)
        return redirect(url_for('comstrat.upload'))
    except KeyError as e:
        current_app.logger.error(f"Error procesando ComStrat para '{filename}': Falta columna o clave esperada {e}", exc_info=True)
        flash(f'Error en los datos de entrada para ComStrat: Falta la columna o clave {e}. Revisa el archivo.', 'danger')
        update_history_status(filename, 'Error - Datos inválidos (ComStrat)')
        return redirect(url_for('comstrat.preview'))
    except Exception as e:
        current_app.logger.error(f"Error inesperado procesando ComStrat para '{filename}': {e}", exc_info=True)
        flash('Ocurrió un error inesperado durante el procesamiento de ComStrat. Consulta los logs.', 'danger')
        update_history_status(filename, 'Error - Procesamiento (ComStrat)')
        session.pop('uploaded_file_path', None); session.pop('original_filename', None); session.pop('analysis_type', None)
        return redirect(url_for('comstrat.upload'))
