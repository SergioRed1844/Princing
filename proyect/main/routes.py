# proyect/main/routes.py

from flask import (
    render_template, request, redirect,
    url_for, flash, session, current_app
)
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from pathlib import Path

# Helpers comunes
from proyect.common.utils import allowed_file, read_data_file

# Importamos el Blueprint definido en __init__.py
from proyect.main import bp


@bp.route('/', methods=['GET'])
def index():
    """Redirige a la vista principal del dashboard."""
    return redirect(url_for('main.dashboard'))


@bp.route('/dashboard', methods=['GET'], endpoint='dashboard')
def dashboard():
    """Muestra el historial de cargas y acceso al dashboard."""
    upload_history = session.get('upload_history', [])
    return render_template('dashboard.html', history=upload_history)


@bp.route('/upload', methods=['GET', 'POST'], endpoint='upload_file')
def upload_file():
    """
    GET: muestra formulario de subida.
    POST: valida y guarda el archivo, redirige a preview.
    """
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            flash('No se seleccionó ningún archivo.', 'warning')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('Tipo de archivo no permitido.', 'warning')
            return redirect(request.url)

        filename = secure_filename(file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        filepath = Path(upload_folder) / filename

        try:
            file.save(filepath)

            session['uploaded_file_path'] = str(filepath)
            session['original_filename']    = filename
            session['analysis_type']        = request.form.get('analysis_type', 'maxdiff')

            history = session.get('upload_history', [])
            history.append({
                'filename': filename,
                'analysis_type': session['analysis_type'],
                'status': 'Subido'
            })
            session['upload_history'] = history

            flash(f"Archivo '{filename}' subido correctamente.", 'success')
            return redirect(url_for('main.preview_file'))

        except RequestEntityTooLarge:
            flash('El archivo excede el tamaño máximo permitido.', 'danger')
            return redirect(request.url)

        except Exception as e:
            current_app.logger.error(f"Error guardando '{filename}': {e}", exc_info=True)
            flash('Error al guardar el archivo. Intenta de nuevo.', 'danger')
            session.pop('uploaded_file_path', None)
            session.pop('original_filename', None)
            session.pop('analysis_type', None)
            return redirect(request.url)

    # GET
    return render_template('upload.html')


@bp.route('/preview', methods=['GET'], endpoint='preview_file')
def preview_file():
    """Muestra las primeras filas del DataFrame cargado."""
    filepath      = session.get('uploaded_file_path')
    filename      = session.get('original_filename')
    analysis_type = session.get('analysis_type')

    if not filepath or not filename or not analysis_type:
        flash('Primero debes subir un archivo.', 'warning')
        return redirect(url_for('main.upload_file'))

    try:
        df = read_data_file(filepath)
        table_html = df.head().to_html(
            classes="table table-sm table-striped table-hover table-preview",
            index=False, border=0, escape=True
        )
        return render_template(
            'preview.html',
            table_html=table_html,
            filename=filename,
            analysis_type=analysis_type
        )

    except FileNotFoundError:
        flash('El archivo no se encontró en el servidor.', 'danger')
        return redirect(url_for('main.upload_file'))

    except Exception as e:
        current_app.logger.error(f"Error en preview de '{filename}': {e}", exc_info=True)
        flash('Error procesando el archivo para vista previa.', 'danger')
        session.pop('uploaded_file_path', None)
        session.pop('original_filename', None)
        return redirect(url_for('main.upload_file'))


@bp.route('/export-options', methods=['GET'], endpoint='export_options')
def export_options():
    """Muestra opciones de exportación tras un análisis."""
    analysis_type = request.args.get('analysis_type')
    source_ref    = request.args.get('source_ref')
    if not analysis_type or not source_ref:
        flash("Faltan parámetros para exportar.", "warning")
        return redirect(url_for('main.dashboard'))

    return render_template(
        'export.html',
        analysis_type=analysis_type,
        source_ref=source_ref
    )


@bp.route('/export', methods=['GET'], endpoint='export_file')
def export_file():
    """Genera y envía el archivo resultante (placeholder)."""
    analysis_type = request.args.get('analysis_type')
    source_ref    = request.args.get('source_ref')
    fmt           = request.args.get('format', 'xlsx')

    if not analysis_type or not source_ref:
        flash("Faltan parámetros para exportar.", "warning")
        return redirect(url_for('main.dashboard'))

    current_app.logger.info(
        f"Export: tipo={analysis_type}, ref={source_ref}, fmt={fmt} (pendiente)"
    )
    flash(f'Exportación {analysis_type} como {fmt} aún no implementada.', 'info')
    return redirect(url_for('main.dashboard'))
