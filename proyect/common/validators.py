# proyect/common/validators.py

import pandas as pd
import logging

logger = logging.getLogger(__name__)

def validate_dataframe_schema(df: pd.DataFrame, required_columns: list, context: str = "") -> bool:
    """
    Valida que un DataFrame contenga las columnas requeridas.

    Args:
        df (pd.DataFrame): DataFrame a validar.
        required_columns (list): Lista de columnas requeridas.
        context (str): Contexto de uso (opcional, solo para logs).

    Raises:
        ValueError: Si faltan columnas requeridas.

    Returns:
        True si es válido.
    """
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        msg = f"[{context}] Faltan columnas requeridas: {missing_cols}"
        logger.error(msg)
        raise ValueError(msg)

    logger.debug(f"[{context}] DataFrame validado correctamente con columnas requeridas presentes.")
    return True
