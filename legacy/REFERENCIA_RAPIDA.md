# 📋 Tarjeta de Referencia Rápida

## ⚡ Comandos Rápidos

### Para Empezar
```bash
# Verificar que todo funcione
python test_setup.py

# Ejecutar el detector
python face_expression_detector.py

# Versión con estadísticas
python advanced_detector.py
```

### Para Personalizar
```bash
# Generar imágenes de ejemplo (si no existen)
python generate_example_images.py

# Editar configuración
nano config.json  # o usa tu editor favorito

# Agregar tus propias imágenes
# 1. Prepara PNGs de 1200x700 px
# 2. Nombra: smile.png, surprised.png, sad.png, angry.png, neutral.png
# 3. Copia a: images/
```

---

## 🎮 Teclas de Control

| Tecla | Función |
|-------|---------|
| `q` | Salir |
| `s` | Captura de pantalla |

---

## 🎭 Expresiones Detectadas

| Expresión | Cómo Activar |
|-----------|-------------|
| 😊 **SMILE** | Sonríe claramente |
| 😲 **SURPRISED** | Abre ojos y boca grande |
| 😢 **SAD** | Frunce cejas, baja comisuras |
| 😠 **ANGRY** | Frunce cejas fuerte, ojos cerrados |
| 😐 **NEUTRAL** | Expresión normal |

---

## 📁 Archivos Principales

```
face_expression_detector.py    ← Programa principal (COMIENZA AQUÍ)
advanced_detector.py           ← Versión con estadísticas
config.json                    ← Personalización (ancho, alto, sensibilidad)
images/                        ← Tus imágenes personalizadas
```

---

## ⚙️ Configuración Rápida

### config.json

```json
{
  "display_width": 1200,              // Ancho pantalla
  "display_height": 700,              // Alto pantalla
  "min_detection_confidence": 0.5,    // Sensibilidad (0-1)
  "min_tracking_confidence": 0.5      // Estabilidad (0-1)
}
```

**Sensibilidad más alta** → `0.3` (detecta más)  
**Sensibilidad más baja** → `0.8` (detecta menos)

---

## 🖼️ Imágenes Requeridas

Coloca en carpeta `images/`:
- `smile.png` (1200x700)
- `surprised.png` (1200x700)
- `sad.png` (1200x700)
- `angry.png` (1200x700)
- `neutral.png` (1200x700)

---

## 📊 Archivos Generados

Al ejecutar se crean:
- `captura_0.png` (cuando presionas `s`)
- `captura_1.png`
- `emotion_stats.csv` (solo con `advanced_detector.py`)

---

## 🐛 Si No Funciona

1. **Cámara no abre:**
   ```bash
   python test_setup.py
   ```

2. **Imágenes no aparecen:**
   - Verifica carpeta `images/`
   - Comprueba nombres exactos
   - Confirma que sean PNG válidos

3. **Detección imprecisa:**
   - Mejor iluminación
   - Acércate más a cámara
   - Lee `TIPS_Y_TRUCOS.md`

---

## 📚 Documentación

| Documento | Lee si... |
|-----------|-----------|
| `README.md` | Quieres información completa |
| `INICIO_RAPIDO.md` | Necesitas empezar rápido |
| `TIPS_Y_TRUCOS.md` | Quieres configuración avanzada |
| `INDEX.md` | Necesitas encontrar algo |
| `EJEMPLOS_CODIGO.py` | Quieres integrar en código |
| `LICENSE_AND_CREDITS.md` | Información legal |

---

## 🎯 Programas Disponibles

### `face_expression_detector.py` ⭐ RECOMENDADO
- Simple, rápido, eficiente
- Ideal para comenzar
- Panel básico de información

### `advanced_detector.py`
- Versión mejorada
- Estadísticas en tiempo real
- Exporta datos a CSV
- Panel detallado

### `start.py`
- Launcher simple
- Solo ejecuta el detector

---

## 💻 Requisitos Mínimos

- Python 3.7+
- Webcam
- 200 MB espacio en disco
- 2 GB RAM

---

## 🚀 Instalación (Primera Vez)

```bash
# 1. Verifica Python
python --version

# 2. Las dependencias ya están instaladas
# (OpenCV, MediaPipe, NumPy)

# 3. Ejecuta
python face_expression_detector.py
```

---

## 📊 Versión Avanzada

```bash
python advanced_detector.py
```

Genera:
- 📈 Panel de estadísticas
- 📊 Gráfico de emociones
- 💾 Datos en CSV
- ⏱️ Temporizador
- 📈 Porcentajes

---

## 🎨 Personalizar Rápido

1. Prepara imágenes PNG (1200x700)
2. Nombres exactos: `smile.png`, etc.
3. Copia a carpeta `images/`
4. ¡Listo! Se usan automáticamente

---

## ⏱️ Atajos Útiles

```bash
# Ejecutar directamente
python face_expression_detector.py

# Con terminal mejorada
python start.py

# Ver opciones interactivas
./run.sh  # (en Linux/Mac)

# Generar ejemplos
python generate_example_images.py

# Verificar todo
python test_setup.py
```

---

## 🎯 Ideas Rápidas

- 📸 Haz capturas de tus expresiones
- 📊 Analiza tus emociones con `advanced_detector.py`
- 🎬 Transmite en vivo mostrando diferentes imágenes
- 👥 Múltiples personas en rondas
- 🎨 Personaliza con imágenes temáticas

---

## 🔍 Tips Rápidos

✅ Mejor iluminación = Mejor detección  
✅ Acércate a la cámara para precisión  
✅ Expresiones claras = Mejor reconocimiento  
✅ Fondo liso = Menos confusión  
✅ Usa `show_landmarks=True` para debug  

---

## 📞 Ayuda Rápida

- ❌ Problema técnico → `python test_setup.py`
- ❌ No sé cómo empezar → Lee `INICIO_RAPIDO.md`
- ❌ Quiero personalizar → Lee `TIPS_Y_TRUCOS.md`
- ❌ Necesito ejemplos de código → Ver `EJEMPLOS_CODIGO.py`
- ❌ Pregunta sobre archivo X → Ver `INDEX.md`

---

## 🎉 ¡Listo!

Tu detector de emociones está funcionando.  
Solo ejecuta y ¡diviértete! 🎭

```bash
python face_expression_detector.py
```

---

**Versión:** 1.0  
**Última actualización:** 2024  
**Estado:** ✅ Completo

---

**¡Que disfrutes! 🚀**
