# MirrorLab — filtros en tiempo real para tu webcam, expresiones faciales y gestos con una sola orden, sin GPU

Convierte tu webcam en un laboratorio de visión artificial: 54 filtros de vídeo, 18 expresiones faciales leídas de 52 canales de coeficientes de expresión, 22 gestos de la mano y 15 efectos AR — solo CPU y todo local.

[English](README.md) | [Español](README.es.md)

[![Licencia: MIT](https://img.shields.io/badge/license-MIT-3da639?style=flat-square)](LICENSE)
[![Python 3.9–3.12](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-3776ab?style=flat-square)](pyproject.toml)
[![Plataformas: macOS, Windows, Linux](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-4c4c4c?style=flat-square)](#instalación)
[![Solo CPU](https://img.shields.io/badge/CPU-only-8957e5?style=flat-square)](#rendimiento)
[![Demo en vivo](https://img.shields.io/badge/demo-live-ff4b4b?style=flat-square)](https://mirrorlab-demo.vercel.app)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)](CONTRIBUTING.md)
[![GitHub](https://img.shields.io/badge/GitHub-TrinaxCode%2Fmirrorlab-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/TrinaxCode/mirrorlab)

---

## Demo

<!-- TODO: replace with assets/demo.gif after recording the hero GIF -->

*El GIF principal debería ser una toma continua sin cortes: una cara neutra, luego una sonrisa que enciende la etiqueta de expresión, un signo de victoria que cambia el filtro a `cartoon`, un deslizamiento que cambia el preset y un pulgar arriba que dispara una captura — con el anillo de confirmación llenándose antes de que se ejecute la acción. Grábalo con `mirrorlab run --filter cartoon`, pulsa `r`, haz la secuencia, vuelve a pulsar `r` y tendrás el MP4 y el GIF en `captures/`.*

También hay una **demo en el navegador** que no requiere instalar nada: **[mirrorlab-demo.vercel.app](https://mirrorlab-demo.vercel.app)**. Ejecuta los modelos de visión dentro de tu navegador con WebAssembly y WebGL. Tu cámara nunca sale de la página.

---

## Por qué existe esto

Las demos de visión artificial con webcam suelen caer en uno de dos extremos: un script de 200 líneas que detecta una cosa y la detecta mal, o un repositorio de investigación que necesita una GPU y un entorno conda. MirrorLab es el punto medio que faltaba: un paquete de verdad, instalable con `pip`, que lee caras y manos como es debido y que sigue funcionando cuando falta un modelo o un runtime.

También existe para resolver un problema concreto de 2025: **MediaPipe 1.0 eliminó `mp.solutions`** y **la 1.0.1 aborta dentro del helper Metal de Apple en algunas compilaciones de macOS**. MirrorLab sondea qué funciona realmente en tu máquina y degrada funciones en lugar de romperse. Mira [la instalación verificada](#instalación-verificada).

## Lo que trae

- **54 filtros de vídeo** — encadenables, por categorías, medidos, con 10 presets seleccionados
- **22 gestos de la mano** — 21 poses estáticas con reglas geométricas explicables más deslizamientos, un saludo y un círculo
- **18 expresiones faciales** — leídas de los 52 canales de coeficientes de expresión (blendshapes) de MediaPipe, no de proporciones entre puntos
- **15 efectos AR** — 11 superposiciones faciales ancladas a la línea de los ojos, 4 efectos de mano, todos dibujados por procedimiento
- **5 backends de detección** — una escalera de respaldo para que la app degrade en lugar de no arrancar
- **Solo CPU** — sin GPU, sin CUDA, sin matriz de drivers; 720p a 30 fps en un portátil moderno
- **Graba MP4 + GIF** — una tecla, además de capturas, un CSV de estadísticas y un resumen de sesión
- **Demo en el navegador** — las mismas ideas de percepción, ejecutándose en el cliente en [mirrorlab-demo.vercel.app](https://mirrorlab-demo.vercel.app)
- **100 % local** — los fotogramas de la cámara nunca salen de tu máquina; el único acceso a la red es la descarga inicial de modelos

---

## Instalación

### Desde el código fuente (la vía principal, funciona hoy)

```bash
git clone https://github.com/TrinaxCode/mirrorlab.git
cd mirrorlab

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
mirrorlab run
```

Eso es toda la instalación. El primer `mirrorlab run` descarga unos 12 MB de modelos en una caché de usuario y abre la vista previa.

¿Prefieres `make`? `make install` crea el entorno virtual e instala los extras de desarrollo, y `make run` arranca la app.

### Desde PyPI (próximamente)

```bash
pip install mirrorlab
mirrorlab run
```

> **Todavía no está publicado.** MirrorLab no está en PyPI. Usa la instalación desde el código fuente de arriba. La publicación en PyPI está en [ROADMAP.md](ROADMAP.md).

### Instalación verificada

> **Fija estas versiones si te topas con un problema de MediaPipe.** MediaPipe 1.0 eliminó `mp.solutions`, y MediaPipe 1.0.1 **se cae en seco en algunas compilaciones de macOS** dentro del helper Metal de Apple (`DrishtiMetalHelper ... Check failed: service_ Service is unavailable`). Esta combinación está probada y funciona:
>
> ```bash
> pip install "mediapipe>=0.10.9,<0.11" "numpy<2" "opencv-python<5"
> ```
>
> `numpy<2` es obligatorio porque MediaPipe 0.10.x se compiló contra la ABI de C de NumPy 1.x. La explicación completa está en [docs/CROSS_PLATFORM.md](docs/CROSS_PLATFORM.md#the-dependency-pins).

Comprueba el resultado antes de ejecutar nada:

```bash
mirrorlab doctor
```

Imprime tus versiones de Python, OpenCV y MediaPipe, qué backends de detección se inicializaron, qué modelos están en caché y la línea exacta de `pip install` para arreglar un MediaPipe ausente.

### Notas por sistema operativo

<details>
<summary><b>macOS</b></summary>

- Tu terminal necesita permiso de cámara: **Ajustes del Sistema → Privacidad y seguridad → Cámara** → activa Terminal / iTerm2 / VS Code.
- El permiso se concede **por aplicación anfitriona**, no por intérprete de Python: dárselo a Terminal no sirve para un script lanzado desde un IDE.
- La primera ejecución lanza el diálogo del sistema. Acéptalo y vuelve a ejecutar; macOS no concede el acceso a mitad de proceso.
- Un iPhone con Continuity Camera puede ocupar el índice 0. Si se abre la cámara equivocada: `mirrorlab run --camera 1`.
- La ventana necesita unas cuantas iteraciones del bucle de eventos para cerrarse. MirrorLab las hace por ti; mira [las preguntas frecuentes](docs/FAQ.md#why-does-the-window-not-close-on-macos).

</details>

<details>
<summary><b>Windows</b></summary>

- **Configuración → Privacidad → Cámara** → *Permitir que las aplicaciones de escritorio accedan a la cámara*.
- Si la vista previa sale negra o el dispositivo no se abre, cambia el backend de captura:
  ```powershell
  mirrorlab run --backend dshow     # DirectShow
  mirrorlab run --backend msmf      # Media Foundation
  ```
  DSHOW informa alegremente de un dispositivo abierto que nunca entrega píxeles, así que MirrorLab lee un fotograma como prueba de aceptación — pero cuando un driver se porta mal, el otro backend suele funcionar.
- Usa `py -3.11 -m venv .venv` si `python3` no está en tu PATH.

</details>

<details>
<summary><b>Linux</b></summary>

```bash
sudo usermod -aG video "$USER"     # después cierra sesión y vuelve a entrar: los grupos se leen al iniciar sesión
ls -l /dev/video*                  # el nodo de dispositivo tiene que existir
mirrorlab run
```

- En Docker o WSL2 tienes que pasar el dispositivo: `--device /dev/video0` (Docker) o `usbipd attach` (WSL2). Mira [docs/CROSS_PLATFORM.md](docs/CROSS_PLATFORM.md#docker).
- En un servidor sin pantalla, instala `opencv-python-headless` y usa `mirrorlab run --headless`.

</details>

---

## Uso

### Órdenes habituales

```bash
mirrorlab                                  # ejecuta con los valores por defecto (igual que `mirrorlab run`)
mirrorlab run --filter cartoon+vignette    # encadena filtros con `+`
mirrorlab run --preset noir                # un aspecto curado de varios filtros
mirrorlab run --effect sunglasses --effect fire
mirrorlab run --no-hands                   # más rápido: sin seguimiento de manos
mirrorlab run --segment                    # activa la máscara de persona (desenfoque/fondo)

mirrorlab filters                          # lista los 54 filtros por categoría
mirrorlab filters --category artistic      # una sola categoría
mirrorlab filters --presets                # los 10 presets seleccionados
mirrorlab gestures                         # cada gesto y su acción asociada
mirrorlab expressions                      # cada expresión detectable
mirrorlab effects                          # cada efecto AR

mirrorlab doctor                           # ¿está lista esta máquina?
mirrorlab cameras --max-index 5            # qué índices y backends entregan fotogramas
mirrorlab models --status                  # qué hay en la caché de modelos
mirrorlab models --download                 # descarga los modelos que falten
mirrorlab benchmark --all --frames 30      # ms/fotograma de los 54 filtros
mirrorlab config --list                    # cada clave de configuración y su valor por defecto
mirrorlab config --init mirrorlab.json     # escribe un archivo de configuración editable
mirrorlab gallery --output assets/filter-gallery.png   # hoja de contacto de todos los filtros
mirrorlab demo --frames 120                # sin cámara, con fuente sintética
```

`mirrorlab` sin argumentos es `mirrorlab run`. Todos los subcomandos aceptan `--help` y casi todos aceptan `--json` para salida legible por máquinas — que es lo que consume el generador de catálogos de la web.

### Configuración

La configuración se resuelve en cuatro capas, de menor a mayor prioridad: valores por defecto → archivo de configuración (`mirrorlab.json` / `mirrorlab.yaml`, que se busca en el directorio actual o en `~/.config/mirrorlab`) → variables de entorno `MIRRORLAB_*` → flags de la línea de órdenes. Una clave desconocida es un error con un puntero a `mirrorlab config --list`, así que una errata nunca se ignora en silencio.

```bash
MIRRORLAB_FILTER="cartoon+vignette" MIRRORLAB_THEME=magma mirrorlab run
MIRRORLAB_SMOOTHING_MIN_CUTOFF=1.0 mirrorlab run      # puntos de referencia más estables
```

Todas las claves, con su tipo y su valor por defecto:

#### Cámara

| Clave | Tipo | Por defecto | Descripción |
| --- | --- | --- | --- |
| `camera_index` | int | `0` | Índice del dispositivo de cámara (`--camera`, `-c`) |
| `camera_width` | int | `1280` | Ancho de captura solicitado (`--camera-width`); bájalo para ganar velocidad |
| `camera_height` | int | `720` | Alto de captura solicitado (`--camera-height`) |
| `camera_fps` | int | `30` | Frecuencia de captura solicitada, de 1 a 240 (`--camera-fps`) |
| `camera_backend` | str | `"auto"` | `auto`, `avfoundation`, `dshow`, `msmf`, `v4l2` o `any` (`--backend`) |
| `mirror` | bool | `true` | Voltea en horizontal para que la vista previa funcione como un espejo (`--no-mirror`) |

#### Detectores

| Clave | Tipo | Por defecto | Descripción |
| --- | --- | --- | --- |
| `enable_face` | bool | `true` | Detección facial y reconocimiento de expresiones (`--no-face`) |
| `enable_hands` | bool | `true` | Seguimiento de manos y gestos. Necesita MediaPipe (`--hand` / `--no-hands`) |
| `enable_segmentation` | bool | `false` | Máscara de persona para `bg_blur`, `bg_replace` y `privacy` (`--segment`) |
| `max_faces` | int | `1` | Número máximo de caras a seguir (`--max-faces`) |
| `max_hands` | int | `2` | Número máximo de manos a seguir (`--max-hands`) |
| `min_face_confidence` | float | `0.5` | Umbral de detección facial, de 0 a 1 |
| `min_hand_confidence` | float | `0.5` | Umbral de detección de manos, de 0 a 1 |
| `min_tracking_confidence` | float | `0.5` | Umbral de seguimiento de ambos modelos, de 0 a 1 |
| `model_complexity` | int | `1` | `0` = más rápido, `1` = equilibrado. Reservada — ningún backend la lee todavía |

#### Pipeline

| Clave | Tipo | Por defecto | Descripción |
| --- | --- | --- | --- |
| `filter` | str | `"original"` | Filtro o cadena con `+`, por ejemplo `cartoon+vignette+glitch` (`--filter`, `-f`) |
| `effects` | list | `[]` | Nombres de efectos AR, por ejemplo `["sunglasses","dog"]` (`--effect`, repetible) |
| `gesture_control` | bool | `true` | Deja que los gestos disparen acciones (`--no-gesture-control` los detecta sin actuar) |
| `air_draw` | bool | `false` | Arranca con el dibujo en el aire activado (`--air-draw`). Reservada — se activa con `d` o con el gesto `pointing` |
| `smooth_landmarks` | bool | `true` | Suavizado One-Euro de puntos de referencia. Apagarlo también desactiva el EMA de expresiones |
| `smoothing_min_cutoff` | float | `1.7` | Frecuencia de corte One-Euro en reposo: más bajo = más suave y algo más lento |
| `smoothing_beta` | float | `0.35` | Coeficiente de velocidad One-Euro: más alto = más reactivo al movimiento rápido |
| `expression_smoothing` | float | `0.35` | Peso del EMA para las puntuaciones de expresión, de 0 a 1; `0` lo desactiva |

#### Ventana y HUD

| Clave | Tipo | Por defecto | Descripción |
| --- | --- | --- | --- |
| `window_name` | str | `"MirrorLab"` | Título de la ventana de vista previa |
| `window_width` | int | `1280` | Ancho de la ventana de vista previa |
| `window_height` | int | `720` | Alto de la ventana de vista previa |
| `fullscreen` | bool | `false` | Arranca en pantalla completa (`--fullscreen`) |
| `show_hud` | bool | `true` | Dibuja los paneles y las etiquetas del HUD (`--no-hud`, o `h`) |
| `show_landmarks` | bool | `true` | Dibuja la malla facial y los esqueletos de las manos (`--no-landmarks`, o `l`) |
| `show_fps` | bool | `true` | Dibuja el panel de FPS, tiempo de fotograma e inferencia |
| `reactions_dir` | str | `"assets/reactions"` | Directorio de imágenes de reacción. Reservada — todavía no se dibujan |
| `show_reactions` | bool | `false` | Muestra una imagen de reacción por expresión (`--reactions`). Reservada — todavía no se dibujan |

#### Salida

| Clave | Tipo | Por defecto | Descripción |
| --- | --- | --- | --- |
| `output_dir` | str | `"captures"` | Directorio de capturas y grabaciones (`--output`) |
| `record_fps` | float | `30.0` | Frecuencia de fotogramas escrita en las grabaciones |
| `record_codec` | str | `"mp4v"` | FourCC del escritor de vídeo (`--record-codec`); si falla, prueba `XVID` y luego `MJPG` |
| `snapshot_format` | str | `"png"` | `png`, `jpg`, `jpeg` o `webp` |
| `jpeg_quality` | int | `95` | Calidad de los formatos de captura con pérdida |

#### Runtime

| Clave | Tipo | Por defecto | Descripción |
| --- | --- | --- | --- |
| `headless` | bool | `false` | Sin ventana de vista previa; para servidores, CI y procesos por lotes (`--headless`) |
| `max_frames` | int | `0` | Se detiene tras N fotogramas; `0` = sin límite (`--frames`) |
| `stats_csv` | str | `""` | Añade estadísticas por fotograma a este CSV; vacío = desactivado (`--stats-csv`) |
| `log_level` | str | `"INFO"` | Nivel de registro. Reservada — usa `--verbose` / `-v` para ver el detalle de depuración |
| `theme` | str | `"aurora"` | Paleta del HUD: `aurora`, `magma`, `mono` o `candy` (`--theme`, o `t` en caliente) |

### Filtros

54 filtros en seis categorías. Pasa uno con `--filter` o encadénalos con `+`:
`--filter cartoon+vignette+glitch`. El token de la CLI es el nombre de la primera columna.

`cost` es una guía aproximada: `cheap` está por debajo de 2 ms a 640×480, `medium` llega a
unos 20 ms y `heavy` lo supera. Las cifras medidas están en [Rendimiento](#rendimiento).

<details>
<summary><b>🎛️ Básicos — 9 filtros</b></summary>

| Nombre | Emoji | Descripción |
| --- | --- | --- |
| `original` | 🎥 | La señal de cámara sin tocar |
| `grayscale` | ⚫ | Solo luminancia, con un ligero aumento de contraste |
| `sepia` | 🟤 | Tono antiguo cálido mediante una matriz de color fija |
| `invert` | 🔳 | Negativo fotográfico |
| `posterize` | 🧱 | Cuantiza cada canal a unos pocos niveles planos: aspecto de serigrafía |
| `sharpen` | 🔪 | Máscara de enfoque que levanta el detalle local sin halos |
| `blur` | 💧 | Desenfoque gaussiano de ensueño |
| `vignette` | ⭕ | Esquinas oscurecidas que llevan la mirada al centro del encuadre |
| `emboss` | 🗿 | Sombreado de bordes en bajorrelieve que parece tallado |

</details>

<details>
<summary><b>🌈 Color — 6 filtros</b></summary>

| Nombre | Emoji | Descripción |
| --- | --- | --- |
| `warmth` | 🌅 | Sombras cálidas y ligeramente levantadas: favorece a cualquier tono de piel |
| `saturation` | 🎨 | Aumento contundente de saturación en espacio HSV |
| `duotone` | 🎭 | Mapea la luminancia sobre una rampa de dos colores |
| `cyberpunk` | 🌆 | Sombras turquesa, altas luces naranjas y un resplandor de neón |
| `infrared` | 🩻 | Falso color tipo Aerochrome: el follaje se vuelve rosa y la piel, porcelana |
| `lomo` | 📷 | Aspecto de cámara de juguete: saturación alta, negros aplastados y viñeta fuerte |

</details>

<details>
<summary><b>🖌️ Artísticos — 13 filtros</b></summary>

| Nombre | Emoji | Descripción |
| --- | --- | --- |
| `cartoon` | 🖍️ | Zonas de color plano con contornos gruesos: el look cel clásico |
| `sketch` | ✏️ | Dibujo a lápiz con mezcla de sobreexposición y un baño de color opcional |
| `ink` | 🖊️ | Line art de alto contraste, como dibujado con pincel |
| `oil` | 🖼️ | Pinceladas por histograma: cada píxel toma el color dominante de su vecindad |
| `watercolor` | 🎐 | Aguadas suaves con bordes de papel y altas luces levantadas |
| `halftone` | 🔵 | Trama de puntos de periódico, generada con una retícula rotada |
| `ascii` | 🔤 | Dibuja el fotograma con glifos de texto — sí, en tiempo real |
| `pixelate` | 🟦 | Mosaico de 8 bits, con tamaño de bloque animado opcional |
| `glass` | 🪟 | Celdas de color separadas por líneas de plomo oscuras |
| `pointillism` | 🔴 | Puntos de color puro estilo Seurat que se mezclan en tu ojo |
| `kaleidoscope` | 🔮 | Multiplica el fotograma en N cuñas giratorias: material de fondo de pantalla |
| `fisheye` | 🐟 | Distorsión de barril sacada de un vídeo de skate |
| `comic` | 💥 | Puntos Ben-Day, degradados de trama y tinta gruesa: una página impresa |

</details>

<details>
<summary><b>✨ Estilizados — 9 filtros</b></summary>

| Nombre | Emoji | Descripción |
| --- | --- | --- |
| `neon` | 💡 | Solo bordes, floreciendo en color eléctrico sobre negro |
| `thermal` | 🌡️ | Mapa de calor en falso color a partir de la luminancia invertida |
| `night_vision` | 🌙 | Intensificador de imagen Gen-II: fósforo verde, ruido de ganancia y resplandor |
| `xray` | 🦴 | Radiografía invertida con bordes brillantes como huesos |
| `hologram` | 🔷 | Proyección de líneas cian con parpadeo de líneas de barrido y una barra glitch |
| `dream` | ☁️ | Resplandor de enfoque suave con negros levantados y color pastel |
| `orton` | 🌤️ | El resplandor del fotógrafo de paisaje: copia desenfocada al 50 % en pantalla |
| `solarize` | 🔆 | Efecto Sabattier: los tonos que pasan del punto medio se invierten |
| `anaglyph` | 🕶️ | Separación estéreo rojo/cian: consigue unas gafas de cartón |

</details>

<details>
<summary><b>📺 Glitch y retro — 9 filtros</b></summary>

| Nombre | Emoji | Descripción |
| --- | --- | --- |
| `glitch` | ⚡ | Desplazamiento de bloques tipo databend, cizalladura RGB y ruido de pérdida |
| `chromatic` | 🔴 | Franjas de color radiales propias de una lente, más fuertes en los bordes |
| `vhs` | 📼 | Ruido de seguimiento, sangrado de color, bamboleo de cinta y sello de tiempo |
| `crt` | 🖥️ | Subpíxeles de rejilla de apertura, líneas de barrido, cristal abombado y barra rodante |
| `datamosh` | 🧬 | Los vectores de movimiento emborronan los píxeles del fotograma anterior: fotogramas P rotos |
| `scanlines` | 〰️ | Entrelazado sutil más una ligera deriva horizontal |
| `trails` | 👻 | Retardo por realimentación que deja fantasmas de todo lo que se mueve |
| `matrix` | 🟩 | Columnas de katakana cayendo sobre una señal teñida de verde |
| `slitscan` | 🌌 | Cada fotograma aporta una columna: el tiempo se vuelve espacio |

</details>

<details>
<summary><b>🛠️ Utilidades — 8 filtros</b></summary>

| Nombre | Emoji | Descripción |
| --- | --- | --- |
| `bg_blur` | 🌀 | Separación tipo retrato. Necesita `--segment` para construir la máscara de persona |
| `bg_replace` | 🏞️ | Cambia el fondo por un degradado o un color plano. Necesita `--segment` |
| `privacy` | 🕵️ | Desenfoca el fondo para que solo se te lea a ti: compartir pantalla sin sustos |
| `face_crop` | 🙂 | Mantiene tu cara centrada y con el tamaño correcto en el encuadre |
| `skin_smooth` | 🧖 | Retoque por separación de frecuencias: suaviza la textura y conserva el detalle |
| `mirror` | 🪞 | Refleja la mitad izquierda sobre la derecha: simetría instantánea |
| `zoom` | 🔍 | Zoom digital con un movimiento de respiración suave |
| `grid` | 📐 | Guías de composición para encuadrar |

</details>

El algoritmo de cada filtro — las llamadas reales a OpenCV y las fórmulas — está documentado en [docs/FILTERS.md](docs/FILTERS.md).

### Presets

Un preset es una cadena de filtros ya ajustada detrás de un solo nombre. `[` y `]` los recorren en caliente, y los gestos `swipe_up` / `swipe_down` hacen lo mismo.

| Preset | Cadena | Aspecto |
| --- | --- | --- |
| `cinema` | `warmth+vignette+sharpen` | Altas luces cálidas, esquinas suaves, detalle nítido |
| `anime` | `cartoon+saturation` | Colores planos tipo cel con paleta viva |
| `noir` | `grayscale+vignette+sharpen` | Monocromo de alto contraste con viñeta marcada |
| `retro80s` | `cyberpunk+chromatic+scanlines` | Gradación de neón, franjas de color y líneas CRT |
| `broken` | `glitch+trails` | Bloques databend con estelas |
| `toon` | `comic+halftone` | Puntos Ben-Day y tinta gruesa |
| `ghost` | `xray+glitch` | Aspecto de radiografía con cortes de señal |
| `studio` | `skin_smooth+warmth+bg_blur` | Piel retocada, luz cálida, fondo desenfocado (necesita `--segment`) |
| `paper` | `sketch+saturation` | Trazo de grafito con un baño de color |
| `vhs` | `vhs+scanlines` | Bamboleo de cinta, ruido de seguimiento y líneas de barrido |

```bash
mirrorlab run --preset noir
mirrorlab run --preset studio --segment
mirrorlab filters --presets
```

### Efectos AR

15 efectos, que se pasan con `--effect` (repetible): `mirrorlab run --effect sunglasses --effect fire`.
Los efectos faciales se anclan a la línea de los ojos, así que escalan con la distancia
interocular y rotan con la inclinación de la cabeza. Todo se dibuja por procedimiento con
primitivas de OpenCV: sin archivos PNG ni arte binario en el repositorio.

**Efectos faciales (11)**

| Nombre | Emoji | Descripción |
| --- | --- | --- |
| `sunglasses` | 🕶️ | Gafas ancladas a la línea de los ojos: siguen el movimiento de tu cabeza |
| `laser_eyes` | 🔴 | Dos rayos saliendo de tus pupilas, con parpadeo animado |
| `dog` | 🐶 | Orejas, nariz y una lengua que sigue tu mandíbula |
| `crown` | 👑 | Una corona dorada: eres el protagonista |
| `halo` | 😇 | Un anillo de luz que flota sobre tu cabeza |
| `mustache` | 🥸 | Un bigote anclado a tu labio superior |
| `blush` | 😊 | Mejillas sonrosadas que se intensifican al sonreír |
| `visor` | 🤖 | Una barra HUD que escanea tus ojos, con lectura en vivo |
| `mask` | 😷 | Una mascarilla ajustada al óvalo de tu cara |
| `big_eyes` | 👀 | Deformación local que agranda los ojos, modo anime |
| `googly` | 🙃 | Dos ojos de papel que se mueven sobre los tuyos |

**Efectos de mano (4)**

| Nombre | Emoji | Descripción |
| --- | --- | --- |
| `trails` | 🌈 | Cintas brillantes que siguen tus dedos y se desvanecen |
| `fire` | 🔥 | Llamas saliendo de tus dedos, más intensas al abrir la mano |
| `sparkles` | ✨ | Una estrella de cuatro puntas brilla en cada dedo |
| `skeleton` | 🦾 | Dibuja el esqueleto de 21 puntos con brillo en los huesos |

Dos de ellos reaccionan a lo que hace tu cara: `dog` alarga la lengua con `jawOpen` y
`blush` se intensifica con `mouthSmile`. Los efectos que reaccionan a las expresiones se
sienten vivos; las pegatinas estáticas no.

---

## Atajos de teclado y de gestos

### Teclado

| Tecla | Acción |
| --- | --- |
| `q` / `Q` | Salir |
| `s` | Guarda una captura de exactamente lo que ves |
| `r` | Empieza o para la grabación (MP4 + GIF) |
| `1`–`9` | Salta al enésimo filtro (orden alfabético) |
| `n` / `p` | Filtro siguiente / anterior |
| `]` / `[` | Preset siguiente / anterior |
| `f` | Congela el fotograma |
| `h` | Muestra u oculta el HUD |
| `l` | Muestra u oculta los puntos de referencia (malla facial y esqueletos) |
| `m` | Activa o desactiva el modo espejo |
| `e` / `Esc` | Activa o desactiva los efectos AR |
| `d` | Activa o desactiva el dibujo en el aire |
| `b` | Tira de comparación antes/después |
| `t` | Rota el tema del HUD |
| `c` | Borra el lienzo del dibujo en el aire |
| `x` | Reinicia todo el estado temporal (suavizado, votos, contadores) |

### Gestos

Los gestos se detectan, se muestran en el HUD y — cuando `gesture_control` está activo — se
asocian a acciones. **Un gesto que dispara una acción tiene que mantenerse unos 0,6 s,** y la
espera se dibuja como un anillo que se llena alrededor de tu mano, etiquetado con la acción
pendiente. Ese anillo es lo que hace que el control por gestos se sienta intencionado y no
nervioso: ves que la app te ha reconocido, ves cuánto falta y ves el instante en que se
ejecuta. Un periodo refractario y la exigencia de soltar el gesto hacen que un pulgar arriba
sea una captura, y no una ráfaga.

| Gesto | Nombre | Acción |
| --- | --- | --- |
| 🖐️ | `open_palm` | Muestra u oculta los puntos de referencia |
| ✊ | `fist` | Congela el fotograma |
| ☝️ | `pointing` | Activa o desactiva el dibujo en el aire |
| ✌️ | `peace` | Filtro siguiente |
| 3️⃣ | `three` | Filtro anterior |
| 4️⃣ | `four` | Activa o desactiva los efectos AR |
| 👍 | `thumbs_up` | Guarda una captura |
| 👎 | `thumbs_down` | Borra la última captura |
| 👌 | `ok` | Muestra u oculta el HUD |
| 🤏 | `pinch` | Entrada de precisión (goma de borrar mientras dibujas) |
| 🤘 | `rock` | Activa o desactiva el filtro `glitch` |
| 🤙 | `call_me` | Activa o desactiva el modo espejo |
| 🤟 | `ily` | Salta al filtro `love` |
| 🖖 | `spock` | Rota el tema del HUD |
| 🔫 | `gun` | Muestra u oculta el HUD |
| 1️⃣ | `one` | Salta a `original` |
| 6️⃣ | `six` | Salta a `cartoon` |
| 7️⃣ | `seven` | Salta a `sketch` |
| 8️⃣ | `eight` | Salta a `thermal` |
| ➡️ | `swipe_right` | Filtro siguiente |
| ⬅️ | `swipe_left` | Filtro anterior |
| ⬆️ | `swipe_up` | Preset siguiente |
| ⬇️ | `swipe_down` | Preset anterior |
| 👋 | `wave` | Guarda una captura |
| 🔄 | `circle` | Rota el tema del HUD |

También se reconocen, pero no están asociados a ninguna acción: `claw` 🫳 y `pinch_zoom` 🔍
(el zoom a dos manos es una tarea del [roadmap](ROADMAP.md)). Cada gesto de la tabla está
definido por una regla geométrica legible: el matcher exacto y sus umbrales están en
[docs/GESTURES.md](docs/GESTURES.md).

Ejecuta `mirrorlab gestures` para ver la tabla en vivo, y `--no-gesture-control` para
detectar gestos sin dejar que actúen.

---

## Cómo funciona

```
   camera.py                 detectors/                  perception
 ┌────────────┐          ┌──────────────────┐      ┌───────────────────────┐
 │ hilo de    │ fotograma│ escalera de      │      │ ExpressionClassifier  │
 │ captura    │ ───────► │ backends         │ ───► │  52 blendshapes → 18  │
 │ (ranura   │          │  tasks → solut.  │      │ GestureTracker        │
 │  que des-  │          │  → yunet → haar  │      │  21 puntos → poses    │
 │  carta el  │          │  → none          │      │ classify_hands()      │
 │  antiguo)  │          │ suavizado One-Euro│     └───────────┬───────────┘
 └────────────┘          └──────────────────┘                  │ fotograma + caras + manos
                                                               ▼
   render/                  effects/                   filters/
 ┌────────────┐          ┌──────────────┐          ┌───────────────────────┐
 │ Hud        │ ◄─────── │ 15 efectos AR│ ◄─────── │ FilterChain           │
 │ Transition │          │ superposic.  │          │  cartoon+vignette+…   │
 │ imshow     │          │ dibujo aéreo │          │  54 etapas registradas│
 └────────────┘          └──────────────┘          └───────────────────────┘
        │
        └──► recording.py (MP4 + GIF), capturas, CSV de estadísticas
```

El orden por fotograma es: **hilo de captura → ranura de fotograma que descarta el antiguo
→ detección con MediaPipe Tasks → suavizado One-Euro de puntos de referencia → clasificación
de expresiones y gestos con EMA y voto por mayoría → cadena de filtros → superposiciones AR
→ HUD → `imshow` → grabadora → gestión de teclas.**

Hay dos decisiones de diseño que merece la pena explicar, porque son las que hacen que los
resultados sean estables.

**Por qué los coeficientes de expresión (blendshapes) ganan a las proporciones entre
puntos.** Una proporción entre dos puntos de referencia es un sustituto de un músculo: se
mueve cuando el músculo se mueve, pero también cuando giras la cabeza, cambias de distancia
o cuando el detector tiembla un píxel. El clásico detector de sonrisa
(`ancho_de_boca / ancho_de_cara > 0.42`) se dispara con una cara ancha, con un bostezo y con
un fotograma malo. Un coeficiente de expresión es la activación muscular en sí: MediaPipe
regresa 52 coeficientes estilo ARKit a partir de la malla facial, así que `mouthSmileLeft`
subiendo *es* el cigomático mayor contrayéndose. La clasificación pasa a ser aritmética
legible sobre canales con nombre (`happy = clamp(0.85·mouthSmile + 0.15·mouthDimple)`) en
lugar de un problema de ajuste, y deja de importar a qué distancia estás sentado. El
intercambio es honesto: los coeficientes necesitan el backend Tasks, así que hay un
respaldo geométrico documentado y `ExpressionResult.method` siempre dice qué camino produjo
la respuesta.

**Por qué las distancias de los gestos se normalizan por la escala de la mano.** Una pose
que puntúa 0,9 a 40 cm tiene que puntuar 0,9 a 1,5 m. Cada medida de gesto se divide por
`hand_scale()` — la distancia media de la muñeca a los nudillos de los cuatro dedos largos,
que es invariante a la rotación y estable cuando los dedos están doblados. Sin eso, cada
umbral necesitaría una calibración de distancia y el control por gestos solo funcionaría si
te quedaras quieto. Esa única normalización es la razón de que un clasificador por reglas sea
viable.

Además, los puntos de referencia se suavizan con un **filtro One-Euro** por punto y por
coordenada (Casiez et al., CHI 2012): la frecuencia de corte sube con la velocidad estimada,
así que una cara quieta deja de vibrar mientras que una yema rápida sigue respondiendo. Las
puntuaciones de expresión pasan por un EMA y un voto por mayoría de 7 fotogramas (4 de
acuerdo) decide la etiqueta final, de modo que un parpadeo no puede apoderarse del HUD.

Todo el detalle: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Rendimiento

Solo CPU, sin GPU y sin CUDA. Todas las cifras siguientes están medidas en un Apple M5
(arm64), Python 3.11.16, OpenCV 4.11.0 y MediaPipe 0.10.21, a 640×480 — reprodúcelas con las
órdenes indicadas.

**Etapa de filtros** (`mirrorlab benchmark --all --frames 20 --width 640 --height 480`):

| Métrica | Medido |
| --- | --- |
| Coste mediano por filtro | **1,41 ms** (≈709 fps de margen para la etapa de filtros) |
| Filtro más lento | `pointillism`, **17,06 ms** |
| Los siguientes más lentos | `watercolor` 15,75 ms, `oil` 14,39 ms, `comic` 13,45 ms, `cyberpunk` 10,68 ms |
| Los 54 filtros | **por debajo de 33 ms** — todos caben en un presupuesto de 30 fps, la mayoría con margen |
| Filtros más rápidos | `original` 0,01 ms, `invert` 0,03 ms, `grid` 0,04 ms, `grayscale` 0,10 ms |

**Etapa de detección**, medida ejecutando `PerceptionEngine.process()` sobre 40 fotogramas después del calentamiento de dos fotogramas:

| Escenario | Mediana | p95 |
| --- | --- | --- |
| Modelos de cara y manos activos, sin nada en el encuadre | **11,9 ms** | 18,3 ms |
| Modelos de cara y manos con dos manos detectadas y clasificadas | **21,7 ms** | 42,7 ms |

La inferencia de cara y manos en el mismo fotograma comparte un único presupuesto de CPU; por eso `--no-hands` es la palanca de velocidad más potente que tienes.

Sobre el primer fotograma: MediaPipe asigna sus grafos y delegados XNNPACK de forma perezosa, así que el primer fotograma visible puede tardar hasta ~300 ms y la vista previa da un tirón evidente. MirrorLab hace un calentamiento de dos fotogramas antes del primer `imshow` (`PerceptionEngine.warm_up`), lo que absorbe ese coste en el arranque.

### Consejos de ajuste

```bash
mirrorlab run --camera-width 640 --camera-height 480   # la mayor ganancia: el coste de detección escala con el área
mirrorlab run --no-hands                               # quita el modelo más caro
mirrorlab run --no-face                                # solo filtros
mirrorlab run --filter grayscale                       # el filtro más barato
mirrorlab benchmark --filter oil --frames 50           # mide antes de publicar una cadena
```

- **No encadenes tres filtros `medium`.** `cost` informa de la peor etapa, pero el *tiempo* es la suma: tres filtros de 10 ms son 30 ms de un presupuesto de 33 ms.
- **Deja `--segment` apagado** salvo que uses `bg_blur`, `bg_replace` o `privacy`. Ejecuta un modelo adicional.
- **Baja `smoothing_min_cutoff`** si los puntos de referencia tiemblan; no ralentiza nada.
- **Usa `MIRRORLAB_SMOOTHING_MIN_CUTOFF=1.0`** en vez de tocar el código — mira [Configuración](#configuración).

---

## Solución de problemas

Ejecuta estas dos órdenes primero; entre las dos responden a casi todo:

```bash
mirrorlab doctor           # backends, modelos, sondeos de capacidades
mirrorlab cameras          # qué índices y backends de captura entregan fotogramas
```

### La cámara no se abre

<details>
<summary><b>Soluciones por sistema operativo</b></summary>

- **macOS:** Ajustes del Sistema → Privacidad y seguridad → Cámara → activa *la terminal desde la que lanzaste*. El permiso es por aplicación anfitriona, no por Python. La primera ejecución lanza el diálogo; acéptalo y vuelve a intentarlo. Un iPhone con Continuity Camera puede ocupar el índice 0: prueba `--camera 1`.
- **Windows:** Configuración → Privacidad → Cámara → permite que las aplicaciones de escritorio usen la cámara. Después prueba `--backend msmf` y, si falla, `--backend dshow`.
- **Linux:** `sudo usermod -aG video "$USER"` y **vuelve a iniciar sesión** (la pertenencia a grupos se lee al iniciar sesión). Comprueba `ls -l /dev/video*`. En Docker/WSL2, pasa el dispositivo explícitamente.

Y cierra las demás apps que estén usando la cámara (Zoom, Teams, OBS, Photo Booth). `open_camera` lanza `CameraError` con la lista de comprobación de tu plataforma añadida, así que el mensaje del terminal ya contiene estos pasos. `mirrorlab cameras --max-index 5` te dice si el problema es el índice o el backend.

</details>

### Se cae en macOS con `DrishtiMetalHelper ... service is unavailable`

Ese es el bug de Metal de MediaPipe 1.0.1. Es un aborto nativo, no una excepción de Python que se pueda capturar. Instala la combinación probada:

```bash
pip install "mediapipe>=0.10.9,<0.11" "numpy<2" "opencv-python<5"
mirrorlab doctor
```

`mirrorlab doctor` imprime exactamente esa línea siempre que no arranca ningún motor facial. La explicación completa está en [docs/CROSS_PLATFORM.md](docs/CROSS_PLATFORM.md#the-dependency-pins).

### Pocos FPS

Mira [los consejos de ajuste](#consejos-de-ajuste). Por orden de impacto: baja la resolución de captura, usa `--no-hands`, evita `--segment` y elige un filtro más barato. El panel de rendimiento del HUD muestra FPS, tiempo de fotograma y tiempo de inferencia por separado, así que puedes saber si el cuello de botella es la detección o el filtrado.

### No se detectan las manos

El seguimiento de manos **necesita MediaPipe**: no hay ningún modelo de puntos de mano en OpenCV, así que sin él el backend de manos es `none` y los gestos se desactivan *por diseño* mientras la app sigue funcionando. Comprueba `mirrorlab doctor`. Si el backend está bien:

- Mete la **mano entera** en el encuadre, de la muñeca a las yemas. MediaPipe necesita la base de la palma.
- Ilumina la mano de frente; a contraluz se convierte en una silueta.
- No muevas rápido: el desenfoque de movimiento destroza la calidad de los puntos.
- Usa un índice de cámara real, no uno virtual limitado a 320×240.

### Falló la descarga de un modelo

La app sigue funcionando con menos funciones y registra un aviso; no se cae. Para arreglarlo:

```bash
mirrorlab models --status             # qué hay en caché y dónde
mirrorlab models --download           # descarga todo lo que falte
mirrorlab doctor --download           # lo mismo, más un informe completo del entorno
```

Si estás detrás de un proxy o sin conexión, descarga el archivo a mano en el directorio de caché que muestra `mirrorlab models --status` y vuelve a ejecutar: MirrorLab funciona completamente sin conexión una vez que el modelo está presente. `MIRRORLAB_MODELS=/ruta` cambia la ubicación de la caché, que es la configuración habitual en redes aisladas. Usa `--no-download` para garantizar que nunca se descargue nada.

### `AttributeError: module 'mediapipe' has no attribute 'solutions'`

Tienes MediaPipe ≥ 1.0. MirrorLab lo maneja —el backend Solutions es un peldaño de la escalera, no un requisito—, así que este error significa que hay código de terceros (o un tutorial anterior a 2025) llamando a `mp.solutions` directamente. El backend principal de MirrorLab es la Tasks API y no usa ese espacio de nombres. Si quieres tener disponible el peldaño antiguo, usa la [instalación verificada](#instalación-verificada).

### No pasa nada cuando uso `--air-draw` o `--reactions`

Correcto, y es una carencia conocida, no algo que estés haciendo mal: ambos flags se aceptan y se guardan en la configuración, pero la aplicación en ejecución todavía no los lee. El dibujo en el aire sí funciona: actívalo con `d` o con el gesto ☝️ `pointing`. Las imágenes de reacción no se dibujan en absoluto. Las dos cosas están en el [roadmap](ROADMAP.md).

### `doctor` dice `display: headless (no window)` en mi escritorio, y los contadores de capacidades salen a 0

También es una carencia conocida: `doctor` imprime esos campos desde un sondeo que no los proporciona. Las secciones de entorno, detectores y modelos son correctas. Se arregla en el [hito v2.1](ROADMAP.md#v21--polish-and-reach).

### La ventana no se cierra en macOS

Cocoa necesita unas cuantas iteraciones del bucle de eventos después de `destroyAllWindows()`; MirrorLab las hace al salir, así que la ventana puede quedarse una fracción de segundo y luego desaparece. Si se queda en pantalla y el proceso parece colgado, es que estás llamando a `destroyAllWindows()` tú mismo antes de que `run()` retorne.

Hay más respuestas —privacidad, uso comercial, cámaras virtuales, gestos propios, Docker, WSL2— en **[docs/FAQ.md](docs/FAQ.md)**.

---

## Estructura del proyecto

```
mirrorlab/
├── src/mirrorlab/
│   ├── __init__.py              # fachada perezosa del paquete (PEP 562): importar sale barato
│   ├── __main__.py              # punto de entrada de `python -m mirrorlab`
│   ├── version.py               # __version_info__, CODENAME
│   ├── config.py                # dataclass Config congelada, DEFAULTS, resolución en 4 capas
│   ├── camera.py                # backends por sistema, captura con hilo y ranura, fuente sintética
│   ├── app.py                   # el bucle de fotogramas: percepción → filtros → efectos → HUD
│   ├── cli.py                   # doce subcomandos, argparse, salida --json
│   ├── actions.py               # asociaciones gesto→acción, máquina de dwell, anillo de espera
│   ├── airdraw.py               # lienzo persistente guiado por la yema del índice
│   ├── recording.py             # escritor MP4 con hilo, exportación a GIF, capturas
│   ├── expressions.py           # 18 expresiones, scorers de blendshapes, respaldo geométrico
│   ├── gestures.py              # HandPose, 22 gestos, matchers declarativos, tracker de movimiento
│   ├── detectors/
│   │   ├── base.py              # FaceObservation, HandObservation, FrameAnalysis, tablas de índices
│   │   ├── backends.py          # la escalera de cinco peldaños: tasks → solutions → yunet → haar → none
│   │   ├── engine.py            # PerceptionEngine: una llamada por fotograma, todo lo derivado
│   │   ├── face.py              # FaceDetector: backend + suavizado One-Euro de puntos
│   │   ├── hands.py             # HandDetector: corte más alto, pistas estables por lateralidad
│   │   ├── models.py            # tabla MODELS, rutas de caché, descargas atómicas verificadas
│   │   └── segmentation.py      # SelfieSegmenter + refinado de máscara (bloque mayor, difuminado)
│   ├── filters/
│   │   ├── base.py              # Filter, FilterContext, FilterChain, registro, CATEGORIES
│   │   ├── classic.py           # filtros básicos y de color
│   │   ├── artistic.py          # cartoon, sketch, oil, halftone, ascii…
│   │   ├── stylize.py           # neon, thermal, x-ray, hologram, dream…
│   │   ├── glitch.py            # glitch, vhs, crt, datamosh, trails, slitscan…
│   │   ├── utility.py           # fondo desenfocado/cambiado, privacidad, encuadre facial, piel
│   │   └── __init__.py          # PRESETS, filter_names(), filters_by_category()
│   ├── effects/
│   │   ├── face.py              # 11 efectos faciales + 4 de mano, dibujados por procedimiento
│   │   └── __init__.py          # reexporta el registro de efectos
│   ├── render/
│   │   ├── hud.py               # Hud, HudState, paneles, etiquetas, esqueletos, retícula
│   │   └── composition.py       # blend, letterbox, lado a lado, rejilla, Transition
│   └── utils/
│       ├── geometry.py          # distance, angle, hand_scale, finger_curl, clamp…
│       ├── smoothing.py         # OneEuroFilter, EmaFilter, SlidingWindow, LandmarkSmoother
│       ├── timing.py            # FpsMeter con perfilado por etapa, Stopwatch
│       ├── colors.py            # Palette y los cuatro temas del HUD
│       └── logging.py           # get_logger / setup_logging
├── docs/                        # ARCHITECTURE, FILTERS, GESTURES, EXPRESSIONS, CROSS_PLATFORM, FAQ
├── tests/                       # pruebas de lógica pura + imágenes de ejemplo (sin cámara en CI)
├── web/                         # demo en el navegador con Vite + React (TypeScript, visión WebAssembly)
├── legacy/                      # el prototipo monolítico de la 1.x, solo como referencia
├── assets/reactions/            # imágenes de reacción (presentes, aún sin dibujar — ver el roadmap)
├── pyproject.toml               # empaquetado, extras, script de consola, configuración de herramientas
├── Makefile                     # make install / test / lint / check / run / demo / benchmark
├── CITATION.cff                 # cómo citar este software
└── LICENSE                      # MIT
```

---

## Roadmap

**Publicado en la 2.0**

- [x] Paquete modular que sustituye al prototipo monolítico (ahora en `legacy/`)
- [x] Migración a **MediaPipe Tasks**: 478 puntos, 52 coeficientes de expresión, matriz de transformación facial
- [x] Escalera de respaldo de cinco peldaños: la app degrada en lugar de romperse
- [x] 54 filtros encadenables en seis categorías, más 10 presets seleccionados
- [x] Seguimiento de manos con 21 gestos estáticos y 6 dinámicos, todos explicables geométricamente
- [x] Control por gestos con máquina de estados de espera y anillo de confirmación en pantalla
- [x] Captura multiplataforma: AVFoundation, DSHOW, MSMF, V4L2, archivos de vídeo y fuente sintética
- [x] Demo en el navegador con la lógica del clasificador portada a TypeScript

**Lo siguiente**

- [ ] **Publicación en PyPI** para que funcione `pip install mirrorlab`
- [ ] **Fórmula de Homebrew** para macOS
- [ ] **Salida de cámara virtual** para Zoom/OBS/Meet — `pyvirtualcam` es GPLv2, así que será un extra opcional
- [ ] **Paralaje por pose de cabeza** usando la matriz de transformación 4×4 que la API ya devuelve
- [ ] **Renderizado de máscaras 3D** con oclusión correcta, con la misma matriz más una máscara de pelo
- [ ] **Seguimiento de mirada** con los canales `eyeLook*`, hoy sin usar
- [ ] **Modo de juego piedra-papel-tijera** — las tres poses ya se clasifican
- [ ] **API de plugins** para filtros de terceros, con un modelo de confianza diseñado
- [ ] **Compartir presets** como archivo portátil y enlace
- [ ] **Entrenador MLP de gestos** para manos a las que las reglas geométricas sirven mal

La lista completa de hitos, y lo que explícitamente *no* está planeado y por qué, está en [ROADMAP.md](ROADMAP.md).

---

## Contribuir

Tres cosas que conviene saber antes de abrir un PR: ejecuta `make check` (black, ruff, mypy,
pytest) antes de subir nada; la CI no tiene cámara ni red, así que la lógica pura tiene que
ser comprobable sin hardware; y los mensajes de commit siguen
[Conventional Commits](https://www.conventionalcommits.org/). La primera contribución más
sencilla es un filtro nuevo (~30 líneas) o un gesto nuevo (~10 líneas): los registros hacen
todo el cableado, así que nunca tocas la CLI.

Lee [CONTRIBUTING.md](CONTRIBUTING.md) para el entorno, el estilo, la lista de comprobación
del PR y cómo añadir un filtro, un gesto o un efecto. Los issues etiquetados como
**`good first issue`** están acotados para ser autocontenidos. Todo el mundo que participa
acepta el [Código de Conducta](CODE_OF_CONDUCT.md).

---

## Licencias de modelos y créditos

El código de MirrorLab es MIT. Los modelos no: se descargan en tiempo de ejecución, nunca se
redistribuyen y cada uno se rige por su propia model card.

| Componente | Licencia | Notas |
| --- | --- | --- |
| [MediaPipe](https://ai.google.dev/edge/mediapipe/solutions/guide) | Apache-2.0 | Tasks API: FaceLandmarker, HandLandmarker, ImageSegmenter |
| [OpenCV](https://opencv.org/) (`opencv-python`) | Apache-2.0 | Captura, cada operación de imagen, el HUD, la codificación de vídeo |
| [NumPy](https://numpy.org/) | BSD-3-Clause | Todos los arrays del pipeline |
| [rich](https://github.com/Textualize/rich) | MIT | Opcional: salida de CLI más agradable |
| [PyYAML](https://pyyaml.org/) | MIT | Opcional: archivos de configuración `.yaml` |
| `face_landmarker.task` | [model card](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker) | 478 puntos, 52 coeficientes de expresión, matriz 4×4 — 3,7 MB, se descarga |
| `hand_landmarker.task` | [model card](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker) | 21 puntos por mano + lateralidad — 7,8 MB, se descarga |
| `selfie_segmenter.tflite` | [model card](https://ai.google.dev/edge/mediapipe/solutions/vision/image_segmenter) | Máscara de persona para los efectos de fondo — 0,25 MB, se descarga |
| `face_detection_yunet_2023mar.onnx` | [OpenCV Model Zoo](https://github.com/opencv/opencv_zoo) | Detector de respaldo con 5 puntos — 0,23 MB, se descarga |

Todo lo demás, incluidos `gesture_recognizer.task`, `pose_landmarker_lite.task` y
`selfie_multiclass_256x256.tflite`, es opcional y no está en el camino por defecto.

Dos consecuencias que conviene decir sin rodeos: **los pesos de los modelos se descargan en
tiempo de ejecución y este proyecto no los redistribuye**, y sus condiciones son las de sus
editores — revisa la model card antes de incluir un modelo dentro de tu propio producto. El
inventario completo, incluidas las dependencias transitivas y la frontera GPL del soporte de
cámara virtual, está en [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

---

## Citación

Si usas MirrorLab en un trabajo académico, cítalo con [CITATION.cff](CITATION.cff) o con:

```bibtex
@software{mirrorlab2026,
  title        = {MirrorLab: real-time webcam filters, facial expressions and hand
                  gestures on the CPU},
  author       = {Trinidad Arguello, Huascar Ignacio D and {TrinaxCode}},
  year         = {2026},
  version      = {2.0.0},
  license      = {MIT},
  url          = {https://github.com/TrinaxCode/mirrorlab},
  repository   = {https://github.com/TrinaxCode/mirrorlab},
  keywords     = {computer-vision, webcam, mediapipe, opencv, hand-tracking,
                  gesture-recognition, facial-expression-recognition, blendshapes}
}
```

## Licencia

MIT — © 2026 TrinaxCode (Huascar Ignacio D Trinidad Arguello). Consulta [LICENSE](LICENSE).
Úsalo en el trabajo, inclúyelo en un producto, vende un servicio construido sobre él;
conserva el aviso de copyright y el texto de la licencia. Las condiciones de terceros de
arriba siguen aplicándose a las partes de terceros.

---

Si MirrorLab te resulta útil, una ⭐ en [GitHub](https://github.com/TrinaxCode/mirrorlab) ayuda a que más gente lo encuentre.
