# proyect/maxdiff/utils.py
# -*- coding: utf-8 -*-
"""
Módulo de Utilidades para Análisis MaxDiff (Maximum Difference Scaling).

Proporciona funciones para procesar datos crudos de MaxDiff, calcular
utilidades agregadas (basado en conteos), derivar métricas clave
(promedios, Top/Middle/Bottom Box), y preparar datos para visualización
con Plotly, enfocado en insights estratégicos para pricing.

**Incluye wrapper de compatibilidad 'run_maxdiff' para rutas existentes.**
"""

import logging
from typing import Dict, Tuple, List, Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# --- Constantes y Configuraciones ---
COL_RESPONDENT_ID = 'RespondentID'
COL_SET_ID = 'SetID'
COL_BEST_ATTR = 'Attribute_Best'
COL_WORST_ATTR = 'Attribute_Worst'

# --- Funciones Principales de Análisis ---

def run_maxdiff_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Orquesta el pipeline completo de análisis MaxDiff agregado basado en conteos.
    (Función interna detallada).

    Args:
        df (pd.DataFrame): DataFrame con los datos crudos de MaxDiff.

    Returns:
        Dict[str, Any]: Un diccionario conteniendo los resultados clave detallados.
            (utilities_df, tmb_df, raw_counts_df, bar_chart_json, etc.)

    Raises:
        ValueError: Si las columnas requeridas no se encuentran en el DataFrame.
        Exception: Para cualquier otro error durante el procesamiento.
    """
    logger.info(f"Iniciando análisis MaxDiff detallado (run_maxdiff_analysis) en DataFrame con {df.shape[0]} filas.")
    try:
        # 1. Validación de Entrada
        _validate_input_df(df)
        logger.debug("Validación de DataFrame de entrada completada.")

        # 2. Identificar Atributos Únicos
        attributes = _get_unique_attributes(df)
        logger.debug(f"Atributos únicos identificados: {len(attributes)}")

        # 3. Calcular Utilidades Agregadas (Método de Conteos)
        utilities_df, raw_counts_df = _calculate_aggregated_counts_utilities(df, attributes)
        logger.info("Utilidades agregadas calculadas y escaladas.")

        # 4. Calcular Scores Top/Middle/Bottom (TMB) - Basado en Utilidades Agregadas
        tmb_df = _calculate_tmb_scores_from_aggregated(utilities_df)
        logger.info("Scores Top/Middle/Bottom calculados.")

        # 5. Preparar Datos para Gráficos Plotly
        bar_chart_json = _prepare_bar_chart_json(utilities_df)
        stacked_bar_json = _prepare_stacked_bar_json(tmb_df)
        logger.info("Datos para gráficos Plotly generados.")

        # 6. Generar Pistas de Interpretación (Nivel Consultor)
        interpretation_hints = _generate_interpretation_hints(utilities_df, tmb_df)
        logger.info("Pistas de interpretación generadas.")

        # Este es el diccionario detallado que devuelve la función interna
        detailed_results = {
            'attributes': attributes,
            'utilities_df': utilities_df, # <--- Clave interna detallada
            'tmb_df': tmb_df,
            'raw_counts_df': raw_counts_df,
            'bar_chart_json': bar_chart_json, # <--- Clave interna detallada
            'stacked_bar_json': stacked_bar_json, # <--- Clave interna detallada
            'interpretation_hints': interpretation_hints
        }
        logger.info("Análisis MaxDiff detallado completado exitosamente.")
        return detailed_results

    except ValueError as ve:
        logger.error(f"Error de validación en los datos de entrada: {ve}", exc_info=False)
        raise
    except Exception as e:
        logger.error(f"Error inesperado durante el análisis MaxDiff detallado: {e}", exc_info=True)
        raise

# --- Funciones Auxiliares de Cálculo y Preparación (Sin cambios) ---

def _validate_input_df(df: pd.DataFrame):
    """Valida que el DataFrame de entrada tenga las columnas necesarias."""
    required_columns = [COL_RESPONDENT_ID, COL_SET_ID, COL_BEST_ATTR, COL_WORST_ATTR]
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Faltan columnas requeridas en el DataFrame de entrada: {', '.join(missing_cols)}")

def _get_unique_attributes(df: pd.DataFrame) -> List[str]:
    """Obtiene la lista de atributos únicos de las columnas Best y Worst."""
    best_attributes = df[COL_BEST_ATTR].unique()
    worst_attributes = df[COL_WORST_ATTR].unique()
    all_attributes = pd.unique(np.concatenate((best_attributes, worst_attributes))).tolist()
    all_attributes = [attr for attr in all_attributes if pd.notna(attr) and isinstance(attr, str) and attr.strip() != '']
    all_attributes.sort()
    if not all_attributes:
         raise ValueError("No se encontraron atributos válidos en las columnas 'Best'/'Worst'.")
    return all_attributes

def _calculate_aggregated_counts_utilities(df: pd.DataFrame, attributes: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula utilidades agregadas usando el método de conteos Best-Worst."""
    best_counts = df[COL_BEST_ATTR].value_counts().reindex(attributes, fill_value=0)
    worst_counts = df[COL_WORST_ATTR].value_counts().reindex(attributes, fill_value=0)

    raw_counts_df = pd.DataFrame({
        'Attribute': attributes,
        'Best_Count': best_counts,
        'Worst_Count': worst_counts
    }).reset_index(drop=True)

    raw_counts_df['BW_Score'] = raw_counts_df['Best_Count'] - raw_counts_df['Worst_Count']

    min_score = raw_counts_df['BW_Score'].min()
    shifted_scores = raw_counts_df['BW_Score'] - min_score
    total_shifted_score = shifted_scores.sum()

    if total_shifted_score == 0:
         logger.warning("Todos los BW scores son iguales o nulos. Asignando utilidad uniforme.")
         raw_counts_df['Avg_Utility_Score'] = 100.0 / len(attributes) if attributes else 0
    else:
        raw_counts_df['Avg_Utility_Score'] = (shifted_scores / total_shifted_score) * 100

    # El DataFrame devuelto aquí usa 'Avg_Utility_Score'
    utilities_df = raw_counts_df[['Attribute', 'Avg_Utility_Score']].sort_values(
        by='Avg_Utility_Score', ascending=False
    ).reset_index(drop=True)

    return utilities_df, raw_counts_df[['Attribute', 'Best_Count', 'Worst_Count']]

def _calculate_tmb_scores_from_aggregated(utilities_df: pd.DataFrame) -> pd.DataFrame:
    """Calcula scores TMB simplificados basados en utilidades agregadas."""
    n_attributes = len(utilities_df)
    if n_attributes == 0:
        return pd.DataFrame(columns=['Attribute', 'Top_Box_%', 'Middle_Box_%', 'Bottom_Box_%'])

    top_tercile_idx = int(np.ceil(n_attributes / 3))
    bottom_tercile_idx = n_attributes - int(np.ceil(n_attributes / 3))

    tmb_data = []
    utilities_df_sorted = utilities_df.sort_values(by='Avg_Utility_Score', ascending=False).reset_index()

    for index, row in utilities_df_sorted.iterrows():
        attribute = row['Attribute']
        top = 100.0 if index < top_tercile_idx else 0.0
        bottom = 100.0 if index >= bottom_tercile_idx else 0.0
        middle = 100.0 if top == 0.0 and bottom == 0.0 else 0.0
        if n_attributes <= 2: middle = 0.0

        tmb_data.append({
            'Attribute': attribute,
            'Top_Box_%': top,
            'Middle_Box_%': middle,
            'Bottom_Box_%': bottom
        })

    tmb_df = pd.DataFrame(tmb_data)
    tmb_df = tmb_df.set_index('Attribute').reindex(utilities_df['Attribute']).reset_index()
    return tmb_df

def _prepare_bar_chart_json(utilities_df: pd.DataFrame) -> Dict[str, Any]:
    """Prepara datos para un gráfico de barras Plotly (Utilidades Promedio)."""
    if utilities_df.empty:
        return {"data": [], "layout": {"title": "Utilidad Promedio de Atributos (MaxDiff) - Sin Datos"}}

    df_sorted = utilities_df.sort_values(by='Avg_Utility_Score', ascending=False)
    data = [{'type': 'bar', 'x': df_sorted['Attribute'].tolist(),
             'y': df_sorted['Avg_Utility_Score'].round(1).tolist(),
             'text': df_sorted['Avg_Utility_Score'].round(1).tolist(),
             'textposition': 'auto', 'marker': {'color': '#1f77b4'},
             'name': 'Utilidad Promedio'}]
    layout = {'title': 'Importancia Relativa de Atributos (MaxDiff - Scores Promedio)',
              'xaxis': {'title': 'Atributo', 'tickangle': -45},
              'yaxis': {'title': 'Utilidad Promedio (Escala 100)', 'range': [0, max(100, df_sorted['Avg_Utility_Score'].max() * 1.1)]},
              'margin': {'b': 150}, 'hovermode': 'closest', 'bargap': 0.15}
    return {'data': data, 'layout': layout}

def _prepare_stacked_bar_json(tmb_df: pd.DataFrame) -> Dict[str, Any]:
    """Prepara datos para un gráfico de barras apiladas Plotly (TMB Scores)."""
    if tmb_df.empty:
       return {"data": [], "layout": {"title": "Distribución Top/Middle/Bottom Box (MaxDiff) - Sin Datos"}}

    attributes = tmb_df['Attribute'].tolist()
    trace_top = {'type': 'bar', 'x': attributes, 'y': tmb_df['Top_Box_%'].tolist(), 'name': 'Top Box (%)', 'marker': {'color': '#2ca02c'}}
    trace_middle = {'type': 'bar', 'x': attributes, 'y': tmb_df['Middle_Box_%'].tolist(), 'name': 'Middle Box (%)', 'marker': {'color': '#ff7f0e'}}
    trace_bottom = {'type': 'bar', 'x': attributes, 'y': tmb_df['Bottom_Box_%'].tolist(), 'name': 'Bottom Box (%)', 'marker': {'color': '#d62728'}}
    data = [trace_top, trace_middle, trace_bottom]
    layout = {'title': 'Distribución de Importancia por Atributo (TMB)',
              'xaxis': {'title': 'Atributo', 'tickangle': -45},
              'yaxis': {'title': 'Porcentaje de Clasificación (%)', 'range': [0, 105]},
              'barmode': 'stack', 'margin': {'b': 150}, 'hovermode': 'closest',
              'legend': {'traceorder': 'normal'}}
    return {'data': data, 'layout': layout}

def _generate_interpretation_hints(utilities_df: pd.DataFrame, tmb_df: pd.DataFrame) -> Dict[str, str]:
    """Genera insights textuales básicos basados en los resultados agregados."""
    # (Implementación sin cambios respecto a la versión anterior)
    hints = {}
    if utilities_df.empty:
        return {"general": "No hay datos suficientes para generar insights."}
    utilities_df_sorted=utilities_df.sort_values(by='Avg_Utility_Score',ascending=False).reset_index(drop=True)
    tmb_df_sorted=tmb_df.set_index('Attribute').reindex(utilities_df_sorted['Attribute']).reset_index()
    top_attribute=utilities_df_sorted.iloc[0]['Attribute']
    top_score=utilities_df_sorted.iloc[0]['Avg_Utility_Score']
    hints['top_driver']=(f"El atributo clave es **'{top_attribute}'** (Score: {top_score:.1f}).")
    bottom_attribute=utilities_df_sorted.iloc[-1]['Attribute']
    bottom_score=utilities_df_sorted.iloc[-1]['Avg_Utility_Score']
    hints['low_impact']=(f"'{bottom_attribute}' (Score: {bottom_score:.1f}) es el menos valorado.")
    if len(utilities_df_sorted)>1:
        second_attribute=utilities_df_sorted.iloc[1]['Attribute']
        second_score=utilities_df_sorted.iloc[1]['Avg_Utility_Score']
        gap=top_score-second_score
        if gap>15: hints['dominance_gap']=(f"Brecha significativa ({gap:.1f} puntos) entre '{top_attribute}' y '{second_attribute}'.")
        elif gap<5: hints['close_contenders']=(f"Diferencia pequeña ({gap:.1f} puntos) entre '{top_attribute}' y '{second_attribute}'.")
    max_score=utilities_df_sorted['Avg_Utility_Score'].max()
    tier1_threshold=max_score*0.66;tier2_threshold=max_score*0.33
    tier1=utilities_df_sorted[utilities_df_sorted['Avg_Utility_Score']>=tier1_threshold]['Attribute'].tolist()
    tier3=utilities_df_sorted[utilities_df_sorted['Avg_Utility_Score']<tier2_threshold]['Attribute'].tolist()
    hints['tiers']=(f"Tiers: **Críticos:** {', '.join(tier1)}. **Menos Relevantes:** {', '.join(tier3)}.")
    top_consensus=tmb_df_sorted[tmb_df_sorted['Top_Box_%']==100]['Attribute'].tolist()
    bottom_consensus=tmb_df_sorted[tmb_df_sorted['Bottom_Box_%']==100]['Attribute'].tolist()
    if top_consensus: hints['top_consensus']=f"Consenso Top: {', '.join(top_consensus)}."
    if bottom_consensus: hints['bottom_consensus']=f"Consenso Bottom: {', '.join(bottom_consensus)}."
    hints['general_pricing']=("**Pricing:** Tier 1 justifica premium. Tier 3 base.")
    return hints

# --- Capa de Compatibilidad (Wrapper) ---

def run_maxdiff(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Wrapper para run_maxdiff_analysis que devuelve un diccionario
    compatible con las expectativas del blueprint/rutas originales.
    Esta es la función que DEBEN llamar las rutas existentes.

    Args:
        df (pd.DataFrame): DataFrame con los datos crudos de MaxDiff.

    Returns:
        Dict[str, Any]: Diccionario con las llaves esperadas por las rutas:
            - 'avg_df': DataFrame de utilidades promedio ('Attribute', 'Avg_Utility_Score').
            - 'tmb_df': DataFrame de scores TMB.
            - 'bar_json': Datos JSON para gráfico de barras Plotly (Utilidades).
            - 'stacked_json': Datos JSON para gráfico apilado Plotly (TMB).
    """
    logger.info("Ejecutando wrapper de compatibilidad 'run_maxdiff'...")
    # 1. Llamar a la función de análisis detallada
    full_analysis_results = run_maxdiff_analysis(df)

    # 2. Crear el diccionario de resultados compatible, mapeando las llaves
    compatible_results = {
        # Llave esperada por la ruta : Llave devuelta por run_maxdiff_analysis
        'avg_df':       full_analysis_results['utilities_df'],  # Mapeo clave
        'tmb_df':       full_analysis_results['tmb_df'],        # Coincide
        'bar_json':     full_analysis_results['bar_chart_json'],# Mapeo clave
        'stacked_json': full_analysis_results['stacked_bar_json'] # Mapeo clave
        # Se omiten deliberadamente: 'attributes', 'raw_counts_df', 'interpretation_hints'
        # porque el código de la ruta original no las procesa.
    }
    logger.info("Resultados mapeados a formato compatible para las rutas.")
    # 3. Devolver el diccionario con las llaves esperadas
    return compatible_results

# --- Ejemplo de uso (si se ejecuta el script directamente) ---
if __name__ == '__main__':
    print("Ejecutando módulo maxdiff_utils.py como script...")

    # Crear datos de ejemplo simulados (igual que antes)
    data = {COL_RESPONDENT_ID: [1]*5 + [2]*5 + [3]*5,
            COL_SET_ID: list(range(1, 6)) * 3,
            COL_BEST_ATTR: ['Precio','Calidad','Velocidad','Soporte','Marca','Calidad','Precio','Marca','Velocidad','Soporte','Velocidad','Soporte','Precio','Calidad','Marca'],
            COL_WORST_ATTR: ['Marca','Soporte','Precio','Calidad','Velocidad','Soporte','Marca','Calidad','Precio','Velocidad','Marca','Precio','Soporte','Velocidad','Calidad']}
    example_df = pd.DataFrame(data)

    print("\nDataFrame de Ejemplo:")
    print(example_df)

    try:
        # --- Prueba llamando al WRAPPER (como lo harían las rutas) ---
        print("\n--- Probando Wrapper 'run_maxdiff' ---")
        compatible_output = run_maxdiff(example_df)

        print("\nResultados (Formato Compatible):")
        print(f"  Claves disponibles: {list(compatible_output.keys())}")

        print("\n1. 'avg_df' (DataFrame):")
        print(compatible_output['avg_df'].round(2))

        print("\n2. 'tmb_df' (DataFrame):")
        print(compatible_output['tmb_df'].round(0))

        print("\n3. 'bar_json' (Dict):")
        print(f"  - Tiene {len(compatible_output['bar_json'].get('data',[]))} traza(s).")
        print(f"  - Título: {compatible_output['bar_json'].get('layout',{}).get('title')}")

        print("\n4. 'stacked_json' (Dict):")
        print(f"  - Tiene {len(compatible_output['stacked_json'].get('data',[]))} traza(s).")
        print(f"  - Título: {compatible_output['stacked_json'].get('layout',{}).get('title')}")

        # --- Opcional: Prueba llamando a la función interna detallada ---
        # print("\n--- Probando Función Interna 'run_maxdiff_analysis' ---")
        # detailed_output = run_maxdiff_analysis(example_df)
        # print(f"  Claves detalladas: {list(detailed_output.keys())}")
        # print("\nPistas de Interpretación (del análisis detallado):")
        # for key, hint in detailed_output['interpretation_hints'].items():
        #     print(f"  - {key.replace('_',' ').capitalize()}: {hint}")


    except Exception as e:
         print(f"\n--- ERROR durante el análisis de ejemplo ---")
         logger.exception("Error en bloque __main__")
         print(f"Error: {e}")
