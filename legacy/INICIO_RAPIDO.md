# 🚀 Guía Rápida de Inicio

## ⚡ 3 pasos para empezar:

### 1️⃣ Verifica tu instalación
```bash
cd "Web Cam Proyect"
python test_setup.py
```

### 2️⃣ Ejecuta el programa
```bash
python face_expression_detector.py
```

O simplemente:
```bash
python start.py
```

### 3️⃣ ¡Haz expresiones!
- 😊 **Sonríe** → Aparece `smile.png`
- 😲 **Abre los ojos y la boca** → Aparece `surprised.png`
- 😢 **Frunce el ceño** → Aparece `sad.png`
- 😠 **Frunce mucho el ceño** → Aparece `angry.png`
- 😐 **Expresión normal** → Aparece `neutral.png`

---

## 🎮 Controles en Tiempo Real

| Tecla | Acción |
|-------|--------|
| `q` | Salir |
| `s` | Guardar captura |

---

## 📁 Archivos Principales

```
├── face_expression_detector.py    ← PROGRAMA PRINCIPAL
├── config.json                    ← CONFIGURACIÓN
├── images/                        ← TUS IMÁGENES
│   ├── smile.png
│   ├── surprised.png
│   ├── sad.png
│   ├── angry.png
│   └── neutral.png
└── README.md                      ← DOCUMENTACIÓN COMPLETA
```

---

## 🎨 Personalizar Imágenes

Simplemente **reemplaza las imágenes PNG** en la carpeta `images/` con las tuyas propias.

**Requisitos:**
- Formato: PNG
- Tamaño: 1200x700 píxeles (puedes usar cualquier tamaño, se redimensionará)
- Nombres exactos:
  - `smile.png`
  - `surprised.png`
  - `sad.png`
  - `angry.png`
  - `neutral.png`

---

## ⚙️ Configuración Básica

Edita `config.json`:

```json
{
  "display_width": 1200,            // Ancho de la pantalla
  "display_height": 700,            // Alto de la pantalla
  "min_detection_confidence": 0.5   // Sensibilidad (0.0-1.0)
}
```

---

## ✅ Checklist de Solución de Problemas

- [ ] ¿Tu webcam está conectada?
- [ ] ¿Tienes iluminación decente?
- [ ] ¿Las imágenes están en la carpeta `images/`?
- [ ] ¿Los nombres de las imágenes son exactos (con puntos)?
- [ ] ¿Ejecutaste `python test_setup.py` sin errores?

---

## 📖 Para Más Información

Lee el [README.md](README.md) para documentación completa.

Lee [TIPS_Y_TRUCOS.md](TIPS_Y_TRUCOS.md) para configuración avanzada.

---

## 💻 Requisitos Mínimos

- Python 3.7+
- Webcam
- 200 MB de espacio en disco
- Conexión a internet (primera ejecución)

---

**¿Problemas?** Revisa el README.md para solucionar errores comunes.

**¿Quieres mejorar?** Mira TIPS_Y_TRUCOS.md para ideas avanzadas.

¡Diviértete! 🎉
