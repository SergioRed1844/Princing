# pricing_dashboard/proyect/comstrat/utils.py
# -*- coding: utf-8 -*-
"""
Módulo de Utilidades para Análisis ComStrat (Competitive Strategy)
dentro del Blueprint 'comstrat'.

Proporciona funciones para procesar datos combinados de importancia y desempeño,
calcular métricas para MOCA y PVM, y preparar datos (JSON, DataFrames)
listos para ser consumidos por las rutas y plantillas.

Importación en routes.py: from .utils import run_comstrat
"""

import logging
# Se quita Tuple ya que no se usa explícitamente aquí
from typing import Dict, List, Any, Optional
import pandas as pd  # Asegúrate de tener pandas en requirements.txt
import numpy as np   # Asegúrate de tener numpy en requirements.txt

logger = logging.getLogger(__name__)

# --- Constantes y Configuraciones ---
# ¡¡CRÍTICO!! Estos nombres DEBEN coincidir 100% con los encabezados
# de tu archivo Excel/CSV fuente para ComStrat.
# Si tu archivo usa 'Attribute Name', cambia COL_ATTRIBUTE = 'Attribute Name'.
COL_ATTRIBUTE = 'Attribute'
COL_IMPORTANCE = 'Importance_Score'
COL_PERFORMANCE_US = 'Performance_Us'
COL_PERFORMANCE_COMPETITOR = 'Performance_Competitor'
# COL_PRICE_METRIC = 'Price_Metric' # Si tienes una métrica de precio por atributo,
                                   # descomenta y ajusta este nombre.

# --- Funciones Principales de Análisis ---

def run_comstrat_analysis(df: pd.DataFrame, price_metric_col: Optional[str] = None) -> Dict[str, Any]:
    """
    Orquesta el pipeline completo de análisis ComStrat (MOCA y PVM).
    (Función interna detallada).

    Args:
        df (pd.DataFrame): DataFrame con los datos de entrada combinados.
        price_metric_col (Optional[str]): Nombre EXACTO de la columna que contiene
                                           la métrica de precio/costo por atributo.
                                           Es sensible a mayúsculas/minúsculas.
                                           Si es None o la columna no existe, el PVM
                                           no se generará.

    Returns:
        Dict[str, Any]: Diccionario con resultados detallados.
            (moca_df, pvm_df, moca_scatter_json, pvm_scatter_json, interpretation_hints)

    Raises:
        ValueError: Si faltan columnas requeridas o no son numéricas.
        Exception: Para otros errores de procesamiento.
    """
    # (Implementación sin cambios respecto a la versión anterior)
    logger.info(f"Iniciando análisis ComStrat detallado (run_comstrat_analysis) en DataFrame con {df.shape[0]} filas.")
    results = {
        'moca_df': pd.DataFrame(),
        'pvm_df': pd.DataFrame(),
        'moca_scatter_json': _prepare_empty_scatter("MOCA - Sin Datos"),
        'pvm_scatter_json': _prepare_empty_scatter("PVM - Sin Datos o Métrica de Precio"),
        'interpretation_hints': {"general": "Análisis no pudo completarse."}
    }
    try:
        required_moca_cols = [COL_ATTRIBUTE, COL_IMPORTANCE, COL_PERFORMANCE_US, COL_PERFORMANCE_COMPETITOR]
        _validate_input_df(df, required_moca_cols, "MOCA")
        logger.debug("Validación inicial para MOCA completada.")

        moca_df = _calculate_moca_data(df.copy(), required_moca_cols)
        results['moca_df'] = moca_df
        logger.info("Datos para MOCA calculados.")

        moca_scatter_json = _prepare_moca_scatter_json(moca_df)
        results['moca_scatter_json'] = moca_scatter_json
        logger.info("Datos para gráfico MOCA (scatter) generados.")

        pvm_scatter_json = _prepare_empty_scatter("PVM - Métrica de Precio no proporcionada")
        pvm_df = pd.DataFrame()
        if price_metric_col and price_metric_col in df.columns:
            logger.info(f"Intentando generar PVM usando la columna '{price_metric_col}'.")
            required_pvm_cols = [COL_ATTRIBUTE, COL_IMPORTANCE, price_metric_col]
            try:
                _validate_input_df(df, required_pvm_cols, "PVM")
                pvm_df = _calculate_pvm_data(df.copy(), required_pvm_cols, price_metric_col)
                results['pvm_df'] = pvm_df
                logger.info("Datos para PVM extraídos/calculados.")

                pvm_scatter_json = _prepare_pvm_scatter_json(pvm_df, price_metric_col)
                results['pvm_scatter_json'] = pvm_scatter_json
                logger.info("Datos para gráfico PVM (scatter) generados.")
            except ValueError as pvm_ve:
                logger.warning(f"No se pudo generar PVM: {pvm_ve}", exc_info=False)
                results['pvm_scatter_json'] = _prepare_empty_scatter(f"PVM - Error: {pvm_ve}")
            except Exception as pvm_e:
                 logger.error(f"Error inesperado durante el cálculo de PVM: {pvm_e}", exc_info=True)
                 results['pvm_scatter_json'] = _prepare_empty_scatter("PVM - Error Interno")
        elif price_metric_col:
             logger.warning(f"Columna de métrica de precio '{price_metric_col}' no encontrada en el DataFrame. PVM no se generará.")
             results['pvm_scatter_json'] = _prepare_empty_scatter(f"PVM - Columna '{price_metric_col}' no encontrada")
        else:
            logger.warning("No se proporcionó columna de métrica de precio. PVM no se generará.")
            results['pvm_scatter_json'] = _prepare_empty_scatter("PVM - Métrica de Precio no definida")

        pvm_was_attempted = bool(price_metric_col)
        results['interpretation_hints'] = _generate_comstrat_insights(moca_df, pvm_df, pvm_was_attempted)
        logger.info("Pistas de interpretación generadas.")

        logger.info("Análisis ComStrat detallado completado.")
        return results

    except ValueError as ve:
        logger.error(f"Error de validación en los datos de entrada para ComStrat: {ve}", exc_info=False)
        results['interpretation_hints']["general"] = f"Error de Validación: {ve}"
        return results
    except Exception as e:
        logger.error(f"Error inesperado durante el análisis ComStrat: {e}", exc_info=True)
        results['interpretation_hints']["general"] = f"Error inesperado: {e}"
        return results


# --- Funciones Auxiliares de Cálculo y Preparación ---

def _validate_input_df(df: pd.DataFrame, required_columns: List[str], analysis_type: str):
    """Valida que el DataFrame tenga las columnas necesarias y tipos correctos."""
    # (Implementación sin cambios respecto a la versión anterior)
    if df.empty:
        raise ValueError(f"El DataFrame de entrada para {analysis_type} está vacío.")
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Faltan columnas requeridas para {analysis_type}: {', '.join(missing_cols)}")

    numeric_cols = [col for col in required_columns if col != COL_ATTRIBUTE]
    for col in numeric_cols:
        if not pd.api.types.is_numeric_dtype(df[col]):
             try:
                 df[col] = pd.to_numeric(df[col])
                 logger.warning(f"Columna '{col}' fue convertida a tipo numérico para {analysis_type}.")
             except (ValueError, TypeError) as convert_error:
                 raise ValueError(f"La columna '{col}' requerida para {analysis_type} no es numérica y no pudo ser convertida. Error: {convert_error}") from convert_error

def _calculate_moca_data(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    """Calcula la ventaja competitiva y prepara el DataFrame para MOCA."""
    # (Implementación sin cambios respecto a la versión anterior)
    moca_df = df[cols].copy()
    moca_df['Competitive_Advantage'] = moca_df[COL_PERFORMANCE_US] - moca_df[COL_PERFORMANCE_COMPETITOR]
    moca_df = moca_df.dropna(subset=[COL_IMPORTANCE, 'Competitive_Advantage', COL_ATTRIBUTE]).reset_index(drop=True)
    return moca_df

def _calculate_pvm_data(df: pd.DataFrame, cols: List[str], price_col: str) -> pd.DataFrame:
    """Extrae los datos necesarios para el PVM."""
    # (Implementación sin cambios respecto a la versión anterior)
    pvm_df = df[cols].copy()
    pvm_df = pvm_df.rename(columns={COL_IMPORTANCE: 'Value_Score', price_col: 'Price_Score'})
    pvm_df = pvm_df.dropna(subset=['Value_Score', 'Price_Score', COL_ATTRIBUTE]).reset_index(drop=True)
    return pvm_df

# Añadido tipo de retorno Dict[str, Any]
def _prepare_moca_scatter_json(moca_df: pd.DataFrame) -> Dict[str, Any]:
    """Prepara datos JSON para un gráfico scatter Plotly (MOCA)."""
    # (Implementación sin cambios funcionales respecto a la versión anterior, solo tipo de retorno)
    if moca_df.empty:
        return _prepare_empty_scatter("MOCA - Sin datos válidos")

    avg_importance = moca_df[COL_IMPORTANCE].median()
    zero_advantage = 0
    min_y, max_y = moca_df[COL_IMPORTANCE].min(), moca_df[COL_IMPORTANCE].max()
    min_x, max_x = moca_df['Competitive_Advantage'].min(), moca_df['Competitive_Advantage'].max()

    y_range = max_y - min_y
    x_range = max_x - min_x
    y_margin = y_range * 0.05 if y_range > 0 else 1
    x_margin = x_range * 0.05 if x_range > 0 else 1

    data = [{
        'type': 'scatter', 'mode': 'markers+text',
        'x': moca_df['Competitive_Advantage'].round(2).tolist(),
        'y': moca_df[COL_IMPORTANCE].round(2).tolist(),
        'text': moca_df[COL_ATTRIBUTE].tolist(),
        'textposition': 'top right', 'marker': {'size': 10, 'color': '#1f77b4'},
        'name': 'Atributos'
    }]
    layout = {
        'title': 'Matriz de Ventajas Competitivas (MOCA)',
        'xaxis': {'title': 'Ventaja Competitiva (Nosotros vs Competencia)', 'range': [min_x - x_margin, max_x + x_margin]},
        'yaxis': {'title': f'{COL_IMPORTANCE} (Importancia)', 'range': [min_y - y_margin, max_y + y_margin]},
        'hovermode': 'closest',
        'shapes': [
            {'type': 'line', 'x0': zero_advantage, 'y0': min_y - y_margin, 'x1': zero_advantage, 'y1': max_y + y_margin, 'line': {'color': 'grey', 'width': 1, 'dash': 'dash'}},
            {'type': 'line', 'x0': min_x - x_margin, 'y0': avg_importance, 'x1': max_x + x_margin, 'y1': avg_importance, 'line': {'color': 'grey', 'width': 1, 'dash': 'dash'}}
        ],
        'annotations': [
             {'x': max_x, 'y': max_y, 'xref': 'x', 'yref': 'y', 'text': 'Fortalezas Clave', 'showarrow': False, 'xanchor': 'right', 'yanchor':'top', 'font': {'size': 10, 'color': 'grey'}},
             {'x': min_x, 'y': max_y, 'xref': 'x', 'yref': 'y', 'text': 'Debilidades Clave', 'showarrow': False, 'xanchor': 'left', 'yanchor':'top', 'font': {'size': 10, 'color': 'grey'}},
             {'x': max_x, 'y': min_y, 'xref': 'x', 'yref': 'y', 'text': 'Fortalezas Sec.', 'showarrow': False, 'xanchor': 'right', 'yanchor':'bottom', 'font': {'size': 10, 'color': 'grey'}},
             {'x': min_x, 'y': min_y, 'xref': 'x', 'yref': 'y', 'text': 'Baja Prioridad', 'showarrow': False, 'xanchor': 'left', 'yanchor':'bottom', 'font': {'size': 10, 'color': 'grey'}}
        ],
        'margin': {'l': 50, 'r': 20, 't': 50, 'b': 50}
    }
    return {'data': data, 'layout': layout}

# Añadido tipo de retorno Dict[str, Any]
def _prepare_pvm_scatter_json(pvm_df: pd.DataFrame, price_col_name: str) -> Dict[str, Any]:
    """Prepara datos JSON para un gráfico scatter Plotly (PVM)."""
    # (Implementación sin cambios funcionales respecto a la versión anterior, solo tipo de retorno)
    if pvm_df.empty:
        return _prepare_empty_scatter("PVM - Sin datos válidos")

    avg_value = pvm_df['Value_Score'].median()
    avg_price = pvm_df['Price_Score'].median()
    min_y, max_y = pvm_df['Value_Score'].min(), pvm_df['Value_Score'].max()
    min_x, max_x = pvm_df['Price_Score'].min(), pvm_df['Price_Score'].max()

    y_range = max_y - min_y
    x_range = max_x - min_x
    y_margin = y_range * 0.05 if y_range > 0 else 1
    x_margin = x_range * 0.05 if x_range > 0 else 1

    data = [{
        'type': 'scatter', 'mode': 'markers+text',
        'x': pvm_df['Price_Score'].round(2).tolist(),
        'y': pvm_df['Value_Score'].round(2).tolist(),
        'text': pvm_df[COL_ATTRIBUTE].tolist(),
        'textposition': 'top right', 'marker': {'size': 10, 'color': '#2ca02c'},
        'name': 'Atributos'
    }]
    layout = {
        'title': f'Mapa Precio-Valor (PVM - Atributos)',
        'xaxis': {'title': f'{price_col_name} (Métrica Precio/Costo)', 'range': [min_x - x_margin, max_x + x_margin]},
        'yaxis': {'title': f'{COL_IMPORTANCE} (Valor Percibido)', 'range': [min_y - y_margin, max_y + y_margin]},
        'hovermode': 'closest',
        'shapes': [
            {'type': 'line', 'x0': avg_price, 'y0': min_y - y_margin, 'x1': avg_price, 'y1': max_y + y_margin, 'line': {'color': 'grey', 'width': 1, 'dash': 'dash'}},
            {'type': 'line', 'x0': min_x - x_margin, 'y0': avg_value, 'x1': max_x + x_margin, 'y1': avg_value, 'line': {'color': 'grey', 'width': 1, 'dash': 'dash'}}
        ],
        'annotations': [
             {'x': max_x, 'y': max_y, 'xref': 'x', 'yref': 'y', 'text': 'Alto Valor, Alto Precio', 'showarrow': False, 'xanchor': 'right', 'yanchor':'top', 'font': {'size': 10, 'color': 'grey'}},
             {'x': min_x, 'y': max_y, 'xref': 'x', 'yref': 'y', 'text': 'Alto Valor, Bajo Precio (Oportunidad)', 'showarrow': False, 'xanchor': 'left', 'yanchor':'top', 'font': {'size': 10, 'color': 'grey'}},
             {'x': max_x, 'y': min_y, 'xref': 'x', 'yref': 'y', 'text': 'Bajo Valor, Alto Precio (¡Peligro!)', 'showarrow': False, 'xanchor': 'right', 'yanchor':'bottom', 'font': {'size': 10, 'color': 'grey'}},
             {'x': min_x, 'y': min_y, 'xref': 'x', 'yref': 'y', 'text': 'Bajo Valor, Bajo Precio', 'showarrow': False, 'xanchor': 'left', 'yanchor':'bottom', 'font': {'size': 10, 'color': 'grey'}}
        ],
        'margin': {'l': 50, 'r': 20, 't': 50, 'b': 50}
    }
    return {'data': data, 'layout': layout}

# Añadido tipo de retorno Dict[str, Any]
def _prepare_empty_scatter(title: str) -> Dict[str, Any]:
    """Genera la estructura JSON de un gráfico Plotly vacío con un título."""
    # (Implementación sin cambios funcionales respecto a la versión anterior, solo tipo de retorno)
    return {"data": [], "layout": {"title": title, "xaxis": {"visible": False}, "yaxis": {"visible": False}, "annotations": []}}

# Tipo de retorno ya era correcto (Dict[str, str])
def _generate_comstrat_insights(moca_df: pd.DataFrame, pvm_df: pd.DataFrame, pvm_was_attempted: bool) -> Dict[str, str]:
    """Genera insights textuales básicos basados en MOCA y PVM."""
    # (Implementación sin cambios respecto a la versión anterior)
    hints = {}
    if moca_df.empty:
        hints["general"] = "No hay datos MOCA válidos para generar insights."
        return hints

    avg_importance = moca_df[COL_IMPORTANCE].median()
    moca_df['Quadrant'] = np.select(
        [
            (moca_df[COL_IMPORTANCE] >= avg_importance) & (moca_df['Competitive_Advantage'] >= 0),
            (moca_df[COL_IMPORTANCE] >= avg_importance) & (moca_df['Competitive_Advantage'] < 0),
            (moca_df[COL_IMPORTANCE] < avg_importance) & (moca_df['Competitive_Advantage'] >= 0),
            (moca_df[COL_IMPORTANCE] < avg_importance) & (moca_df['Competitive_Advantage'] < 0)
        ],
        ['Fortaleza Clave', 'Debilidad Clave', 'Fortaleza Secundaria', 'Baja Prioridad'],
        default='Indeterminado'
    )

    strengths = moca_df[moca_df['Quadrant'] == 'Fortaleza Clave'][COL_ATTRIBUTE].tolist()
    weaknesses = moca_df[moca_df['Quadrant'] == 'Debilidad Clave'][COL_ATTRIBUTE].tolist()
    secondary_strengths = moca_df[moca_df['Quadrant'] == 'Fortaleza Secundaria'][COL_ATTRIBUTE].tolist()
    low_priority = moca_df[moca_df['Quadrant'] == 'Baja Prioridad'][COL_ATTRIBUTE].tolist()

    hints['moca_strengths'] = f"**Fortalezas Clave (Alto Imp, Ventaja ≥ 0):** {', '.join(strengths) if strengths else 'Ninguna.'} -> CAPITALIZAR."
    hints['moca_weaknesses'] = f"**Debilidades Clave (Alto Imp, Ventaja < 0):** {', '.join(weaknesses) if weaknesses else 'Ninguna.'} -> MEJORA PRIORITARIA."
    hints['moca_secondary'] = f"**Fortalezas Secundarias (Bajo Imp, Ventaja ≥ 0):** {', '.join(secondary_strengths) if secondary_strengths else 'Ninguna.'} -> MANTENER EFICIENCIA."
    hints['moca_low_priority'] = f"**Baja Prioridad (Bajo Imp, Ventaja < 0):** {', '.join(low_priority) if low_priority else 'Ninguna.'} -> EVITAR SOBREINVERSIÓN."

    if not pvm_df.empty:
        hints['pvm_summary'] = ("**PVM:** El mapa Precio-Valor muestra la relación entre el valor percibido (importancia) y la métrica de precio/costo asociada a cada atributo. "
                              "Identifica atributos en la zona de 'Oportunidad' (Alto Valor, Bajo Precio/Costo) y gestiona los que caen en 'Peligro' (Bajo Valor, Alto Precio/Costo).")
    elif pvm_was_attempted:
         hints['pvm_summary'] = "**PVM:** No se pudieron generar insights PVM (datos vacíos después del filtro o error durante el proceso)."
    else:
        hints['pvm_summary'] = "**PVM:** No generado (métrica de precio no especificada)."

    hints['general_strategy'] = "**Estrategia General:** Enfocar recursos en mejorar **Debilidades Clave**. Defender y comunicar **Fortalezas Clave**. Evaluar la rentabilidad de mantener **Fortalezas Secundarias** y minimizar esfuerzo en **Baja Prioridad**."

    return hints


# --- Capa de Compatibilidad (Wrapper) ---

# Tipo de retorno ya era correcto (Dict[str, Any])
def run_comstrat(df: pd.DataFrame, price_metric_col: Optional[str] = None) -> Dict[str, Any]:
    """
    Wrapper público para ser llamado desde las rutas del blueprint 'comstrat'.
    Ejecuta el análisis ComStrat y devuelve un diccionario simplificado
    listo para pasar a la plantilla `results_comstrat.html`.

    Args:
        df (pd.DataFrame): DataFrame con los datos combinados.
        price_metric_col (Optional[str]): Nombre de la columna de métrica de precio.

    Returns:
        Dict[str, Any]: Diccionario con llaves: 'moca_json', 'pvm_json',
                        'moca_df', 'insights'.
    """
    logger.info(f"Ejecutando wrapper 'run_comstrat' para blueprint (Price Metric Col: {price_metric_col})...")
    full_analysis_results = run_comstrat_analysis(df, price_metric_col)

    compatible_results = {
        'moca_json': full_analysis_results['moca_scatter_json'],
        'pvm_json': full_analysis_results['pvm_scatter_json'],
        'moca_df': full_analysis_results['moca_df'], # DataFrame para tabla HTML
        'insights': full_analysis_results['interpretation_hints']
    }
    logger.info("Resultados ComStrat listos para pasar a la plantilla.")
    return compatible_results

# --- Bloque de Ejemplo para Pruebas Directas ---
# Comentado por defecto, ya que no es necesario cuando se importa como módulo.
# Descomenta si necesitas probar este archivo de forma aislada.
'''
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    print("*"*20 + " Ejecutando Ejemplo Directo de comstrat/utils.py " + "*"*20)
    # (Código de ejemplo sin cambios respecto a la versión anterior)
    data = {
        COL_ATTRIBUTE: ['Calidad', 'Precio', 'Soporte', 'Velocidad', 'Innovación', 'Facilidad de Uso'],
        COL_IMPORTANCE: [85, 95, 60, 75, 50, 70],
        COL_PERFORMANCE_US: [7, 5, 8, 9, 6, 7],
        COL_PERFORMANCE_COMPETITOR: [6, 6, 7, 7, 7, 6],
        'Price_Sensitivity': [30, 80, 20, 40, 50, 35]
    }
    example_df = pd.DataFrame(data)
    example_price_col = 'Price_Sensitivity'
    # example_price_col = None

    print("\nDataFrame de Ejemplo ComStrat:")
    print(example_df)
    try:
        print(f"\n--- Probando Wrapper 'run_comstrat' (con Price Metric: {example_price_col}) ---")
        compatible_output = run_comstrat(example_df, price_metric_col=example_price_col)
        print("\nResultados (Formato Compatible devuelto por el Wrapper):")
        print(f"  Claves disponibles: {list(compatible_output.keys())}")
        print("\n1. 'moca_json' (Dict):")
        print(f"  - Título: {compatible_output['moca_json'].get('layout',{}).get('title')}")
        print("\n2. 'pvm_json' (Dict):")
        print(f"  - Título: {compatible_output['pvm_json'].get('layout',{}).get('title')}")
        print("\n3. 'moca_df' (DataFrame):")
        if not compatible_output['moca_df'].empty: print(compatible_output['moca_df'].round(2).to_string())
        else: print("  (DataFrame vacío)")
        print("\n4. 'insights' (Dict):")
        if compatible_output['insights']:
            for key, hint in compatible_output['insights'].items(): print(f"  - {key}: {hint}")
        else: print("  (No se generaron insights)")
    except Exception as e:
         print(f"\n--- ERROR durante el análisis de ejemplo ComStrat ---")
         print(f"Error: {e}")
    print("*"*20 + " Fin Ejemplo Directo " + "*"*20)
'''
