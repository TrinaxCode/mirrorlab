#!/usr/bin/env python3
"""
Script de prueba para verificar que todo funciona correctamente
"""

import sys
import subprocess
from pathlib import Path

def test_environment():
    """Prueba el entorno de ejecución"""
    print("🔍 Verificando entorno...")
    
    try:
        import cv2
        print(f"✅ OpenCV: {cv2.__version__}")
    except ImportError:
        print("❌ OpenCV no instalado")
        return False
    
    try:
        import mediapipe
        print(f"✅ MediaPipe: {mediapipe.__version__}")
    except ImportError:
        print("❌ MediaPipe no instalado")
        return False
    
    try:
        import numpy
        print(f"✅ NumPy: {numpy.__version__}")
    except ImportError:
        print("❌ NumPy no instalado")
        return False
    
    return True

def test_images():
    """Prueba que las imágenes existan"""
    print("\n📁 Verificando imágenes...")
    
    images_dir = Path("images")
    if not images_dir.exists():
        print("❌ Carpeta 'images' no existe")
        return False
    
    required_images = ["smile.png", "surprised.png", "sad.png", "angry.png", "neutral.png"]
    all_exist = True
    
    for img in required_images:
        img_path = images_dir / img
        if img_path.exists():
            size_mb = img_path.stat().st_size / (1024 * 1024)
            print(f"✅ {img} ({size_mb:.2f} MB)")
        else:
            print(f"⚠️  {img} no encontrado")
            all_exist = False
    
    return all_exist

def test_camera():
    """Prueba que la cámara funcione"""
    print("\n🎥 Verificando cámara...")
    
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret:
                print("✅ Cámara funcionando")
                return True
            else:
                print("❌ No se puede capturar desde la cámara")
                return False
        else:
            print("❌ Cámara no accesible (verifica permisos)")
            return False
    except Exception as e:
        print(f"❌ Error al probar la cámara: {e}")
        return False

def main():
    print("🎭 Detector de Expresiones Faciales - Pruebas")
    print("=" * 50)
    
    env_ok = test_environment()
    images_ok = test_images()
    camera_ok = test_camera()
    
    print("\n" + "=" * 50)
    print("📊 Resumen:")
    print(f"  Entorno: {'✅ OK' if env_ok else '❌ FALLA'}")
    print(f"  Imágenes: {'✅ OK' if images_ok else '⚠️ INCOMPLETO'}")
    print(f"  Cámara: {'✅ OK' if camera_ok else '❌ NO DISPONIBLE'}")
    
    if env_ok and camera_ok:
        print("\n✅ ¡Listo para ejecutar!")
        print("\nEjecuta: python face_expression_detector.py")
    else:
        print("\n❌ Hay problemas que deben resolverse primero")
        if not env_ok:
            print("\n   Instala las dependencias:")
            print("   pip install opencv-python mediapipe numpy")
        if not camera_ok:
            print("\n   Verifica que:")
            print("   - Tu webcam esté conectada")
            print("   - Tengas permisos para acceder a la cámara")

if __name__ == "__main__":
    main()
