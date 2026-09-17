"""
Versión Mejorada - Detector de Expresiones Faciales Avanzado
Incluye estadísticas, grabación y características adicionales
"""

import cv2
import mediapipe as mp
import numpy as np
from pathlib import Path
import json
from collections import deque
from datetime import datetime
import csv

# Configuración de MediaPipe
mp_face_mesh = mp.solutions.face_mesh

class AdvancedExpressionDetector:
    def __init__(self, config_path='config.json', record_stats=False):
        """Inicializa el detector avanzado con estadísticas"""
        self.load_config(config_path)
        self.face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=self.config.get('min_detection_confidence', 0.5),
            min_tracking_confidence=self.config.get('min_tracking_confidence', 0.5)
        )
        self.emotion_history = deque(maxlen=self.config.get('smooth_emotion_history', 5))
        self.current_emotion = "neutral"
        self.frame_count = 0
        self.start_time = datetime.now()
        
        # Estadísticas
        self.emotion_stats = {expr: 0 for expr in ['smile', 'surprised', 'neutral']}
        self.record_stats = record_stats
        self.stats_file = 'emotion_stats.csv' if record_stats else None
        
        if record_stats:
            self._init_stats_file()
    
    def load_config(self, config_path):
        """Carga la configuración"""
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {
                "image_dir": "images",
                "display_width": 1200,
                "display_height": 700,
                "min_detection_confidence": 0.5,
                "min_tracking_confidence": 0.5,
                "smooth_emotion_history": 5
            }
    
    def _init_stats_file(self):
        """Inicializa el archivo de estadísticas"""
        with open(self.stats_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'frame', 'emotion', 'elapsed_seconds'])
    
    def _record_emotion(self):
        """Registra la emoción detectada"""
        if self.record_stats and self.frame_count % 5 == 0:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            with open(self.stats_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    self.frame_count,
                    self.current_emotion,
                    f"{elapsed:.2f}"
                ])
    
    def calculate_distance(self, point1, point2):
        """Calcula distancia entre dos puntos"""
        return np.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)
    
    def detect_smile(self, landmarks):
        """Detecta sonrisa"""
        left_mouth = np.array([landmarks[61].x, landmarks[61].y])
        right_mouth = np.array([landmarks[291].x, landmarks[291].y])
        top_mouth = np.array([landmarks[13].x, landmarks[13].y])
        bottom_mouth = np.array([landmarks[14].x, landmarks[14].y])
        
        mouth_width = self.calculate_distance(left_mouth, right_mouth)
        mouth_height = self.calculate_distance(top_mouth, bottom_mouth)
        
        smile_ratio = mouth_width / (mouth_height + 0.001)
        return smile_ratio > 3.0
    
    def detect_surprise(self, landmarks):
        """Detecta sorpresa"""
        left_eye_top = np.array([landmarks[159].x, landmarks[159].y])
        left_eye_bottom = np.array([landmarks[145].x, landmarks[145].y])
        eye_height = self.calculate_distance(left_eye_top, left_eye_bottom)
        
        right_eye_top = np.array([landmarks[386].x, landmarks[386].y])
        right_eye_bottom = np.array([landmarks[374].x, landmarks[374].y])
        right_eye_height = self.calculate_distance(right_eye_top, right_eye_bottom)
        
        top_mouth = np.array([landmarks[13].x, landmarks[13].y])
        bottom_mouth = np.array([landmarks[14].x, landmarks[14].y])
        mouth_opening = self.calculate_distance(top_mouth, bottom_mouth)
        
        # Más sensible: boca abierta O ambos ojos abiertos
        # Reducir umbrales para ser más flexible
        boca_abierta = mouth_opening > 0.035
        ojos_abiertos = (eye_height > 0.028) or (right_eye_height > 0.028)
        
        return boca_abierta or ojos_abiertos
    
    def recognize_expression(self, landmarks):
        """Reconoce la expresión"""
        if landmarks is None:
            return "neutral"
        
        expressions = {
            "smile": self.detect_smile(landmarks),
            "surprised": self.detect_surprise(landmarks),
        }
        
        for expr, detected in expressions.items():
            if detected:
                return expr
        
        return "neutral"
    
    def load_expression_image(self, expression):
        """Carga la imagen de la expresión"""
        image_dir = Path(self.config.get('image_dir', 'images'))
        image_path = image_dir / f"{expression}.png"
        
        if image_path.exists():
            image = cv2.imread(str(image_path))
            if image is not None:
                height = self.config.get('display_height', 700)
                width = self.config.get('display_width', 1200)
                image = cv2.resize(image, (width, height))
                return image
        
        return None
    
    def create_blank_image(self, expression):
        """Crea imagen en blanco"""
        height = self.config.get('display_height', 700)
        width = self.config.get('display_width', 1200)
        image = np.ones((height, width, 3), dtype=np.uint8) * 240
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        text = expression.upper()
        font_scale = 2
        thickness = 3
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        
        x = (width - text_size[0]) // 2
        y = (height + text_size[1]) // 2
        
        cv2.putText(image, text, (x, y), font, font_scale, (0, 0, 0), thickness)
        return image
    
    def draw_stats_panel(self, image):
        """Dibuja panel de estadísticas"""
        panel_height = 120
        panel = np.ones((panel_height, image.shape[1], 3), dtype=np.uint8) * 230
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        y_offset = 25
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        cv2.putText(panel, f"Frames: {self.frame_count} | Tiempo: {elapsed:.1f}s", 
                   (10, y_offset), font, 0.6, (0, 0, 0), 1)
        
        y_offset += 30
        stats_text = " | ".join([f"{k}: {v}" for k, v in self.emotion_stats.items()])
        cv2.putText(panel, stats_text, (10, y_offset), font, 0.5, (0, 0, 0), 1)
        
        y_offset += 30
        most_common = max(self.emotion_stats, key=self.emotion_stats.get)
        cv2.putText(panel, f"Más frecuente: {most_common}", 
                   (10, y_offset), font, 0.6, (0, 100, 200), 2)
        
        return panel
    
    def process_frame(self, frame):
        """Procesa un frame"""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_frame)
        
        if results.multi_face_landmarks and len(results.multi_face_landmarks) > 0:
            landmarks = results.multi_face_landmarks[0].landmark
            expression = self.recognize_expression(landmarks)
            self.emotion_history.append(expression)
            
            if self.emotion_history:
                self.current_emotion = max(set(self.emotion_history), 
                                          key=self.emotion_history.count)
        
        self.emotion_stats[self.current_emotion] += 1
        self._record_emotion()
        self.frame_count += 1
        
        return self.current_emotion, results
    
    def run(self, show_stats=True):
        """Ejecuta el detector"""
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            print("❌ No se pudo abrir la cámara web")
            return
        
        print("✅ Cámara abierta. Presiona 'q' para salir, 's' para guardar captura")
        if self.record_stats:
            print(f"📊 Registrando estadísticas en {self.stats_file}")
        
        display_width = self.config.get('display_width', 1200)
        display_height = self.config.get('display_height', 700)
        
        capture_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame = cv2.resize(frame, (640, 480))
            expression, results = self.process_frame(frame)
            
            expression_image = self.load_expression_image(expression)
            if expression_image is None:
                expression_image = self.create_blank_image(expression)
            
            # Agregar panel de estadísticas si está habilitado
            if show_stats:
                stats_panel = self.draw_stats_panel(expression_image)
                expression_image = np.vstack([stats_panel, expression_image[120:]])
            
            # Miniatura de cámara
            cam_frame = cv2.resize(frame, (320, 240))
            cv2.rectangle(cam_frame, (0, 0), (320, 240), (0, 255, 0), 2)
            
            expression_image[0:240, display_width-320:display_width] = cam_frame
            
            # Texto
            font = cv2.FONT_HERSHEY_SIMPLEX
            text = f"Expresion: {expression.upper()}"
            cv2.putText(expression_image, text, (20, 30), font, 0.7, (0, 0, 0), 2)
            
            cv2.imshow('Detector Avanzado', expression_image)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("👋 Saliendo...")
                break
            elif key == ord('s'):
                filename = f"captura_{capture_count}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                cv2.imwrite(filename, expression_image)
                print(f"📸 Captura guardada como {filename}")
                capture_count += 1
        
        cap.release()
        cv2.destroyAllWindows()
        
        # Mostrar estadísticas finales
        if self.record_stats:
            print("\n📊 Estadísticas Finales:")
            for emotion, count in self.emotion_stats.items():
                percentage = (count / self.frame_count * 100) if self.frame_count > 0 else 0
                print(f"  {emotion.capitalize()}: {count} frames ({percentage:.1f}%)")
            
            print(f"\n✅ Estadísticas guardadas en: {self.stats_file}")


if __name__ == "__main__":
    # Usa record_stats=True para grabar estadísticas en CSV
    detector = AdvancedExpressionDetector('config.json', record_stats=True)
    detector.run(show_stats=True)
