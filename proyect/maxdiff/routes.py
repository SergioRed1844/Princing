# proyect/maxdiff/routes.py (FINAL - con índice y mejoras previas)

from pathlib import Path
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, current_app
)
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

# Importaciones de utilidades
from proyect.common.utils import allowed_file, read_data_file, update_history_status
from proyect.maxdiff.utils import run_maxdiff

# Definición del Blueprint con prefijo /maxdiff
bp = Blueprint('maxdiff', __name__, url_prefix='/maxdiff')


# --- NUEVO: Ruta índice para el blueprint MaxDiff ---
@bp.route('/', endpoint='index')
def index():
    """
    Punto de entrada principal para el módulo MaxDiff.
    Redirige al formulario de subida de archivos de este módulo.
    Permite usar url_for('maxdiff.index') como enlace principal al módulo.
    """
    # Redirige a la ruta 'upload' dentro de este mismo blueprint ('maxdiff')
    return redirect(url_for('maxdiff.upload'))


# --- Endpoint explícito ---
@bp.route('/upload', methods=['GET', 'POST'], endpoint='upload')
def upload():
    """
    Endpoint para subir archivos específicos para MaxDiff.
    Guarda el archivo, actualiza historial y redirige a preview.
    Accesible en /maxdiff/upload
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
            session['analysis_type'] = 'maxdiff' # Marcar explícitamente

            # --- Usar update_history_status centralizado ---
            update_history_status(filename, 'Subido (MaxDiff)')

            flash(f"Archivo '{filename}' para MaxDiff subido exitosamente.", 'success')
            return redirect(url_for('maxdiff.preview')) # Usa endpoint 'preview'

        except RequestEntityTooLarge:
            flash(f"El archivo '{filename}' es demasiado grande.", 'danger')
            return redirect(request.url)
        except Exception as e:
            current_app.logger.error(f"Error guardando '{filename}' para MaxDiff: {e}", exc_info=True)
            flash('Ocurrió un error al guardar el archivo para MaxDiff.', 'danger')
            return redirect(request.url)

    # GET
    # Asegúrate que la plantilla 'upload.html' pueda manejar 'analysis_type'
    # y que su <form action="..."> apunte a url_for('maxdiff.upload')
    return render_template('upload.html', analysis_type='maxdiff')


# --- Endpoint explícito ---
@bp.route('/preview', endpoint='preview')
def preview():
    """
    Muestra una tabla con las primeras filas del archivo subido para MaxDiff.
    Accesible en /maxdiff/preview
    """
    filepath = session.get('uploaded_file_path')
    analysis_type = session.get('analysis_type')

    if not filepath:
        flash('No se encontró archivo en sesión. Por favor, sube uno primero desde MaxDiff.', 'warning')
        return redirect(url_for('maxdiff.upload'))
    if analysis_type != 'maxdiff':
         flash(f'El archivo en sesión es para {analysis_type}, no para MaxDiff. Sube uno nuevo para MaxDiff.', 'warning')
         return redirect(url_for('maxdiff.upload'))

    try:
        df = read_data_file(filepath)
        table_html = df.head().to_html(
            classes='table table-striped table-hover table-sm',
            border=0, index=False
        )
        # Asegúrate que 'preview.html' tenga un enlace/botón que apunte a
        # href="{{ url_for('maxdiff.process') }}"
        return render_template('preview.html', table_html=table_html, analysis_type='maxdiff')

    except FileNotFoundError:
         current_app.logger.error(f"Archivo '{filepath}' no encontrado para preview de MaxDiff.")
         flash('Error: El archivo subido no se encuentra en el servidor.', 'danger')
         session.pop('uploaded_file_path', None)
         session.pop('original_filename', None)
         session.pop('analysis_type', None)
         return redirect(url_for('maxdiff.upload'))
    except Exception as e:
        current_app.logger.error(f"Error al leer archivo para vista previa de MaxDiff: {e}", exc_info=True)
        flash('Error al generar vista previa para MaxDiff. Comprueba el formato del archivo.', 'danger')
        session.pop('uploaded_file_path', None)
        session.pop('original_filename', None)
        session.pop('analysis_type', None)
        return redirect(url_for('maxdiff.upload'))


# --- Endpoint explícito ---
# --- Método GET (invocado por enlace desde preview.html) ---
@bp.route('/process', endpoint='process', methods=['GET'])
def process():
    """
    Procesa los datos de MaxDiff y muestra resultados.
    Limpia la sesión relacionada con el archivo tras procesar con éxito.
    Accesible en /maxdiff/process
    """
    filepath = session.get('uploaded_file_path')
    filename = session.get('original_filename')
    analysis_type = session.get('analysis_type')

    if not filepath or not filename:
        flash('Falta información de subida en sesión. Por favor, sube el archivo de nuevo.', 'warning')
        return redirect(url_for('maxdiff.upload'))
    if analysis_type != 'maxdiff':
         flash(f'Se esperaba procesar MaxDiff pero el tipo en sesión es {analysis_type}.', 'danger')
         return redirect(url_for('maxdiff.upload'))

    try:
        current_app.logger.info(f"Iniciando procesamiento MaxDiff para archivo: {filename}")
        df = read_data_file(filepath)
        results = run_maxdiff(df)

        update_history_status(filename, 'Procesado (MaxDiff)')
        current_app.logger.info(f"Procesamiento MaxDiff para {filename} completado con éxito.")

        # --- Limpiar sesión después de procesar ---
        session.pop('uploaded_file_path', None)
        session.pop('original_filename', None)
        session.pop('analysis_type', None)

        return render_template(
            'results_maxdiff.html',
            filename=filename,
            avg_table=results['avg_df'].to_html(
                classes='table table-hover table-sm', border=0, index=False, float_format='%.2f'
            ),
            tmb_table=results['tmb_df'].to_html(
                classes='table table-hover table-sm', border=0, index=False
            ),
            bar_json=results['bar_json'],
            stacked_json=results['stacked_json']
        )

    # Manejo de Errores Específico
    except FileNotFoundError:
        current_app.logger.error(f"Archivo '{filepath}' no encontrado durante el procesamiento MaxDiff.")
        flash('Error crítico: El archivo a procesar no se encuentra. Pudo ser borrado.', 'danger')
        update_history_status(filename, 'Error - Archivo no encontrado (MaxDiff)')
        session.pop('uploaded_file_path', None)
        session.pop('original_filename', None)
        session.pop('analysis_type', None)
        return redirect(url_for('maxdiff.upload'))
    except KeyError as e:
        current_app.logger.error(f"Error procesando MaxDiff para '{filename}': Falta columna o clave esperada {e}", exc_info=True)
        flash(f'Error en los datos de entrada para MaxDiff: Falta la columna o clave {e}. Revisa el archivo de entrada.', 'danger')
        update_history_status(filename, 'Error - Datos inválidos (MaxDiff)')
        # Redirigir a preview puede ser útil para reintentar si fue un error de datos
        return redirect(url_for('maxdiff.preview'))
    except Exception as e:
        current_app.logger.error(f"Error inesperado procesando MaxDiff para '{filename}': {e}", exc_info=True)
        flash('Ocurrió un error inesperado durante el procesamiento de MaxDiff. Consulta los logs del servidor.', 'danger')
        update_history_status(filename, 'Error - Procesamiento (MaxDiff)')
        session.pop('uploaded_file_path', None)
        session.pop('original_filename', None)
        session.pop('analysis_type', None)
        return redirect(url_for('maxdiff.upload'))
