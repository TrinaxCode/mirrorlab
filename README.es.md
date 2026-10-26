# MirrorLab

**Una cámara virtual para videollamadas, controlada con tus manos.** Desenfoque y reemplazo
de fondo, encuadre automático, exposición medida sobre tu rostro y un obturador de privacidad,
publicados como una cámara que Zoom, Meet, Teams, Discord, OBS y tu navegador pueden
seleccionar. Funciona en la CPU, en tu máquina, en Linux, macOS y Windows.

[English](README.md) | [Español](README.es.md)

[![CI](https://github.com/TrinaxCode/mirrorlab/actions/workflows/ci.yml/badge.svg)](https://github.com/TrinaxCode/mirrorlab/actions/workflows/ci.yml)
[![Licencia: MIT](https://img.shields.io/badge/license-MIT-3da639?style=flat-square)](LICENSE)
[![Python 3.9–3.12](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-3776ab?style=flat-square)](pyproject.toml)
[![Estado: beta](https://img.shields.io/badge/status-beta-f0a020?style=flat-square)](CHANGELOG.md)

```console
$ mirrorlab doctor                       # ¿está lista esta máquina? si no, te indica la solución exacta
$ mirrorlab cam --profile meeting        # desenfoque + encuadre automático + luz de estudio, publicado como cámara
$ mirrorlab ctl privacy                  # desde otra terminal o un atajo de teclado: cubre la cámara
```

Mantén la palma abierta durante 1,6 segundos y la cámara se cubre. Mantén el pulgar en alto y
un pulgar arriba flota sobre tu imagen para las demás personas de la llamada. Sin mouse, sin
ventanas que buscar en medio de una reunión.

---

## Por qué existe

Las formas habituales de obtener estos efectos tienen un costo: una aplicación específica de
cada plataforma (NVIDIA Broadcast, Studio Light de Apple, Windows Studio Effects), una GPU
NVIDIA, una configuración de OBS con un plugin y una escena, o un daemon solo para Linux.
MirrorLab es la versión pequeña y programable: un solo `pip install`, solo CPU, el mismo
comando en los tres sistemas y una base de código pequeña que puedes leer.

Lo que añade más allá del desenfoque es la **superficie de control**. En una reunión tienes las
manos libres y el teclado no, por lo que los efectos se controlan con gestos de la mano con un
tiempo de sostenimiento (para que un gesto hecho mientras conversas no active nada) y con un
comando `ctl` que puedes asignar a cualquier atajo de teclado.

No pretende superar en acabado a las aplicaciones dedicadas. No hay interfaz gráfica, la
máscara de la persona proviene de un modelo pequeño y rápido en lugar de una red de matting, y
en Windows y macOS sigues necesitando OBS instalado para proporcionar el dispositivo de cámara.
Consulta [Limitaciones](#limitaciones).

---

## Instalación

```bash
git clone https://github.com/TrinaxCode/mirrorlab.git
cd mirrorlab
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[vcam]"
mirrorlab doctor
```

`doctor` revisa Python, OpenCV y MediaPipe, qué modelos están en caché y si hay una cámara
virtual disponible, e imprime el comando exacto para cualquier cosa que falte. La primera
ejecución descarga unos 12 MB de modelos.

> **Todavía no está en PyPI.** Instala desde el código fuente como se indica arriba. La
> publicación en PyPI está en el [roadmap](ROADMAP.md).

El extra `vcam` instala [pyvirtualcam](https://github.com/letmaik/pyvirtualcam), que es
**GPL-2.0**, por lo que es opcional y nunca se instala por defecto. Sin él todo funciona,
excepto el último paso, publicar en una cámara (`--output none` aún te permite previsualizar).

El sistema operativo también necesita un dispositivo de cámara virtual:

| Sistema | Configuración única |
| --- | --- |
| **Linux** | `sudo apt install v4l2loopback-dkms` y luego `sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="MirrorLab" exclusive_caps=1` |
| **macOS** | Instala [OBS Studio](https://obsproject.com) 30+, haz clic en *Start Virtual Camera* y luego en *Stop Virtual Camera* una vez, y cierra OBS. |
| **Windows** | Instala [OBS Studio](https://obsproject.com) (proporciona la *OBS Virtual Camera*). |

Las instrucciones completas por plataforma, incluidos los permisos de cámara, están en
[docs/STUDIO.md](docs/STUDIO.md#setting-up-a-virtual-camera).

### Versiones de dependencias conocidas como funcionales

Si alguna versión de MediaPipe o NumPy se comporta mal en tu máquina, esta combinación es la
alternativa probada (MediaPipe 1.0.1 aborta dentro del helper de Metal de Apple en algunas
compilaciones de macOS):

```bash
pip install "mediapipe>=0.10.9,<0.11" "numpy<2" "opencv-python<5"
```

Detalles en [docs/CROSS_PLATFORM.md](docs/CROSS_PLATFORM.md#the-dependency-pins).

---

## Uso

```bash
mirrorlab cam --profile meeting                       # desenfoque + encuadre automático + luz de estudio
mirrorlab cam --background replace --bg-image office.jpg
mirrorlab cam --background green --studio-light       # chroma key para OBS
mirrorlab cam --privacy-on-start                      # inicia cubierta; una palma la abre
mirrorlab cam --away-after 10                         # cubre tras 10 s sin nadie en el encuadre
mirrorlab cam --output none --preview                 # pruébalo sin tener una cámara virtual instalada
```

Luego, desde cualquier lugar:

```bash
mirrorlab ctl status
mirrorlab ctl privacy              # alterna el obturador
mirrorlab ctl background blur
mirrorlab ctl react love
```

La configuración vive en un archivo opcional `studio.json`; los perfiles (`meeting`, `stream`,
`privacy`, `clean`, o los tuyos) la agrupan. Cada clave está documentada en
[docs/STUDIO.md](docs/STUDIO.md#settings), y las claves desconocidas producen un error en lugar
de ignorarse en silencio.

### Qué obtienes

| | |
| --- | --- |
| **Fondo** | `blur`, `replace` (tu imagen), `green` o `black`, con una máscara suavizada en el tiempo para que el contorno no parpadee |
| **Encuadre automático** | Paneo y zoom virtuales suaves que mantienen tu rostro en el tercio superior; zona muerta, zoom acotado, vuelve gradualmente cuando te vas |
| **Luz de estudio** | Exposición medida sobre tu rostro y no sobre la habitación, para que una ventana luminosa no te deje oscuro |
| **Obturador de privacidad** | Bajo demanda, por gesto, o automáticamente cuando sales del encuadre |
| **Reacciones** | Íconos de pulgar arriba, corazón y OK flotan sobre la imagen, activados con gestos de la mano |
| **Gestos** | Posturas de la mano con confirmación por sostenimiento, asignadas a cualquiera de las acciones anteriores |

### Gestos predeterminados

| Gesto | Acción | Sostener |
| --- | --- | --- |
| Palma abierta | alterna el obturador de privacidad | 1,6 s |
| Señal de paz | siguiente fondo | 1,0 s |
| Pulgar arriba | reacción de pulgar arriba | 0,6 s |
| Te quiero | reacción de corazón | 0,6 s |
| OK | reacción OK | 0,6 s |

Todo es reasignable en el archivo de configuración. El funcionamiento del reconocimiento y de la
lógica de confirmación por sostenimiento está en [docs/GESTURES.md](docs/GESTURES.md).

---

## Qué garantiza sobre tu privacidad

Estas garantías están escritas como propiedades que el código mantiene y que las pruebas
verifican ([detalles](docs/STUDIO.md#privacy-model)):

- **Nada sale de la máquina.** El único acceso a la red es la descarga única de modelos.
- **Los efectos de fondo fallan de forma segura.** Si la máscara de la persona no está
  disponible, todo el fotograma se desenfoca. Tu habitación nunca pasa sin filtro mientras
  crees que está oculta.
- **Un obturador cerrado no muestra píxeles de la cámara** (en los modos `card` y `black`
  predeterminados).
- **Una cámara perdida nunca se congela en tu última imagen.** Tras 1,5 s sin fotogramas, la
  salida pasa a ser la cubierta y la sesión reintenta con la cámara.
- **El canal de control es local y autenticado:** solo loopback, un token aleatorio en un
  archivo que solo tú puedes leer, y un protocolo de líneas que una página web no puede hablar.

---

## Rendimiento

Tasa de salida y costo por fotograma a 1280x720, en un portátil AMD Ryzen 7 5700U (Python 3.12)
que además ejecutaba un escritorio, un navegador y un editor. Tres ejecuciones de 400
fotogramas cada una sobre una entrada fija; el presupuesto de 30 fps es de 33 ms por fotograma.

| Configuración | Salida | Tiempo por fotograma p50 / p95 |
| --- | --- | --- |
| `--profile meeting` (desenfoque, encuadre, luz, gestos) | 29.9 fps | 23 ms / 29-33 ms |
| `--profile meeting --no-gestures` | 29.9 fps | 23 ms / 29 ms |
| `--profile clean` (passthrough) | 30.0 fps | 2.7 ms / 4 ms |

Mide el tuyo con el comando de [docs/STUDIO.md](docs/STUDIO.md#performance), que también
indica qué reducir en una máquina más lenta.

---

## Limitaciones

Cosas que son ciertas hoy, para que no las descubras en plena reunión:

- **Windows y macOS necesitan OBS instalado** para proporcionar el dispositivo de cámara. Es
  un límite de la biblioteca subyacente, algo que MirrorLab no puede eliminar.
- **La salida de la cámara virtual se prueba con mocks y, para todo lo anterior a ella, con una
  cámara real; no se ejercita contra un dispositivo real de `v4l2loopback` u OBS en CI.** Si
  falla en tu configuración, la salida de `mirrorlab doctor` en un issue es la vía más rápida
  hacia una solución.
- **La máscara proviene de un modelo pequeño.** El segmentador de selfies de MediaPipe es
  rápido y bueno para una vista de cabeza y hombros. El movimiento rápido de las manos y el
  cabello pueden mostrar un halo en el borde.
- **El encuadre automático es un recorte digital**, por lo que acercar cuesta resolución.
  `max_zoom` lo acota.
- **Sin audio.** La supresión de ruido del micrófono es un problema distinto y queda fuera del
  alcance.
- **Los gestos necesitan una mano visible y buena luz.** Si tu CPU es débil, `--no-gestures` y
  `mirrorlab ctl` ofrecen el mismo control sin seguimiento de manos.

---

## También en este repositorio

**El playground** (`mirrorlab play`) es el MirrorLab original: una ventana en vivo con 54
filtros de video encadenables, 15 efectos de RA, 18 expresiones faciales y 22 gestos de la
mano. Comparte el código de percepción con el estudio y está documentado en
[docs/PLAYGROUND.md](docs/PLAYGROUND.md). **La demo en el navegador** en [`web/`](web/) ejecuta
un subconjunto de las mismas ideas del lado del cliente, en
[mirrorlab-demo.vercel.app](https://mirrorlab-demo.vercel.app).

---

## Desarrollo

```bash
make install        # venv + extras de desarrollo
make check          # ruff, black, mypy sobre el paquete studio, y las pruebas
```

El conjunto de pruebas no necesita cámara ni red. La lógica del estudio se prueba con
detectores falsos; un pequeño conjunto de pruebas (`-m slow`) ejecuta los modelos reales de
MediaPipe sobre una fotografía real y se omite cuando los modelos no están disponibles.
CONTRIBUTING.md tiene las convenciones, y [docs/STUDIO.md](docs/STUDIO.md#how-a-frame-is-processed)
tiene el mapa del código.

```
src/mirrorlab/
├── studio/        la cámara virtual: configuración, estado, pipeline, efectos, control, sesión
├── detectors/     rostro / manos / segmentación de MediaPipe tras una escalera de respaldo
├── gestures.py    22 gestos de la mano a partir de reglas geométricas explicables
├── actions.py     gesto → acción con voto por mayoría, tiempo de sostenimiento y liberación
├── camera.py      backends de captura por SO, lector con hilos que descarta lo más reciente
├── filters/ effects/ render/ app.py     el playground
└── cli.py         comando `mirrorlab`
```

---

## Roadmap

Consulta [ROADMAP.md](ROADMAP.md): qué está hecho, qué sigue (publicación en PyPI, una prueba
de integración real con `v4l2loopback`, gestos calibrados) y qué no está planeado a propósito.

## Créditos y licencias

El código de MirrorLab es **MIT**. Está construido sobre [MediaPipe](https://ai.google.dev/edge/mediapipe)
(Apache-2.0), [OpenCV](https://opencv.org/) (Apache-2.0) y [NumPy](https://numpy.org/)
(BSD-3). Los modelos de rostro, manos y segmentación se **descargan en tiempo de ejecución, nunca
se redistribuyen**, y conservan los términos de sus editores. `pyvirtualcam` (GPL-2.0) es un
extra opcional que instalas tú. El inventario completo está en
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

Para citar, usa [CITATION.cff](CITATION.cff). Los reportes de seguridad se envían a través de
[SECURITY.md](SECURITY.md). Contribuciones: [CONTRIBUTING.md](CONTRIBUTING.md) y el
[Código de Conducta](CODE_OF_CONDUCT.md).

MIT © 2026 TrinaxCode (Huascar Ignacio D Trinidad Arguello).
