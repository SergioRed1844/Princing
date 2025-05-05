# proyect/moca/routes.py (CORREGIDO y MEJORADO)

from pathlib import Path
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, current_app
)
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

# Importaciones de utilidades
from proyect.common.utils import allowed_file, read_data_file, update_history_status
from proyect.moca.utils import run_moca # Asume que esta función existe y hace el análisis MOCA

# --- CORRECCIÓN: Definición única de Blueprint con prefijo y nombre consistente ---
bp = Blueprint('moca', __name__, url_prefix='/moca')


# --- NUEVO: Ruta índice para el blueprint MOCA ---
@bp.route('/', endpoint='index')
def index():
    """
    Punto de entrada principal para el módulo MOCA.
    Redirige al formulario de subida de archivos de este módulo.
    """
    return redirect(url_for('moca.upload'))


# --- CORRECCIÓN: Decorador y Endpoint actualizados ---
@bp.route('/upload', methods=['GET', 'POST'], endpoint='upload')
def upload():
    """
    Endpoint para subir archivos específicos para MOCA.
    Guarda el archivo, actualiza historial y redirige a preview.
    Accesible en /moca/upload
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
            session['analysis_type'] = 'moca' # Marcar explícitamente

            # --- MEJORA: Usar update_history_status ---
            update_history_status(filename, 'Subido (MOCA)')

            flash(f"Archivo '{filename}' para MOCA subido exitosamente.", 'success')
            return redirect(url_for('moca.preview')) # Usa endpoint 'preview'

        except RequestEntityTooLarge:
            flash(f"El archivo '{filename}' es demasiado grande.", 'danger')
            return redirect(request.url)
        except Exception as e:
            current_app.logger.error(f"Error guardando '{filename}' para MOCA: {e}", exc_info=True)
            flash('Ocurrió un error al guardar el archivo para MOCA.', 'danger')
            return redirect(request.url)

    # GET
    return render_template('upload.html', analysis_type='moca')


# --- CORRECCIÓN: Decorador y Endpoint actualizados ---
@bp.route('/preview', endpoint='preview')
def preview():
    """
    Muestra una tabla con las primeras filas del archivo subido para MOCA.
    Accesible en /moca/preview
    """
    filepath = session.get('uploaded_file_path')
    analysis_type = session.get('analysis_type')

    if not filepath:
        flash('No se encontró archivo en sesión. Por favor, sube uno primero desde MOCA.', 'warning')
        return redirect(url_for('moca.upload'))
    if analysis_type != 'moca':
         flash(f'El archivo en sesión es para {analysis_type}, no para MOCA. Sube uno nuevo para MOCA.', 'warning')
         return redirect(url_for('moca.upload'))

    try:
        df = read_data_file(filepath)
        table_html = df.head().to_html(
            classes='table table-striped table-hover table-sm',
            border=0, index=False
        )
        # Asegúrate que 'preview.html' tenga enlace/botón a url_for('moca.process')
        return render_template('preview.html', table_html=table_html, analysis_type='moca')

    except FileNotFoundError:
         current_app.logger.error(f"Archivo '{filepath}' no encontrado para preview de MOCA.")
         flash('Error: El archivo subido no se encuentra en el servidor.', 'danger')
         session.pop('uploaded_file_path', None)
         session.pop('original_filename', None)
         session.pop('analysis_type', None)
         return redirect(url_for('moca.upload'))
    except Exception as e:
        current_app.logger.error(f"Error al leer archivo para vista previa de MOCA: {e}", exc_info=True)
        flash('Error al generar vista previa para MOCA. Comprueba el formato del archivo.', 'danger')
        session.pop('uploaded_file_path', None)
        session.pop('original_filename', None)
        session.pop('analysis_type', None)
        return redirect(url_for('moca.upload'))


# --- CORRECCIÓN: Decorador y Endpoint actualizados ---
# --- NOTA: Método GET ---
@bp.route('/process', endpoint='process', methods=['GET'])
def process():
    """
    Procesa los datos para MOCA y muestra resultados.
    Limpia la sesión relacionada con el archivo tras procesar con éxito.
    Accesible en /moca/process
    """
    filepath = session.get('uploaded_file_path')
    filename = session.get('original_filename')
    analysis_type = session.get('analysis_type')

    if not filepath or not filename:
        flash('Falta información de subida en sesión. Por favor, sube el archivo de nuevo.', 'warning')
        return redirect(url_for('moca.upload'))
    if analysis_type != 'moca':
         flash(f'Se esperaba procesar MOCA pero el tipo en sesión es {analysis_type}.', 'danger')
         return redirect(url_for('moca.upload'))

    try:
        current_app.logger.info(f"Iniciando procesamiento MOCA para archivo: {filename}")
        df = read_data_file(filepath)
        results = run_moca(df) # Ejecuta la lógica de análisis MOCA

        # Actualiza estado en historial
        update_history_status(filename, 'Procesado (MOCA)')
        current_app.logger.info(f"Procesamiento MOCA para {filename} completado con éxito.")

        # --- MEJORA: Limpiar sesión después de procesar ---
        session.pop('uploaded_file_path', None)
        session.pop('original_filename', None)
        session.pop('analysis_type', None)

        # Renderiza la plantilla de resultados específica para MOCA
        # Asegúrate que 'results_moca.html' existe y espera estas variables
        return render_template(
            'results_moca.html',
            filename=filename,
            # Asumiendo que run_moca devuelve estas claves con estos tipos
            moca_matrix=results['moca_matrix'].to_html(
                classes='table table-hover table-sm', border=0, index=False
            ),
            pvm_json=results['pvm_json'] # JSON para el gráfico Plotly Precio-Valor
        )

    # Manejo de Errores Específico
    except FileNotFoundError:
        current_app.logger.error(f"Archivo '{filepath}' no encontrado durante el procesamiento MOCA.")
        flash('Error crítico: El archivo a procesar no se encuentra.', 'danger')
        update_history_status(filename, 'Error - Archivo no encontrado (MOCA)')
        session.pop('uploaded_file_path', None)
        session.pop('original_filename', None)
        session.pop('analysis_type', None)
        return redirect(url_for('moca.upload'))
    except KeyError as e:
        current_app.logger.error(f"Error procesando MOCA para '{filename}': Falta columna o clave esperada {e}", exc_info=True)
        flash(f'Error en los datos de entrada para MOCA: Falta la columna o clave {e}. Revisa el archivo.', 'danger')
        update_history_status(filename, 'Error - Datos inválidos (MOCA)')
        return redirect(url_for('moca.preview'))
    except Exception as e:
        current_app.logger.error(f"Error inesperado procesando MOCA para '{filename}': {e}", exc_info=True)
        flash('Ocurrió un error inesperado durante el procesamiento de MOCA. Consulta los logs.', 'danger')
        update_history_status(filename, 'Error - Procesamiento (MOCA)')
        session.pop('uploaded_file_path', None)
        session.pop('original_filename', None)
        session.pop('analysis_type', None)
        return redirect(url_for('moca.upload'))
