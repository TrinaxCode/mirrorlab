# 📑 Índice Maestro del Proyecto

## 🎯 Descripción General

Este es un **Detector de Expresiones Faciales en Tiempo Real** que:
- Accede a tu webcam
- Detecta tu expresión facial (sonrisa, sorpresa, tristeza, enojo, neutral)
- Muestra imágenes personalizadas según la expresión

---

## 📂 Estructura de Archivos

### 🚀 Archivos Principales (Para Ejecutar)

| Archivo | Descripción | Cómo Usar |
|---------|-------------|----------|
| `face_expression_detector.py` | **PROGRAMA PRINCIPAL** - Detector estándar | `python face_expression_detector.py` |
| `advanced_detector.py` | Versión mejorada con estadísticas | `python advanced_detector.py` |
| `start.py` | Launcher simple | `python start.py` |

### ⚙️ Archivos de Configuración

| Archivo | Descripción |
|---------|-------------|
| `config.json` | Configuración principal (ancho, alto, sensibilidad) |
| `requirements.txt` | Dependencias Python necesarias |

### 📚 Archivos de Documentación

| Archivo | Contenido |
|---------|----------|
| `README.md` | Documentación completa del proyecto |
| `INICIO_RAPIDO.md` | Guía de 3 pasos para empezar |
| `TIPS_Y_TRUCOS.md` | Configuración avanzada e ideas creativas |
| `INDEX.md` | Este archivo |

### 🔧 Herramientas de Utilidad

| Archivo | Propósito |
|---------|----------|
| `generate_example_images.py` | Crea imágenes de ejemplo |
| `test_setup.py` | Verifica que todo esté instalado correctamente |
| `install_dependencies.sh` | Script de instalación automática |
| `run.sh` | Menú interactivo de opciones |

### 🖼️ Carpeta de Imágenes

| Carpeta | Contenido |
|---------|----------|
| `images/` | Imágenes PNG para cada expresión |
| ├─ `smile.png` | Se muestra cuando sonríes |
| ├─ `surprised.png` | Se muestra cuando tienes sorpresa |
| ├─ `sad.png` | Se muestra cuando estás triste |
| ├─ `angry.png` | Se muestra cuando estás enojado |
| └─ `neutral.png` | Se muestra en expresión neutral |

---

## 🎯 Flujo de Inicio Recomendado

### Para Principiantes
```
1. Lee: INICIO_RAPIDO.md
2. Ejecuta: python test_setup.py
3. Ejecuta: python face_expression_detector.py
```

### Para Usuarios Avanzados
```
1. Lee: TIPS_Y_TRUCOS.md
2. Personaliza: config.json
3. Crea: Tus propias imágenes en images/
4. Ejecuta: python advanced_detector.py
```

---

## 💡 Usos Comunes

### ✨ Caso de Uso 1: Diversión Básica
```bash
python face_expression_detector.py
```
- Simplemente diviértete viendo cómo cambian las imágenes
- Presiona `s` para capturar momentos

### 🎬 Caso de Uso 2: Transmisión en Vivo
```bash
python advanced_detector.py
# Comparte tu pantalla en Discord/Twitch/OBS
```
- Muestra el panel de estadísticas en tiempo real
- Registra tus emociones en CSV

### 📊 Caso de Uso 3: Análisis de Emociones
```python
from advanced_detector import AdvancedExpressionDetector
detector = AdvancedExpressionDetector(record_stats=True)
detector.run()
# Genera: emotion_stats.csv
```

### 🎨 Caso de Uso 4: Personalizado
1. Crea imágenes personalizadas (1200x700px PNG)
2. Colócalas en `images/` con nombres exactos
3. Edita `config.json` según necesites
4. Ejecuta: `python face_expression_detector.py`

---

## 🔍 Guía Rápida de Selección

### ¿Qué programa debo usar?

**`face_expression_detector.py`** → Versión estándar, simple y eficiente
- ✅ Perfecto para comenzar
- ✅ Interfaz limpia
- ✅ Bajo consumo de recursos

**`advanced_detector.py`** → Versión mejorada con estadísticas
- ✅ Panel de estadísticas en tiempo real
- ✅ Exporta datos a CSV
- ✅ Información detallada

**`start.py`** → Simple launcher
- ✅ Solo ejecuta face_expression_detector.py
- ✅ Ideal si quieres algo muy simple

---

## ⚙️ Configuración Rápida

### Cambiar Dimensiones de Pantalla
Edita `config.json`:
```json
{
  "display_width": 1920,    // Ancho
  "display_height": 1080    // Alto
}
```

### Aumentar/Disminuir Sensibilidad
```json
{
  "min_detection_confidence": 0.3,    // Más sensible (0.0-1.0)
  "smooth_emotion_history": 10        // Más suave
}
```

---

## 🎨 Personalizar Imágenes

### Paso 1: Preparar Imágenes
- Tamaño: 1200x700 píxeles
- Formato: PNG

### Paso 2: Nombrar Correctamente
```
smile.png
surprised.png
sad.png
angry.png
neutral.png
```

### Paso 3: Guardar en Carpeta
```
images/
├─ smile.png
├─ surprised.png
├─ sad.png
├─ angry.png
└─ neutral.png
```

### Paso 4: Ejecutar
```bash
python face_expression_detector.py
```

---

## 🚨 Solución de Problemas

### ❌ "La cámara no se abre"
```bash
python test_setup.py
# Verifica la sección de cámara
```

### ❌ "Las imágenes no aparecen"
1. Verifica que existan en `images/`
2. Confirma que los nombres sean exactos
3. Verifica que sean archivos PNG válidos

### ❌ "Detección imprecisa"
- Mejora la iluminación
- Acércate más a la cámara
- Lee: TIPS_Y_TRUCOS.md

---

## 📊 Archivos Generados

Durante la ejecución, se crean:

| Archivo | Descripción |
|---------|-------------|
| `captura_0.png` | Capturas de pantalla (presiona `s`) |
| `emotion_stats.csv` | Estadísticas (solo con advanced_detector) |

---

## 📚 Documentación Detallada

Para información específica, consulta:

- **Empezar rápido** → [INICIO_RAPIDO.md](INICIO_RAPIDO.md)
- **Uso completo** → [README.md](README.md)
- **Configuración avanzada** → [TIPS_Y_TRUCOS.md](TIPS_Y_TRUCOS.md)

---

## 🔐 Requisitos

- ✅ Python 3.7+
- ✅ Webcam funcional
- ✅ 200 MB de espacio en disco
- ✅ Conexión a internet (primera vez)

---

## 📊 Versiones de Archivos

| Programa | Funciones |
|----------|-----------|
| `face_expression_detector.py` | Básico, estándar, rápido |
| `advanced_detector.py` | +Estadísticas, +Panel info, +CSV |

---

## 🎯 Próximos Pasos

1. ✅ Lee [INICIO_RAPIDO.md](INICIO_RAPIDO.md)
2. ✅ Ejecuta `python test_setup.py`
3. ✅ Corre `python face_expression_detector.py`
4. ✅ Personaliza tus imágenes
5. ✅ ¡Diviértete! 🎉

---

## 🆘 Ayuda

- ¿Preguntas sobre instalación? → Ver [README.md](README.md)
- ¿Configuración avanzada? → Ver [TIPS_Y_TRUCOS.md](TIPS_Y_TRUCOS.md)
- ¿Empezar rápido? → Ver [INICIO_RAPIDO.md](INICIO_RAPIDO.md)
- ¿Problemas técnicos? → Ejecuta `python test_setup.py`

---

**Versión:** 1.0  
**Última actualización:** 2024  
**Estado:** ✅ Listo para usar
