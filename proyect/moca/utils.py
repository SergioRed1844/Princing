# proyect/moca/utils.py
# -*- coding: utf-8 -*-
"""
Módulo de Utilidades para Análisis MOCA
(Matriz de Oportunidades y Consistencia Estratégica).

Proporciona funciones para procesar datos de Precio y Valor, calcular
la Línea de Valor Justo, generar una Matriz MOCA, preparar datos para
visualización con Plotly (Price-Value Map - PVM), y ofrecer insights
estratégicos enfocados en oportunidad y consistencia.

**Incluye wrapper de compatibilidad 'run_moca' para rutas existentes.**
"""

import logging
from typing import Dict, Any, Tuple, List, Optional
import pandas as pd
import numpy as np
# Usaremos sklearn para la regresión lineal (Línea de Valor Justo)
# Asegúrate de que esté instalado: pip install scikit-learn
try:
    from sklearn.linear_model import LinearRegression
except ImportError:
    LinearRegression = None # Marcar como no disponible si falta sklearn

logger = logging.getLogger(__name__)

# --- Constantes y Configuraciones ---
# Nombres de columnas esperados (ajustar si es necesario)
COL_ENTITY = 'EntityName' # Nombre genérico (Producto, Marca, Competidor)
COL_PRICE = 'PriceMetric'
COL_VALUE = 'ValueMetric'

# --- Funciones Principales de Análisis ---

def run_moca_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Orquesta el pipeline completo de análisis MOCA.
    (Función interna detallada).

    Args:
        df (pd.DataFrame): DataFrame con los datos crudos, conteniendo al menos
                           las columnas COL_ENTITY, COL_PRICE, COL_VALUE.

    Returns:
        Dict[str, Any]: Un diccionario conteniendo los resultados clave detallados:
            - 'moca_matrix' (pd.DataFrame): Matriz MOCA con clasificación estratégica.
                                          Columnas: [COL_ENTITY, COL_PRICE, COL_VALUE,
                                                   'Value_Deviation', 'MOCA_Zone']
            - 'pvm_json' (Dict): Datos JSON para gráfico de dispersión Plotly (Price-Value Map).
            - 'fair_value_line_params' (Dict): Parámetros de la línea de valor justo.
            - 'avg_metrics' (Dict): Métricas promedio (precio, valor).
            - 'insights' (Dict): Sugerencias textuales para interpretación estratégica MOCA.

    Raises:
        RuntimeError: Si scikit-learn no está instalado.
        ValueError: Si las columnas requeridas no se encuentran o hay datos insuficientes.
        Exception: Para cualquier otro error durante el procesamiento.
    """
    if LinearRegression is None:
         msg = "La librería 'scikit-learn' es necesaria para el análisis MOCA (regresión lineal). Por favor, instálala (`pip install scikit-learn`)."
         logger.critical(msg)
         raise RuntimeError(msg)

    logger.info(f"Iniciando análisis MOCA detallado (run_moca_analysis) en DataFrame con {df.shape[0]} filas.")
    try:
        # 1. Validación y Preparación de Entrada
        validated_df = _validate_and_prepare_moca_df(df)
        logger.debug("Validación y preparación de DataFrame de entrada MOCA completada.")

        # 2. Calcular Línea de Valor Justo y Métricas Promedio
        fair_value_params, avg_metrics = _calculate_fair_value_line(validated_df)
        logger.info(f"Línea de Valor Justo MOCA calculada: Pendiente={fair_value_params['slope']:.2f}, Intercepto={fair_value_params['intercept']:.2f}")
        logger.info(f"Métricas promedio MOCA: Precio={avg_metrics['avg_price']:.2f}, Valor={avg_metrics['avg_value']:.2f}")

        # 3. Calcular Desviación de Valor y Clasificar en Matriz MOCA
        moca_matrix_df = _calculate_moca_zones(validated_df, fair_value_params, avg_metrics)
        logger.info("Clasificación en zonas MOCA completada.")

        # 4. Preparar Datos para Gráfico de Dispersión Plotly (Price-Value Map - PVM)
        pvm_json = _prepare_pvm_chart_json(moca_matrix_df, fair_value_params, avg_metrics)
        logger.info("Datos para Price-Value Map (PVM) generados.")

        # 5. Generar Pistas de Interpretación Estratégica MOCA
        insights = _generate_moca_interpretation_hints(moca_matrix_df, avg_metrics)
        logger.info("Pistas de interpretación estratégica MOCA generadas.")

        # Diccionario detallado devuelto por esta función interna
        detailed_results = {
            'moca_matrix': moca_matrix_df, # Llave esperada por wrapper
            'pvm_json': pvm_json,           # Llave esperada por wrapper
            'fair_value_line_params': fair_value_params,
            'avg_metrics': avg_metrics,
            'insights': insights
        }
        logger.info("Análisis MOCA detallado completado exitosamente.")
        return detailed_results

    except ValueError as ve:
        logger.error(f"Error de validación o datos insuficientes en MOCA: {ve}", exc_info=False)
        raise
    except Exception as e:
        logger.error(f"Error inesperado durante el análisis MOCA detallado: {e}", exc_info=True)
        raise

# --- Funciones Auxiliares de Cálculo y Preparación (Adaptadas de ComStrat) ---

def _validate_and_prepare_moca_df(df: pd.DataFrame) -> pd.DataFrame:
    """Valida columnas requeridas, tipos de datos y elimina filas inválidas para MOCA."""
    required_columns = [COL_ENTITY, COL_PRICE, COL_VALUE]
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Faltan columnas requeridas para MOCA: {', '.join(missing_cols)}")

    df_copy = df[required_columns].copy()
    df_copy[COL_PRICE] = pd.to_numeric(df_copy[COL_PRICE], errors='coerce')
    df_copy[COL_VALUE] = pd.to_numeric(df_copy[COL_VALUE], errors='coerce')

    initial_rows = len(df_copy)
    df_copy = df_copy.dropna(subset=[COL_PRICE, COL_VALUE])
    df_copy = df_copy[df_copy[COL_ENTITY].astype(str).str.strip() != '']
    df_copy = df_copy.drop_duplicates(subset=[COL_ENTITY])
    final_rows = len(df_copy)

    if final_rows < initial_rows:
        logger.warning(f"MOCA: Se eliminaron {initial_rows - final_rows} filas por datos inválidos/duplicados en {COL_ENTITY}, {COL_PRICE} o {COL_VALUE}.")

    if final_rows < 3:
        raise ValueError(f"Datos insuficientes para análisis MOCA. Se requieren al menos 3 entidades con datos válidos. Encontrados: {final_rows}")

    return df_copy

def _calculate_fair_value_line(df: pd.DataFrame) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Calcula la línea de valor justo (Value ~ Price) usando Regresión Lineal."""
    # Idéntico a ComStrat
    X = df[[COL_PRICE]]
    y = df[COL_VALUE]
    model = LinearRegression()
    model.fit(X, y)
    fair_value_params = {'slope': model.coef_[0], 'intercept': model.intercept_}
    avg_metrics = {'avg_price': df[COL_PRICE].mean(), 'avg_value': df[COL_VALUE].mean()}
    return fair_value_params, avg_metrics

def _calculate_moca_zones(df: pd.DataFrame, fv_params: Dict[str, float], avg_metrics: Dict[str, float]) -> pd.DataFrame:
    """Calcula la desviación de valor y asigna zonas MOCA enfocando en Oportunidad y Consistencia."""
    df_copy = df.copy()
    df_copy['Expected_Value'] = fv_params['intercept'] + fv_params['slope'] * df_copy[COL_PRICE]
    df_copy['Value_Deviation'] = df_copy[COL_VALUE] - df_copy['Expected_Value']
    avg_price = avg_metrics['avg_price']

    # Lógica de Zonas MOCA (ajustando nombres para Opportunity/Consistency)
    conditions = [
        (df_copy['Value_Deviation'] > 0) & (df_copy[COL_PRICE] < avg_price),   # Alto Valor, Bajo Precio
        (df_copy['Value_Deviation'] > 0) & (df_copy[COL_PRICE] >= avg_price),  # Alto Valor, Alto Precio
        (df_copy['Value_Deviation'] <= 0) & (df_copy[COL_PRICE] >= avg_price), # Bajo Valor, Alto Precio
        (df_copy['Value_Deviation'] <= 0) & (df_copy[COL_PRICE] < avg_price)   # Bajo Valor, Bajo Precio
    ]
    # Nombres de zonas MOCA con enfoque en Oportunidad y Consistencia
    zone_names = [
        '1. Value Leader / Opportunity', # Alto valor a buen precio -> Oportunidad
        '2. Premium / Consistent',     # Alto valor justifica alto precio -> Consistente
        '4. Inconsistent / Risk',      # Bajo valor a alto precio -> Inconsistente, Riesgo
        '3. Economy / Potential Drag'  # Bajo valor, bajo precio -> Podría lastrar si no es nicho
    ]

    df_copy['MOCA_Zone'] = np.select(conditions, zone_names, default='Indeterminado')

    moca_result_df = df_copy[[COL_ENTITY, COL_PRICE, COL_VALUE, 'Value_Deviation', 'MOCA_Zone']]
    moca_result_df = moca_result_df.sort_values(by=['MOCA_Zone', 'Value_Deviation'], ascending=[True, False]).reset_index(drop=True)
    return moca_result_df

def _prepare_pvm_chart_json(moca_df: pd.DataFrame, fv_params: Dict[str, float], avg_metrics: Dict[str, float]) -> Dict[str, Any]:
    """Prepara datos para un gráfico de dispersión Plotly (Price-Value Map - PVM)."""
    # Prácticamente idéntico a ComStrat, solo cambia el título y quizás colores/nombres leyenda
    if moca_df.empty:
        return {"data": [], "layout": {"title": "Price-Value Map (PVM) para MOCA - Sin Datos"}}

    traces = []
    # Colores adaptados a nombres de zona MOCA
    zone_colors = {
        '1. Value Leader / Opportunity': '#2ca02c', # Verde
        '2. Premium / Consistent':     '#1f77b4', # Azul
        '3. Economy / Potential Drag': '#ff7f0e', # Naranja
        '4. Inconsistent / Risk':      '#d62728', # Rojo
        'Indeterminado': '#7f7f7f'               # Gris
    }

    for zone, color in zone_colors.items():
        zone_df = moca_df[moca_df['MOCA_Zone'] == zone]
        if not zone_df.empty:
             traces.append({
                 'type': 'scatter', 'mode': 'markers+text',
                 'x': zone_df[COL_PRICE].tolist(), 'y': zone_df[COL_VALUE].tolist(),
                 'text': zone_df[COL_ENTITY].tolist(), 'textposition': 'top right',
                 'marker': {'color': color, 'size': 10}, 'name': zone
             })

    # Línea de Valor Justo (igual)
    min_price=moca_df[COL_PRICE].min()*0.9; max_price=moca_df[COL_PRICE].max()*1.1
    x_line=[min_price, max_price]
    y_line=[fv_params['intercept']+fv_params['slope']*p for p in x_line]
    traces.append({'type':'scatter','mode':'lines','x':x_line,'y':y_line,'line':{'color':'grey','dash':'dash'},'name':'Línea Valor Justo'})

    # Líneas de Promedio (igual)
    avg_price=avg_metrics['avg_price']; avg_value=avg_metrics['avg_value']
    x_range=[moca_df[COL_PRICE].min()*0.9, moca_df[COL_PRICE].max()*1.1]
    y_range=[moca_df[COL_VALUE].min()*0.9, moca_df[COL_VALUE].max()*1.1]
    traces.append({'type':'scatter','mode':'lines','x':[avg_price,avg_price],'y':y_range,'line':{'color':'lightgrey','dash':'dot'},'name':'Precio Promedio'})
    traces.append({'type':'scatter','mode':'lines','x':x_range,'y':[avg_value,avg_value],'line':{'color':'lightgrey','dash':'dot'},'name':'Valor Promedio'})

    # Layout con título PVM/MOCA
    layout = {
        'title': 'Price-Value Map (PVM) - Análisis MOCA',
        'xaxis': {'title': f'{COL_PRICE}'},
        'yaxis': {'title': f'{COL_VALUE}'},
        'hovermode': 'closest', 'showlegend': True,
        'legend': {'title': 'Zona Estratégica MOCA'},
        'annotations': [
            {'x':avg_price,'y':y_range[0],'xref':'x','yref':'y','text':'Avg Price','showarrow':False,'yanchor':'bottom'},
            {'x':x_range[0],'y':avg_value,'xref':'x','yref':'y','text':'Avg Value','showarrow':False,'xanchor':'left'}
        ]
    }
    return {'data': traces, 'layout': layout}

def _generate_moca_interpretation_hints(moca_df: pd.DataFrame, avg_metrics: Dict[str, float]) -> Dict[str, str]:
    """Genera insights estratégicos MOCA enfocados en Oportunidad y Consistencia."""
    hints = {}
    if moca_df.empty:
        return {"general": "No hay datos suficientes para generar insights MOCA."}

    # Analizar cada zona MOCA
    for zone in moca_df['MOCA_Zone'].unique():
        entities_in_zone = moca_df[moca_df['MOCA_Zone'] == zone][COL_ENTITY].tolist()
        count = len(entities_in_zone)
        if count == 0: continue

        entities_str = ", ".join(entities_in_zone)
        key_name = zone.split('/')[0].strip().lower().replace(' ', '_') # e.g., 'value_leader'

        if zone == '1. Value Leader / Opportunity':
            hints[key_name] = (f"**{zone}:** {entities_str} ({count}). Líderes en valor relativo. Excelente **oportunidad** de crecimiento o ajuste de precios al alza. "
                               f"Representan alta **consistencia** entre valor entregado y precio competitivo.")
        elif zone == '2. Premium / Consistent':
             hints[key_name] = (f"**{zone}:** {entities_str} ({count}). Posición premium **consistente**: alto valor justifica alto precio. "
                                f"Menor **oportunidad** de subida de precio sin mejora de valor. Clave: defender la diferenciación.")
        elif zone == '3. Economy / Potential Drag':
             hints[key_name] = (f"**{zone}:** {entities_str} ({count}). Nicho económico. Valor por debajo de lo esperado, pero precio bajo. "
                                f"**Consistencia** precaria, vulnerables si no es un nicho claro. Poca **oportunidad** de precio. Podrían ser un lastre ('drag') para el portfolio.")
        elif zone == '4. Inconsistent / Risk':
             hints[key_name] = (f"**{zone}:** {entities_str} ({count}). Estrategia **inconsistente**: precio alto no respaldado por valor. "
                                f"Alto riesgo, baja **oportunidad** salvo nichos insensibles. Requieren acción correctiva urgente (mejorar valor o bajar precio).")
        else: # Indeterminado
            hints['indeterminado'] = (f"**Indeterminado:** {entities_str} ({count}). No clasificados.")

    # Insight General MOCA
    hints['general_strategy'] = (
        f"La matriz MOCA evalúa la **consistencia** estratégica (alineación Precio-Valor) y las **oportunidades** de mercado. "
        f"Las zonas 'Value Leader' y 'Premium' muestran mayor consistencia. Las mayores oportunidades (precio/cuota) están en 'Value Leader'. "
        f"Las zonas 'Inconsistent' y 'Economy' requieren revisión estratégica."
    )
    hints['fair_value_line'] = (
        f"La Línea de Valor Justo en el PVM representa la relación 'normal' Precio-Valor. Desviarse positivamente (arriba) es favorable; negativamente (abajo) indica inconsistencia o posicionamiento económico."
    )
    return hints

# --- Capa de Compatibilidad (Wrapper) ---

def run_moca(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Wrapper de compatibilidad para el blueprint de MOCA.
    Llama a run_moca_analysis y devuelve solo lo que la ruta necesita:
        - 'moca_matrix': DataFrame de la matriz MOCA
        - 'pvm_json': JSON para el Price-Value Map

    Args:
        df (pd.DataFrame): DataFrame de entrada para MOCA.

    Returns:
        Dict[str, Any]: Diccionario con llaves 'moca_matrix' y 'pvm_json'.

    Raises:
        RuntimeError: Si scikit-learn no está instalado.
        ValueError: Si los datos de entrada son inválidos o insuficientes.
        KeyError: Si el análisis interno no devuelve las llaves esperadas.
        Exception: Para cualquier otro error durante el procesamiento.
    """
    logger.info("Ejecutando wrapper 'run_moca' para compatibilidad con el blueprint MOCA...")
    # 1. Llamar a la función de análisis detallada
    full_analysis_results = run_moca_analysis(df)

    # 2. Validar y extraer las llaves requeridas por el blueprint
    if 'moca_matrix' not in full_analysis_results or 'pvm_json' not in full_analysis_results:
        # Loggear qué llaves SÍ están presentes para depuración
        available_keys = list(full_analysis_results.keys())
        logger.error(f"Error en wrapper run_moca: Faltan llaves esperadas. Esperadas: ['moca_matrix', 'pvm_json']. Encontradas: {available_keys}")
        raise KeyError("Las llaves 'moca_matrix' y/o 'pvm_json' no se encontraron en los resultados detallados de MOCA.")

    # 3. Crear y devolver el diccionario compatible
    compatible_results = {
        'moca_matrix': full_analysis_results['moca_matrix'],
        'pvm_json':    full_analysis_results['pvm_json']
        # Se omiten 'fair_value_line_params', 'avg_metrics', 'insights'
    }
    logger.info("Resultados MOCA mapeados a formato compatible para las rutas.")
    return compatible_results


# --- Ejemplo de uso (si se ejecuta el script directamente) ---
if __name__ == '__main__':
    print("Ejecutando módulo moca_utils.py como script...")

    # Crear datos de ejemplo simulados (usando nuevos nombres de columna)
    data_moca = {
        COL_ENTITY: ['Producto Alpha', 'Producto Beta', 'Competidor X', 'Competidor Y', 'Producto Gamma'],
        COL_PRICE:  [150,            130,           140,            90,             100],
        COL_VALUE:  [90,             75,            80,             65,             70]
    }
    example_moca_df = pd.DataFrame(data_moca)

    print("\nDataFrame de Ejemplo MOCA:")
    print(example_moca_df)

    if LinearRegression is None:
        print("\nERROR: scikit-learn no está instalado. No se puede ejecutar el ejemplo completo MOCA.")
        print("Por favor, instala con: pip install scikit-learn")
    else:
        try:
            # --- Prueba llamando al WRAPPER ---
            print("\n--- Probando Wrapper 'run_moca' ---")
            compatible_output = run_moca(example_moca_df)

            print("\nResultados (Formato Compatible):")
            print(f"  Claves disponibles: {list(compatible_output.keys())}")

            print("\n1. 'moca_matrix' (DataFrame):")
            with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 1000):
                print(compatible_output['moca_matrix'].round(2))

            print("\n2. 'pvm_json' (Dict):")
            print(f"  - Tiene {len(compatible_output['pvm_json'].get('data',[]))} traza(s).")
            print(f"  - Título: {compatible_output['pvm_json'].get('layout',{}).get('title')}")

            # --- Opcional: Acceder a los resultados detallados ---
            print("\n--- Información Adicional del Análisis Detallado MOCA ---")
            detailed_output = run_moca_analysis(example_moca_df)
            print("\nPistas de Interpretación MOCA:")
            for key, hint in detailed_output['insights'].items():
                print(f"  - {key.replace('_',' ').capitalize()}: {hint}")

        except Exception as e:
             print(f"\n--- ERROR durante el análisis de ejemplo MOCA ---")
             logger.exception("Error en bloque __main__ de MOCA")
             print(f"Error: {e}")
