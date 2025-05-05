# pricing_dashboard/proyect/common/utils.py
# -*- coding: utf-8 -*-
"""
Helpers compartidos para el dashboard de pricing.
Contiene funciones reutilizables en todos los módulos (MaxDiff, ComStrat, Main).
"""

import logging
from pathlib import Path
from typing import Union
import pandas as pd
from flask import session

logger = logging.getLogger(__name__)

# --- Funciones Requeridas por main/routes.py ---

# Extensiones permitidas
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

def allowed_file(filename: str) -> bool:
    """
    Comprueba que el nombre de archivo tiene una extensión permitida.
    """
    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )

def read_data_file(filepath: Union[str, Path]) -> pd.DataFrame:
    """
    Lee un archivo Excel (.xlsx, .xls) o CSV y devuelve un pandas.DataFrame limpio.
    """
    path = Path(filepath)
    if not path.exists():
        logger.error(f"Archivo no encontrado al intentar leer: {filepath}")
        raise FileNotFoundError(f"El archivo {filepath} no existe o no se puede acceder.")

    suffix = path.suffix.lower()
    df = None

    try:
        if suffix in ('.xlsx', '.xls'):
            df = pd.read_excel(path, engine='openpyxl' if suffix == '.xlsx' else None)
        elif suffix == '.csv':
            try:
                df = pd.read_csv(path, sep=None, engine='python', encoding='utf-8-sig')
                logger.info(f"Archivo CSV '{path.name}' leído con UTF-8.")
            except UnicodeDecodeError:
                logger.warning(f"Fallo UTF-8 en CSV '{path.name}', intentando latin-1.")
                df = pd.read_csv(path, sep=None, engine='python', encoding='latin-1')
            except pd.errors.ParserError as pe:
                logger.error(f"Error de parsing leyendo CSV '{path.name}': {pe}")
                raise ValueError(f"Error al interpretar el archivo CSV: {pe}") from pe
        else:
            logger.error(f"Intento de leer archivo con extensión no soportada: {suffix} en {filepath}")
            raise ValueError(f"Extensión no soportada: {suffix}. Permitidas: {', '.join(ALLOWED_EXTENSIONS)}")

        if df is None:
            raise ValueError("No se pudo generar un DataFrame a partir del archivo.")

        original_shape = df.shape
        df.dropna(axis=0, how='all', inplace=True)
        df.dropna(axis=1, how='all', inplace=True)
        if original_shape != df.shape:
            logger.info(f"Filas/columnas vacías eliminadas de '{path.name}'. Antes: {original_shape}, Ahora: {df.shape}")

        if df.empty:
            logger.warning(f"El archivo '{path.name}' resultó vacío después de la lectura y limpieza.")
            raise ValueError("El archivo está vacío o no contiene datos legibles después de la limpieza inicial.")

        logger.info(f"Archivo '{path.name}' leído y limpiado exitosamente. Dimensiones finales: {df.shape}.")
        return df

    except FileNotFoundError:
        raise
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error inesperado leyendo el archivo '{path.name}': {e}", exc_info=True)
        raise ValueError(f"Ocurrió un error inesperado al procesar el archivo: {e}") from e

# --- Validación de DataFrame ---

def validate_dataframe(df: pd.DataFrame) -> bool:
    """
    Valida que el DataFrame contenga las columnas requeridas y no tenga valores nulos.

    Args:
        df (pandas.DataFrame): DataFrame a validar.

    Returns:
        bool: True si es válido, False si falta alguna columna o hay valores nulos.
    """
    required_columns = ['columna1', 'columna2']  # Ajusta las columnas requeridas según tu caso

    columns_exist = all(col in df.columns for col in required_columns)
    no_nulls = not df.isnull().values.any()

    if not columns_exist:
        logger.warning(f"Validación fallida: faltan columnas requeridas. Requeridas: {required_columns}. Encontradas: {list(df.columns)}")
    if not no_nulls:
        logger.warning(f"Validación fallida: el DataFrame contiene valores nulos.")

    valid = columns_exist and no_nulls
    logger.info(f"Resultado de validate_dataframe: {valid}")
    return valid

# --- Otras Funciones Auxiliares ---

def update_history_status(filename: str, status: str) -> None:
    """
    Actualiza el estado de un archivo en el historial de uploads guardado en session.
    """
    try:
        history = session.get('upload_history', [])
        found = False
        for entry in reversed(history):
            if entry.get('filename') == filename:
                entry['status'] = status
                found = True
                break
        if found:
            session.modified = True
            logger.debug(f"Historial actualizado para '{filename}' con estado '{status}'.")
        else:
            logger.warning(f"No se encontró la entrada para '{filename}' en el historial para actualizar estado a '{status}'.")
    except Exception as e:
        logger.error(f"Error al actualizar el historial para '{filename}': {e}", exc_info=True)
