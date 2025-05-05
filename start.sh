#!/usr/bin/env bash

# === Modo Estricto y Seguro ===
# -e: Salir inmediatamente si un comando falla.
# -u: Tratar variables no definidas como un error.
# -o pipefail: El código de salida de una tubería es el del último comando que falló.
set -euo pipefail

# === Variables de Configuración ===
VENV_DIR="env"               # Nombre del directorio del entorno virtual
REQUIREMENTS_FILE="requirements.txt" # Archivo de dependencias
DEFAULT_PORT=5000            # Puerto por defecto para Flask
FALLBACK_PORT=5001           # Puerto alternativo si el defecto está ocupado
FLASK_APP_FILE="app.py"      # Archivo principal de la aplicación Flask
HOST_IP="0.0.0.0"            # Escuchar en todas las interfaces (accesible en red local)
# HOST_IP="127.0.0.1"        # Descomentar para escuchar solo en localhost

# === Funciones Auxiliares ===
# Imprime mensajes informativos con un prefijo
info() {
    # Usar printf para mejor control de formato y compatibilidad
    printf "✅ INFO: %s\n" "$1"
}

# Imprime advertencias a stderr con un prefijo
warn() {
    printf "⚠️ WARN: %s\n" "$1" >&2
}

# Imprime errores a stderr con un prefijo y sale del script
die() {
    printf "❌ ERROR: %s\n" "$1" >&2
    exit 1
}

# Verifica si un puerto TCP está en estado LISTEN
# Usa 'lsof' que es común en macOS y Linux.
# Devuelve 0 (éxito en bash) si el puerto está en uso, 1 (fallo en bash) si está libre.
is_port_in_use() {
    # 'local' SÍ se puede usar DENTRO de una función
    local port="${1}"
    local check_cmd="lsof"

    # Verificar si el comando lsof existe
    if ! command -v "${check_cmd}" >/dev/null 2>&1; then
        # Fallback básico si lsof no existe (menos fiable)
        warn "'${check_cmd}' no encontrado. No se puede verificar el puerto ${port} de forma fiable."
        # Asumimos que no está en uso, pero la app podría fallar
        return 1 # Código de salida de fallo (puerto parece libre)
    fi

    # Ejecutar lsof para buscar sockets TCP escuchando en el puerto especificado
    if "${check_cmd}" -iTCP:"${port}" -sTCP:LISTEN -P -n -t >/dev/null 2>&1; then
        # Si lsof encuentra algo, sale con 0 (éxito), significa que el puerto está ocupado
        return 0 # Código de salida de éxito (puerto en uso)
    else
        # Si lsof no encuentra nada, sale con 1 (fallo), significa que el puerto está libre
        return 1 # Código de salida de fallo (puerto libre)
    fi
}

# --- Inicio de la Ejecución del Script ---
info "Iniciando script de arranque para Pricing Dashboard..."

# 1. Asegurar que estamos en el directorio del script
cd "$(dirname "${BASH_SOURCE[0]}")"
info "Directorio de trabajo: $(pwd)"

# 2. Activar Entorno Virtual
info "Activando entorno virtual '${VENV_DIR}'..."
ACTIVATE_PATH="${VENV_DIR}/bin/activate"
if [[ ! -f "${ACTIVATE_PATH}" ]]; then
    die "Entorno virtual no encontrado en '${VENV_DIR}'. Créalo con: python3 -m venv ${VENV_DIR}"
fi
# shellcheck disable=SC1090 # Desactivar advertencia SC para 'source' con variable
source "${ACTIVATE_PATH}"
info "Entorno virtual activado. Python: $(python --version)"

# 3. Instalar/Actualizar Dependencias
info "Instalando/Actualizando dependencias desde '${REQUIREMENTS_FILE}'..."
# Es buena práctica actualizar pip dentro del entorno
python -m pip install --upgrade pip --quiet # Usar --quiet para menos verbosidad
# Instalar los paquetes listados
python -m pip install -r "${REQUIREMENTS_FILE}" --quiet # Usar --quiet
info "Dependencias instaladas/actualizadas."

# 4. Configurar Variables de Entorno para Flask
info "Configurando variables de entorno de Flask..."
export FLASK_APP="${FLASK_APP_FILE}"
# Para modo debug en Flask >= 2.3, se recomienda usar FLASK_DEBUG=1
export FLASK_DEBUG=1
info "-> FLASK_APP='${FLASK_APP}'"
info "-> FLASK_DEBUG='${FLASK_DEBUG}' (Modo Desarrollo Activado)"

# 5. Determinar Puerto Disponible
# Leer FLASK_RUN_PORT si está definido, si no, usar DEFAULT_PORT
target_port="${FLASK_RUN_PORT:-${DEFAULT_PORT}}"
info "Puerto objetivo inicial: ${target_port}"

# Verificar si el puerto objetivo está en uso
if is_port_in_use "${target_port}"; then
    # CORRECCIÓN: 'process_info' ahora es variable global del script (no 'local')
    process_info=""
    if command -v lsof >/dev/null 2>&1; then
         # El comando ps puede fallar si el PID ya no existe, usamos || true para ignorar error
         # Obtener el comando asociado al PID
         pid=$(lsof -iTCP:"${target_port}" -sTCP:LISTEN -P -n -t | head -n 1)
         if [[ -n "$pid" ]]; then
            # ps -o comm= muestra solo el nombre del comando
            process_name=$(ps -p "${pid}" -o comm= || true)
            # Usar basename para obtener solo el nombre del ejecutable
            [[ -n "$process_name" ]] && process_info=" (Posiblemente usado por: $(basename "${process_name}"))"
         fi
    fi
    warn "Puerto ${target_port} está actualmente en uso${process_info}. Intentando usar el puerto alternativo: ${FALLBACK_PORT}."
    target_port=${FALLBACK_PORT} # Cambiar al puerto de fallback

    # Verificar si el puerto de fallback también está en uso
    if is_port_in_use "${target_port}"; then
        # CORRECCIÓN: 'fallback_process_info' ahora es variable global del script (no 'local')
        fallback_process_info=""
         if command -v lsof >/dev/null 2>&1; then
             pid=$(lsof -iTCP:"${target_port}" -sTCP:LISTEN -P -n -t | head -n 1)
             if [[ -n "$pid" ]]; then
                 process_name=$(ps -p "${pid}" -o comm= || true)
                 [[ -n "$process_name" ]] && fallback_process_info=" (Posiblemente usado por: $(basename "${process_name}"))"
             fi
         fi
        die "El puerto alternativo ${target_port} también está en uso${fallback_process_info}. Libera un puerto o define FLASK_RUN_PORT."
    fi
    info "Usando puerto alternativo: ${target_port}"
else
    info "Puerto ${target_port} está disponible."
fi

# 6. Iniciar la Aplicación Flask
info "🚀 Iniciando servidor de desarrollo Flask en http://${HOST_IP}:${target_port}"
info "   (Presiona CTRL+C para detener el servidor)"
echo "----------------------------------------------------------------------"

# Usar 'exec' para reemplazar este script con el proceso de Flask.
# Esto permite que Flask reciba directamente señales como CTRL+C.
# Se pasa el puerto determinado a Flask.
# Flask usará FLASK_APP y FLASK_DEBUG desde las variables de entorno.
exec flask run --host="${HOST_IP}" --port="${target_port}"

# Si exec falla por alguna razón, se mostrará este mensaje
warn "El comando 'flask run' falló o fue interrumpido antes de iniciar completamente."
exit 1 # Salir con error si exec no funcionó