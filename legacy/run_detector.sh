#!/bin/bash

# ============================================================
# SCRIPT PARA EJECUTAR EL DETECTOR DE EXPRESIONES FACIALES
# ============================================================

echo "🎭 Detector de Expresiones Faciales"
echo "===================================="
echo ""

# Obtener la ruta del script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Usar el Python del venv
PYTHON="${SCRIPT_DIR}/.venv/bin/python"

# Verificar que Python existe
if [ ! -f "$PYTHON" ]; then
    echo "❌ Error: No se encontró Python en el venv"
    exit 1
fi

echo "🔧 Ejecutando verificación rápida..."
"$PYTHON" -c "import cv2; print('✅ OpenCV disponible')" 2>/dev/null

echo ""
echo "🎥 Abriendo detector..."
echo "Presiona 'q' para salir, 's' para capturar"
echo ""

# Ejecutar el detector
"$PYTHON" "$SCRIPT_DIR/face_expression_detector.py"
