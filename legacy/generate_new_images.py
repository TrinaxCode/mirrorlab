"""
Generador de imágenes para nuevas expresiones
"""

import cv2
import numpy as np
from pathlib import Path

def create_image(text, color, filename):
    width, height = 1200, 700
    image = np.ones((height, width, 3), dtype=np.uint8)
    image[:] = color
    
    # Gradiente
    for i in range(height):
        alpha = i / height
        image[i] = cv2.addWeighted(image[i], 0.7, np.zeros_like(image[i]), 0.3, 0)
    
    # Texto principal
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 3
    thickness = 4
    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
    x = (width - text_size[0]) // 2
    y = (height // 2) - 50
    cv2.putText(image, text, (x, y), font, font_scale, (255, 255, 255), thickness)
    cv2.putText(image, text, (x-2, y-2), font, font_scale, color, thickness)
    
    # Borde
    cv2.rectangle(image, (20, 20), (width-20, height-20), (255, 255, 255), 5)
    
    filepath = Path("images") / filename
    cv2.imwrite(str(filepath), image)
    print(f"✅ Creada: {filename}")

if __name__ == "__main__":
    print("🎨 Generando imágenes para nuevas expresiones...\n")
    
    # Crear nuevas imágenes
    create_image("LENGUA", (100, 150, 255), "tongue.png")      # Azul/naranja
    create_image("PAZ ✌", (100, 255, 100), "peace.png")        # Verde
    create_image("AMOR ❤", (100, 100, 255), "love.png")        # Rojo
    
    print("\n✅ ¡Imágenes nuevas creadas!")
    print("\nAhora ejecuta: python face_expression_detector.py")
