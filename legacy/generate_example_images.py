"""
Generador de imágenes de prueba para las expresiones faciales
Crea imágenes de ejemplo si no tienes propias
"""

import cv2
import numpy as np
from pathlib import Path

def create_example_images(output_dir="images"):
    """Crea imágenes de ejemplo para cada expresión"""
    Path(output_dir).mkdir(exist_ok=True)
    
    # Dimensiones
    width, height = 1200, 700
    
    expressions = {
        "smile": {
            "color": (100, 255, 100),  # Verde
            "emoji": "😊",
            "text": "¡SONRISA!",
            "description": "Detectada una sonrisa feliz"
        },
        "surprised": {
            "color": (255, 200, 100),  # Naranja
            "emoji": "😲",
            "text": "¡SORPRESA!",
            "description": "¡Parece sorprendido!"
        },
        "sad": {
            "color": (100, 150, 255),  # Azul
            "emoji": "😢",
            "text": "TRISTEZA",
            "description": "Se detectó expresión triste"
        },
        "angry": {
            "color": (50, 50, 255),  # Rojo
            "emoji": "😠",
            "text": "¡ENOJO!",
            "description": "Se detectó enojo"
        },
        "neutral": {
            "color": (200, 200, 200),  # Gris
            "emoji": "😐",
            "text": "NEUTRAL",
            "description": "Expresión neutra"
        }
    }
    
    for emotion, info in expressions.items():
        # Crea imagen de fondo
        image = np.ones((height, width, 3), dtype=np.uint8)
        image[:] = info["color"]
        
        # Añade gradiente
        for i in range(height):
            alpha = i / height
            image[i] = cv2.addWeighted(image[i], 0.7, np.zeros_like(image[i]), 0.3, 0)
        
        # Escribe el texto principal
        font = cv2.FONT_HERSHEY_SIMPLEX
        text = info["text"]
        font_scale = 3
        thickness = 4
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        x = (width - text_size[0]) // 2
        y = (height // 2) - 50
        cv2.putText(image, text, (x, y), font, font_scale, (255, 255, 255), thickness)
        cv2.putText(image, text, (x-2, y-2), font, font_scale, info["color"], thickness)
        
        # Escribe descripción
        font_small = cv2.FONT_HERSHEY_SIMPLEX
        desc = info["description"]
        font_scale_small = 1.5
        thickness_small = 2
        text_size_small = cv2.getTextSize(desc, font_small, font_scale_small, thickness_small)[0]
        x_small = (width - text_size_small[0]) // 2
        y_small = (height // 2) + 100
        cv2.putText(image, desc, (x_small, y_small), font_small, font_scale_small, (255, 255, 255), thickness_small)
        
        # Dibuja un borde
        cv2.rectangle(image, (20, 20), (width-20, height-20), (255, 255, 255), 5)
        
        # Guarda la imagen
        filepath = Path(output_dir) / f"{emotion}.png"
        cv2.imwrite(str(filepath), image)
        print(f"✅ Creada imagen: {filepath}")

if __name__ == "__main__":
    print("🎨 Generando imágenes de ejemplo...")
    create_example_images()
    print("✅ ¡Imágenes de ejemplo creadas en la carpeta 'images/'!")
    print("\n💡 Puedes reemplazar estas imágenes con las tuyas propias.")
