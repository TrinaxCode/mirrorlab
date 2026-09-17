#!/bin/bash

echo "📦 Instalando dependencias necesarias..."

# Actualiza pip
pip install --upgrade pip

# Instala las librerías necesarias
pip install opencv-python mediapipe numpy

echo "✅ Dependencias instaladas correctamente"
echo ""
echo "📁 Creando carpeta de imágenes..."
mkdir -p images

echo "ℹ️  Para usar el programa:"
echo "1. Coloca imágenes PNG en la carpeta 'images/'"
echo "2. Nombra las imágenes como:"
echo "   - smile.png (para sonrisa)"
echo "   - surprised.png (para sorpresa)"
echo "   - sad.png (para tristeza)"
echo "   - angry.png (para enojo)"
echo "   - neutral.png (para expresión neutra)"
echo ""
echo "3. Ejecuta: python face_expression_detector.py"
