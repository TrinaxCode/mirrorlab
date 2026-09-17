"""
Detector de Expresiones Faciales con OpenCV
Detecta: sonrisa, sorpresa, lengua, paz, neutral
"""

import cv2
import numpy as np
from pathlib import Path
import json
from collections import deque

class ExpressionDetector:
    def __init__(self, config_path='config.json'):
        """Inicializa el detector de expresiones"""
        self.load_config(config_path)
        
        # Cargar cascadas de OpenCV
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_eye.xml'
        )
        self.smile_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_smile.xml'
        )
        
        self.emotion_history = deque(maxlen=5)
        self.current_emotion = "neutral"
        
    def load_config(self, config_path):
        """Carga la configuración"""
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {
                "image_dir": "images",
                "display_width": 1200,
                "display_height": 700
            }
    
    def detect_tongue(self, roi_gray, roi_color):
        """Detecta si la lengua está sacada"""
        try:
            height, width = roi_gray.shape
            mouth_region = roi_gray[int(height*0.6):, :]
            _, thresh = cv2.threshold(mouth_region, 50, 255, cv2.THRESH_BINARY_INV)
            contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            if len(contours) > 0:
                largest_contour = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(largest_contour)
                if area > 800:
                    return True
        except:
            pass
        return False
    
    def detect_hands_peace(self, frame):
        """Detecta gesto de paz (manos en V)"""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            hand_count = 0
            for contour in contours:
                area = cv2.contourArea(contour)
                if 1000 < area < 50000:
                    hand_count += 1
            if hand_count >= 2:
                return True
        except:
            pass
        return False
    
    def detect_expression(self, frame, faces):
        """Detecta expresión basada en características"""
        if len(faces) == 0:
            return "neutral"
        
        (x, y, w, h) = faces[0]
        roi_color = frame[y:y+h, x:x+w]
        roi_gray = cv2.cvtColor(roi_color, cv2.COLOR_BGR2GRAY)
        
        smiles = self.smile_cascade.detectMultiScale(roi_gray, 1.8, 20, minSize=(25, 25))
        eyes = self.eye_cascade.detectMultiScale(roi_gray, 1.1, 10, minSize=(15, 15))
        
        # Detectar lengua
        if self.detect_tongue(roi_gray, roi_color):
            return "tongue"
        
        if len(smiles) > 0:
            return "smile"
        
        if len(eyes) > 2:
            return "surprised"
        
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
    
    def run(self):
        """Ejecuta el detector"""
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            print("❌ No se pudo abrir la cámara web")
            return
        
        print("✅ Cámara abierta")
        print("Expresiones disponibles:")
        print("  😊 Sonrisa → smile.png")
        print("  😲 Sorpresa → surprised.png")
        print("  👅 Lengua → tongue.png")
        print("  ✌  Paz (manos) → peace.png")
        print("  😐 Neutral → neutral.png")
        print("\nPresiona 'q' para salir, 's' para captura\n")
        
        display_width = self.config.get('display_width', 1200)
        display_height = self.config.get('display_height', 700)
        
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame = cv2.resize(frame, (640, 480))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detectar caras
            faces = self.face_cascade.detectMultiScale(
                gray, 1.3, 5, minSize=(30, 30)
            )
            
            # Detectar expresión facial
            expression = self.detect_expression(frame, faces)
            
            # Detectar gesto de paz
            if self.detect_hands_peace(frame) and expression == "neutral":
                expression = "peace"
            
            self.emotion_history.append(expression)
            
            if self.emotion_history:
                self.current_emotion = max(set(self.emotion_history), 
                                          key=self.emotion_history.count)
            
            # Cargar imagen
            expression_image = self.load_expression_image(self.current_emotion)
            if expression_image is None:
                expression_image = self.create_blank_image(self.current_emotion)
            
            # Miniatura de cámara
            cam_frame = cv2.resize(frame, (320, 240))
            cv2.rectangle(cam_frame, (0, 0), (320, 240), (0, 255, 0), 2)
            expression_image[0:240, display_width-320:display_width] = cam_frame
            
            # Información
            font = cv2.FONT_HERSHEY_SIMPLEX
            text = f"Expresion: {self.current_emotion.upper()}"
            cv2.putText(expression_image, text, (20, 30), font, 0.7, (0, 0, 0), 2)
            cv2.putText(expression_image, f"Caras: {len(faces)}", (20, 60), font, 0.5, (100, 100, 100), 1)
            
            cv2.imshow('Detector de Expresiones Faciales', expression_image)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("👋 Saliendo...")
                break
            elif key == ord('s'):
                filename = f"captura_{frame_count}.png"
                cv2.imwrite(filename, expression_image)
                print(f"📸 Captura guardada: {filename}")
                frame_count += 1
        
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    detector = ExpressionDetector('config.json')
    detector.run()
