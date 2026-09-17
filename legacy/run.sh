#!/bin/bash

echo "🎭 Detector de Expresiones Faciales"
echo "===================================="
echo ""
echo "1️⃣  Instalar dependencias (primera vez)"
echo "2️⃣  Generar imágenes de ejemplo"
echo "3️⃣  Ejecutar el detector"
echo "4️⃣  Salir"
echo ""

read -p "Selecciona una opción (1-4): " option

case $option in
    1)
        echo "📦 Instalando dependencias..."
        pip install --upgrade pip
        pip install opencv-python mediapipe numpy
        mkdir -p images
        echo "✅ ¡Dependencias instaladas!"
        ;;
    2)
        echo "🎨 Generando imágenes de ejemplo..."
        python generate_example_images.py
        echo "✅ ¡Imágenes generadas!"
        ;;
    3)
        echo "🎥 Iniciando detector..."
        python face_expression_detector.py
        ;;
    4)
        echo "👋 ¡Hasta luego!"
        exit 0
        ;;
    *)
        echo "❌ Opción no válida"
        ;;
esac
