"""
EJEMPLOS DE CÓDIGO - Cómo Usar el Detector en tus Propios Proyectos
"""

# ============================================================================
# EJEMPLO 1: Uso Básico Simple
# ============================================================================

from face_expression_detector import ExpressionDetector

# Crear detector
detector = ExpressionDetector()

# Ejecutar
detector.run()


# ============================================================================
# EJEMPLO 2: Obtener la Expresión Actual Dentro de tu Código
# ============================================================================

from face_expression_detector import ExpressionDetector
import cv2

detector = ExpressionDetector()
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Procesa el frame
    expression, results = detector.process_frame(frame)
    
    # Ahora puedes hacer algo con la expresión detectada
    print(f"Expresión actual: {expression}")
    
    if expression == "smile":
        print("¡El usuario está sonriendo!")
    elif expression == "surprised":
        print("¡El usuario está sorprendido!")
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()


# ============================================================================
# EJEMPLO 3: Usar el Detector Avanzado con Estadísticas
# ============================================================================

from advanced_detector import AdvancedExpressionDetector

# Con estadísticas
detector = AdvancedExpressionDetector(record_stats=True)
detector.run(show_stats=True)

# Las estadísticas se guardan en emotion_stats.csv


# ============================================================================
# EJEMPLO 4: Integración con Aplicación Personalizada
# ============================================================================

from face_expression_detector import ExpressionDetector
import cv2
import numpy as np

class MiAplicacion:
    def __init__(self):
        self.detector = ExpressionDetector()
        self.cap = cv2.VideoCapture(0)
        
        # Acciones para cada expresión
        self.actions = {
            "smile": self.on_smile,
            "surprised": self.on_surprised,
            "sad": self.on_sad,
            "angry": self.on_angry,
            "neutral": self.on_neutral,
        }
    
    def on_smile(self):
        print("🙂 Sonrisa detectada - Reproduciendo sonido feliz")
        # os.system('play sonido_feliz.wav')
    
    def on_surprised(self):
        print("😲 ¡Sorpresa!")
        # Hacer algo especial aquí
    
    def on_sad(self):
        print("😢 Tristeza detectada")
    
    def on_angry(self):
        print("😠 Enojo detectado")
    
    def on_neutral(self):
        pass  # No hacer nada
    
    def run(self):
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            expression, _ = self.detector.process_frame(frame)
            
            # Ejecutar la acción correspondiente
            if expression in self.actions:
                self.actions[expression]()
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        self.cap.release()
        cv2.destroyAllWindows()

# Usar
app = MiAplicacion()
app.run()


# ============================================================================
# EJEMPLO 5: Aplicación Web Flask (Básica)
# ============================================================================

"""
from flask import Flask, jsonify, Response
from face_expression_detector import ExpressionDetector
import cv2

app = Flask(__name__)
detector = ExpressionDetector()
cap = cv2.VideoCapture(0)

@app.route('/emotion', methods=['GET'])
def get_emotion():
    ret, frame = cap.read()
    if ret:
        expression, _ = detector.process_frame(frame)
        return jsonify({"emotion": expression})
    return jsonify({"error": "No se pudo acceder a la cámara"}), 500

@app.route('/emotion_stats', methods=['GET'])
def get_stats():
    return jsonify({
        "total_frames": detector.frame_count,
        "current_emotion": detector.current_emotion,
        "emotion_history": list(detector.emotion_history)
    })

if __name__ == '__main__':
    app.run(debug=True)
"""


# ============================================================================
# EJEMPLO 6: Guardar Datos de Emociones en CSV
# ============================================================================

"""
import csv
from datetime import datetime
from face_expression_detector import ExpressionDetector
import cv2

detector = ExpressionDetector()
cap = cv2.VideoCapture(0)

# Crear archivo CSV
with open('emociones.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Timestamp', 'Expresión', 'Frame'])

frame_count = 0
while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    expression, _ = detector.process_frame(frame)
    
    # Guardar cada 10 frames
    if frame_count % 10 == 0:
        with open('emociones.csv', 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                expression,
                frame_count
            ])
    
    frame_count += 1
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
"""


# ============================================================================
# EJEMPLO 7: Aplicación con Eventos (Event-driven)
# ============================================================================

"""
from face_expression_detector import ExpressionDetector
import cv2

class EventosDector:
    def __init__(self):
        self.detector = ExpressionDetector()
        self.listeners = {}
        self.last_emotion = None
    
    def on(self, emotion, callback):
        '''Registra un callback para una emoción'''
        if emotion not in self.listeners:
            self.listeners[emotion] = []
        self.listeners[emotion].append(callback)
    
    def trigger(self, emotion):
        '''Dispara los callbacks de una emoción'''
        if emotion in self.listeners:
            for callback in self.listeners[emotion]:
                callback(emotion)
    
    def run(self):
        cap = cv2.VideoCapture(0)
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            expression, _ = self.detector.process_frame(frame)
            
            # Dispara eventos solo cuando cambia la emoción
            if expression != self.last_emotion:
                self.trigger(expression)
                self.last_emotion = expression
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()

# Usar:
detector_eventos = EventosDector()

detector_eventos.on('smile', lambda e: print("😊 ¡Sonrisa detectada!"))
detector_eventos.on('surprised', lambda e: print("😲 ¡Sorpresa!"))
detector_eventos.on('sad', lambda e: print("😢 Tristeza detectada"))

detector_eventos.run()
"""


# ============================================================================
# EJEMPLO 8: Con Timer/Cooldown
# ============================================================================

"""
from face_expression_detector import ExpressionDetector
import cv2
import time

class DetectorConCooldown:
    def __init__(self, cooldown_seconds=2):
        self.detector = ExpressionDetector()
        self.cooldown = cooldown_seconds
        self.last_action_time = {}
    
    def can_trigger(self, emotion):
        '''Verifica si se puede disparar la acción'''
        current_time = time.time()
        if emotion not in self.last_action_time:
            return True
        return (current_time - self.last_action_time[emotion]) > self.cooldown
    
    def trigger(self, emotion):
        '''Ejecuta la acción solo si pasó el cooldown'''
        if self.can_trigger(emotion):
            print(f"Emoción: {emotion}")
            self.last_action_time[emotion] = time.time()
    
    def run(self):
        cap = cv2.VideoCapture(0)
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            expression, _ = self.detector.process_frame(frame)
            self.trigger(expression)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()

detector = DetectorConCooldown(cooldown_seconds=1)
detector.run()
"""


# ============================================================================
# EJEMPLO 9: Procesar Imágenes en Lote
# ============================================================================

"""
from face_expression_detector import ExpressionDetector
from pathlib import Path
import cv2

detector = ExpressionDetector()

# Procesar todas las imágenes en una carpeta
image_folder = Path('fotos/')
results = []

for image_file in image_folder.glob('*.jpg'):
    image = cv2.imread(str(image_file))
    if image is not None:
        expression, _ = detector.process_frame(image)
        results.append({
            'file': image_file.name,
            'emotion': expression
        })
        print(f"{image_file.name}: {expression}")

# Guardar resultados
for result in results:
    print(f"{result['file']}: {result['emotion']}")
"""


# ============================================================================
# EJEMPLO 10: Aplicación con Interfaz Gráfica (Tkinter)
# ============================================================================

"""
import tkinter as tk
from tkinter import Label, Button
from PIL import Image, ImageTk
from face_expression_detector import ExpressionDetector
import cv2
import threading

class AppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Detector de Emociones")
        self.root.geometry("800x600")
        
        self.detector = ExpressionDetector()
        self.cap = cv2.VideoCapture(0)
        
        self.label = Label(root)
        self.label.pack()
        
        self.emotion_label = Label(root, text="Emoción: Neutral", 
                                   font=("Arial", 20))
        self.emotion_label.pack()
        
        self.running = True
        self.thread = threading.Thread(target=self.update_frame)
        self.thread.daemon = True
        self.thread.start()
    
    def update_frame(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                expression, _ = self.detector.process_frame(frame)
                
                # Convertir para mostrar en tkinter
                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = cv2.resize(image, (640, 480))
                
                # Aquí irían más operaciones...
                self.emotion_label.config(text=f"Emoción: {expression}")

root = tk.Tk()
app = AppGUI(root)
root.mainloop()
"""


# ============================================================================
# Consejos Útiles
# ============================================================================

"""
1. PERSONALIZAR DETECCIÓN:
   - Modificar los umbrales en los métodos detect_smile(), detect_surprise(), etc.
   - Ajustar config.json para sensibilidad

2. OPTIMIZACIÓN:
   - Procesar cada Nth frame para mejorar rendimiento
   - Usar GPU si está disponible

3. DEBUGGING:
   - Usa show_landmarks=True para ver puntos de referencia
   - Imprime detector.emotion_history para ver el histórico

4. SEGURIDAD:
   - El procesamiento es LOCAL, no se envía nada a internet
   - Puedes revisar el código fuente

5. PERFORMANCE:
   - Reduce la resolución de entrada si es muy lenta
   - Aumenta smooth_emotion_history para más estabilidad
"""
