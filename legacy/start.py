#!/usr/bin/env python3
"""
Launcher - Ejecutor Simple
Solo ejecuta el detector con un comando
"""

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    project_dir = Path(__file__).parent
    detector_script = project_dir / "face_expression_detector.py"
    
    if not detector_script.exists():
        print("❌ Error: No se encontró face_expression_detector.py")
        sys.exit(1)
    
    print("🎭 Iniciando Detector de Expresiones Faciales...")
    print("Presiona 'q' para salir\n")
    
    try:
        subprocess.run([sys.executable, str(detector_script)], 
                      cwd=str(project_dir))
    except KeyboardInterrupt:
        print("\n👋 ¡Hasta luego!")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
