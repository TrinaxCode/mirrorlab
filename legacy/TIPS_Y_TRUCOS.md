# 💡 Tips y Trucos - Detector de Expresiones Faciales

## 🎯 Mejorando la Precisión de Detección

### 1. Iluminación
- **Mejora:** Asegúrate de tener buena luz frontal
- **Evita:** Contraluz y sombras en la cara
- **Consejo:** La luz natural o una lámpara frente a ti es ideal

### 2. Distancia a la Cámara
- **Óptimo:** 30-60 cm de distancia
- **Muy cerca:** La cámara no verá toda la cara
- **Muy lejos:** Pérdida de precisión

### 3. Expresiones Claras
- **Sonrisa:** Levanta las comisuras de la boca claramente
- **Sorpresa:** Abre mucho los ojos y la boca
- **Tristeza:** Baja las comisuras y frunce las cejas
- **Enojo:** Frunce mucho las cejas y cierra los ojos

### 4. Fondo
- **Mejor:** Fondo liso y de contraste
- **Evita:** Fondos muy similares al color de tu piel
- **Consejo:** Un fondo blanco o azul funciona bien

## 🎨 Personalizar Imágenes

### Cambiar las Imágenes
1. Prepara tus propias imágenes (PNG recomendado)
2. Dimensiones: 1200x700 píxeles (puedes usar PhotoShop, GIMP o Canva)
3. Reemplaza los archivos en la carpeta `images/`
4. Usa nombres exactos:
   - `smile.png`
   - `surprised.png`
   - `sad.png`
   - `angry.png`
   - `neutral.png`

### Ideas Creativas
- Emojis grandes
- Personajes animados
- Memes personalizados
- Imágenes temáticas
- Colores degradados
- Mensajes motivacionales

## ⚙️ Configuración Avanzada

### Editar config.json

```json
{
  "image_dir": "images",              // Cambiar directorio de imágenes
  "display_width": 1200,              // Ancho de la ventana
  "display_height": 700,              // Alto de la ventana
  "min_detection_confidence": 0.5,    // Mayor = más estricto
  "min_tracking_confidence": 0.5,     // Mayor = más estable
  "smooth_emotion_history": 5         // Más = más suavizado
}
```

## 🔧 Ajustes de Sensibilidad

Si la detección es:

### **Muy Sensible** (cambia de expresión frecuentemente)
```json
{
  "smooth_emotion_history": 10,           // Aumenta el suavizado
  "min_detection_confidence": 0.7         // Más estricto
}
```

### **Muy Poco Sensible** (no detecta cambios)
```json
{
  "smooth_emotion_history": 2,            // Menos suavizado
  "min_detection_confidence": 0.3         // Menos estricto
}
```

## 🎮 Usos Avanzados

### 1. Integración con Aplicaciones
```python
from face_expression_detector import ExpressionDetector

detector = ExpressionDetector()
# Tu código que usa detector.current_emotion
```

### 2. Obtener la Expresión Detectada
```python
expression, results = detector.process_frame(frame)
print(f"Expresión detectada: {expression}")
```

### 3. Guardar Datos de Expresiones
```python
# Modificar el script para guardar en CSV
timestamp, expression = time.time(), detector.current_emotion
with open('emociones.csv', 'a') as f:
    f.write(f"{timestamp},{expression}\n")
```

## 🐛 Debugging

### Ver Landmarks Faciales
```python
detector.run(show_landmarks=True)
```
Esto mostrará los puntos de referencia faciales que el programa está analizando.

### Registrar Capturas
Presiona `s` durante la ejecución para guardar capturas con timestamp.

## 📊 Estadísticas

Para agregar un contador de expresiones:

```python
from collections import defaultdict

emotion_count = defaultdict(int)

# En el loop principal:
emotion_count[detector.current_emotion] += 1

# Al finalizar:
for emotion, count in emotion_count.items():
    print(f"{emotion}: {count}")
```

## 🔊 Agregar Sonidos

```python
import winsound  # Windows
# o
import os
os.system(f'play audio_file.wav')  # Linux/Mac con SoX
```

## 💾 Grabar Video Completo

```python
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter('output.mp4', fourcc, 30.0, (width, height))

# En el loop:
out.write(expression_image)

# Al finalizar:
out.release()
```

## 📱 Integrar con Discord/OBS

1. **Para OBS:** Usa VirtualCam para capturar la salida
2. **Para Discord:** Comparte tu pantalla con la aplicación abierta
3. **Para Twitch:** Igual que Discord

## 🎬 Crear un Filtro de Video

```python
# Superponer efectos sobre el video en lugar de imágenes fijas
overlay_alpha = 0.7
expression_image = cv2.addWeighted(
    expression_image, overlay_alpha,
    cam_frame, 1 - overlay_alpha, 0
)
```

## ⏱️ Limitaciones Conocidas

- Funciona mejor con una cara a la vez
- Requiere buena iluminación
- Las gafas de sol pueden afectar la precisión
- Maquillaje excesivo puede confundir al detector
- Funciona mejor con rostros de frente

## 🚀 Próximas Características Sugeridas

- [ ] Detección de múltiples caras
- [ ] Exportar reportes en PDF
- [ ] Integración con base de datos
- [ ] Panel web para visualizar en tiempo real
- [ ] Procesamiento en GPU (CUDA)
- [ ] Detección de puntos de atención
- [ ] Análisis de estrés/fatiga
- [ ] Reconocimiento de gestos con manos

## 📚 Recursos Útiles

- [MediaPipe Documentación](https://mediapipe.dev/)
- [OpenCV Tutoriales](https://docs.opencv.org/)
- [NumPy Guía](https://numpy.org/doc/)

## 🤔 Preguntas Frecuentes

**P: ¿Funciona con múltiples caras?**  
R: Actualmente está optimizado para una cara. Puedes modificarlo para múltiples.

**P: ¿Puedo usar esto en un teléfono?**  
R: Sí, con Kivy u otra librería móvil de Python.

**P: ¿Necesito internet?**  
R: Mediapipe descarga modelos la primera vez, luego no necesita conexión.

**P: ¿Funciona con cámaras IP?**  
R: Sí, reemplaza VideoCapture(0) con la URL de la cámara.

---

¡Diviértete experimentando con diferentes expresiones y personalizaciones! 🎉
