/**
 * Bilingual copy (Spanish default / English) for the whole site.
 *
 * The dictionary is intentionally a plain object rather than a runtime lookup
 * system: every string is checked by TypeScript, there is no interpolation
 * syntax to parse, and switching language is a single object swap.
 */

export type Lang = "es" | "en";

export const LANGS: readonly Lang[] = ["es", "en"] as const;

const es = {
  code: "es",
  htmlLang: "es",
  name: "Español",
  other: "English",
  switchLabel: "Cambiar a inglés",
  seo: {
    title: "MirrorLab · Cámara virtual con gestos para Windows, macOS y Linux",
    description:
      "Cámara virtual gratis para Zoom, Meet y Teams: desenfoca el fondo, te encuadra solo, ajusta la luz y se controla con gestos de la mano. Funciona en tu equipo y no sube vídeo a ningún sitio. Para Windows, macOS y Linux.",
    ogTitle: "MirrorLab: cierra la cámara con la mano abierta",
    ogDescription:
      "Desenfoque de fondo, encuadre automático y control por gestos para tus videollamadas. Gratis, de código abierto y privada.",
    ogLocale: "es_ES",
    keywords:
      "cámara virtual, desenfocar fondo videollamada, encuadre automático, control por gestos, Zoom, Google Meet, Microsoft Teams, OBS, webcam, privacidad, código abierto",
  },
  nav: {
    demo: "Demo",
    features: "Qué hace",
    control: "Gestos",
    download: "Descargar",
    install: "Instalar",
    filters: "Filtros",
    gestures: "Gestos",
    expressions: "Expresiones",
    shortcuts: "Atajos",
    reference: "Referencia",
    repo: "GitHub",
  },
  hero: {
    title: "Cierra la cámara con la mano abierta.",
    kicker: "Cámara virtual con control por gestos",
    pitch:
      "MirrorLab es una cámara virtual para Zoom, Meet y Teams. Desenfoca el fondo, te mantiene encuadrado y se controla con las manos, sin buscar el teclado en mitad de la reunión.",
    ctaPrimary: "Descargar la app",
    ctaSecondary: "Probar en el navegador",
    platforms: "Windows · macOS · Linux · gratis y de código abierto",
    commandLabel: "Así se arranca",
    copy: "Copiar",
    copied: "Copiado",
    caption: "Mantén la palma 1,6 segundos para cubrir la cámara. Otra vez para abrirla.",
    monitor: {
      label: "Vista previa animada de MirrorLab: fondo desenfocado, encuadre y una palma que cubre la cámara",
      live: "En vivo",
      covered: "Cámara cubierta",
      hold: "Palma · 1,6 s",
      source: "MirrorLab Virtual Camera",
      blur: "Fondo desenfocado",
      frame: "Encuadre",
      light: "Luz",
    },
  },
  features: {
    title: "Qué hace",
    subtitle:
      "Cuatro ajustes que corrigen lo que suele salir mal en una videollamada, y un obturador para cuando necesitas desaparecer.",
    items: [
      {
        name: "Fondo",
        body: "Desenfoque, una imagen tuya, croma verde o negro. La máscara de la persona se suaviza en el tiempo para que el contorno no tiemble.",
        readout: "blur · replace · green · black",
      },
      {
        name: "Encuadre",
        body: "Un paneo y un zoom suaves mantienen tu cara en el tercio superior. Ignora los movimientos pequeños y vuelve al plano completo cuando te levantas.",
        readout: "zoom hasta 1,8×",
      },
      {
        name: "Luz",
        body: "La exposición se mide sobre tu cara, no sobre toda la imagen: una ventana a tu espalda ya no te deja a oscuras.",
        readout: "medida en la cara",
      },
      {
        name: "Obturador",
        body: "Cubre la imagen cuando quieras, con un gesto o solo, tras unos segundos sin nadie delante.",
        readout: "palma · ctl privacy · --away-after",
      },
      {
        name: "Reacciones",
        body: "Un pulgar, un corazón o un ok flotan sobre tu imagen para el resto de participantes.",
        readout: "pulgar · corazón · ok",
      },
    ],
  },
  control: {
    title: "Se controla con las manos",
    subtitle:
      "Cada gesto tiene que mantenerse un rato antes de actuar. Uno hecho mientras hablas no dispara nada.",
    holdUnit: "s",
    holdLabel: "Tiempo que hay que mantenerlo",
    rows: [
      { emoji: "🖐️", gesture: "Palma abierta", hold: 1.6, action: "Cubre o descubre la cámara" },
      { emoji: "✌️", gesture: "Paz", hold: 1.0, action: "Pasa al siguiente fondo" },
      { emoji: "👍", gesture: "Pulgar arriba", hold: 0.6, action: "Lanza un pulgar sobre tu imagen" },
      { emoji: "🤟", gesture: "Te quiero", hold: 0.6, action: "Lanza un corazón" },
      { emoji: "👌", gesture: "OK", hold: 0.6, action: "Lanza un ok" },
    ],
    alt: "Sin manos libres: mirrorlab ctl privacy desde otra terminal o desde un atajo de teclado hace lo mismo que la palma.",
  },
  privacy: {
    title: "Qué sale de tu equipo",
    subtitle: "Casi nada. Esto es todo lo que ocurre en la red.",
    facts: [
      {
        title: "El vídeo no se sube",
        body: "La cámara se lee en tu navegador y se procesa en tu CPU o GPU. No hay ningún servidor que reciba la imagen.",
      },
      {
        title: "Los modelos se bajan una vez",
        body: "Unos 11 MB desde la CDN de MediaPipe, solo cuando enciendes la cámara. El navegador los guarda en caché.",
      },
      {
        title: "Las capturas no se descargan solas",
        body: "Se quedan en la bandeja de la página hasta que pulses Descargar.",
      },
      {
        title: "Sin cuentas ni seguimiento",
        body: "Esta página no pide registro ni usa cookies de seguimiento. Si quieres, puedes activar estadísticas anónimas de visitas desde el pie de página; están desactivadas por defecto.",
      },
    ],
  },
  download: {
    title: "Descarga la app",
    subtitle:
      "Una aplicación para Windows, macOS y Linux, con ventana, vista previa y todos los controles. Se instala como cualquier otra.",
    recommended: "Recomendado para tu sistema",
    cta: "Descargar para {os}",
    allReleases: "Todas las versiones y sumas de verificación",
    platforms: [
      {
        id: "windows",
        name: "Windows",
        file: "Instalador .exe o ZIP portátil",
        requirements: "Windows 10 o superior, 64 bits",
        note: "Para usarla en Zoom, Meet o Teams, instala OBS Studio: aporta el dispositivo «OBS Virtual Camera».",
      },
      {
        id: "macos",
        name: "macOS",
        file: "Imagen de disco .dmg",
        requirements: "macOS 12 o superior, chip Apple",
        note: "La app no está notarizada: la primera vez, clic derecho › Abrir. Necesita OBS Studio para la cámara virtual.",
      },
      {
        id: "linux",
        name: "Linux",
        file: "Paquete .deb o archivo .tar.gz",
        requirements: "Ubuntu 22.04 o equivalente, 64 bits",
        note: "Para la cámara virtual instala v4l2loopback: sudo apt install v4l2loopback-dkms.",
      },
    ],
    steps: [
      { title: "Descarga e instala", body: "Abre el archivo de tu sistema y sigue el instalador." },
      { title: "Enciende la cámara", body: "Pulsa «Encender cámara» y elige el fondo. La app te dice si falta algo." },
      { title: "Elígela en tu videollamada", body: "En Zoom, Meet o Teams, selecciona «MirrorLab» como cámara." },
    ],
    license:
      "El código es MIT. Los instaladores incluyen pyvirtualcam (GPL-2.0), así que los binarios se distribuyen bajo GPL-2.0.",
    screenshot: {
      src: "/screenshots/desktop-app-es.png",
      alt: "Ventana de MirrorLab en escritorio: vista previa de la cámara a la izquierda y, a la derecha, los controles de fondo, encuadre, luz, gestos y reacciones.",
      caption: "La app de escritorio: vista previa en directo y todos los controles.",
    },
  },
  faq: {
    title: "Preguntas frecuentes",
    subtitle: "Lo que suele preguntar la gente antes de instalarla.",
    items: [
      {
        q: "¿MirrorLab sube mi vídeo a algún sitio?",
        a: "No. La cámara se lee y se procesa en tu equipo, con la CPU. Lo único que se descarga son unos 12 MB de modelos de visión la primera vez, y los modelos se verifican con una suma SHA-256.",
      },
      {
        q: "¿Funciona con Zoom, Google Meet y Microsoft Teams?",
        a: "Sí. MirrorLab publica una cámara virtual que cualquier aplicación de videollamadas puede elegir, y también OBS, Discord y el navegador.",
      },
      {
        q: "¿Necesito una tarjeta gráfica NVIDIA?",
        a: "No. Todo corre en la CPU, en Windows, macOS y Linux. En un portátil de gama media mantiene 30 fotogramas por segundo.",
      },
      {
        q: "¿Por qué hace falta OBS o v4l2loopback?",
        a: "El sistema operativo necesita un dispositivo de cámara virtual y una aplicación no puede crearlo sola. En Windows y macOS lo aporta OBS Studio; en Linux, el módulo v4l2loopback. La app te dice qué falta.",
      },
      {
        q: "¿Cómo se controla sin tocar el teclado?",
        a: "Con gestos de la mano que hay que mantener un instante: la palma abierta tapa la cámara, la paz cambia el fondo y el pulgar, el corazón o el OK lanzan una reacción. También hay un comando, mirrorlab ctl, que puedes asignar a un atajo.",
      },
      {
        q: "¿Es gratis? ¿Quién lo ha hecho?",
        a: "Es gratis y de código abierto (MIT). Lo creó TrinaxCode y el código está en github.com/TrinaxCode/mirrorlab.",
      },
    ],
  },
  install: {
    title: "O instálalo con Python",
    subtitle:
      "Para desarrolladores y para quien prefiera la terminal. Python 3.9 a 3.12, solo CPU. Windows y macOS necesitan OBS para tener un dispositivo de cámara; Linux usa v4l2loopback.",
    tabsLabel: "Sistema operativo",
    copy: "Copiar",
    copied: "Copiado",
    notOnPypi: "Todavía no está en PyPI: se instala desde el código fuente.",
    docs: "Guía completa de la cámara virtual",
    platforms: [
      {
        id: "linux",
        name: "Linux",
        steps: [
          { title: "Crea el dispositivo de cámara", code: "sudo apt install v4l2loopback-dkms libegl1 libgles2\nsudo modprobe v4l2loopback devices=1 video_nr=10 card_label=\"MirrorLab\" exclusive_caps=1" },
          { title: "Instala MirrorLab", code: "git clone https://github.com/TrinaxCode/mirrorlab.git && cd mirrorlab\npython3 -m venv .venv && source .venv/bin/activate\npip install -e \".[vcam]\"" },
          { title: "Comprueba y arranca", code: "mirrorlab doctor\nmirrorlab cam --profile meeting --device /dev/video10" },
        ],
      },
      {
        id: "macos",
        name: "macOS",
        steps: [
          { title: "Prepara OBS una sola vez", body: "Instala OBS Studio 30 o superior, ábrelo, pulsa «Iniciar cámara virtual», luego «Detener» y ciérralo." },
          { title: "Instala MirrorLab", code: "git clone https://github.com/TrinaxCode/mirrorlab.git && cd mirrorlab\npython3 -m venv .venv && source .venv/bin/activate\npip install -e \".[vcam]\"" },
          { title: "Comprueba y arranca", code: "mirrorlab doctor\nmirrorlab cam --profile meeting", body: "Tu terminal necesita permiso de cámara. Cierra OBS mientras MirrorLab funciona." },
        ],
      },
      {
        id: "windows",
        name: "Windows",
        steps: [
          { title: "Instala OBS Studio", body: "Su instalador registra el dispositivo «OBS Virtual Camera»." },
          { title: "Instala MirrorLab", code: "git clone https://github.com/TrinaxCode/mirrorlab.git\ncd mirrorlab\npy -m venv .venv\n.venv\\Scripts\\activate\npip install -e \".[vcam]\"" },
          { title: "Comprueba y arranca", code: "mirrorlab doctor\nmirrorlab cam --profile meeting", body: "No uses la cámara virtual de OBS a la vez." },
        ],
      },
    ],
  },
  reference: {
    title: "Referencia de la demo",
    subtitle: "Todos los gestos, expresiones y atajos que reconoce la demo del navegador.",
    show: "Mostrar",
    hide: "Ocultar",
  },
  tray: {
    title: "Capturas",
    empty: "Las capturas que hagas con un gesto se guardan aquí. Nada se descarga solo.",
    download: "Descargar",
    discard: "Descartar",
    clear: "Vaciar bandeja",
    alt: "Captura hecha el",
  },
  demo: {
    invite: "Los modelos (unos 11 MB) se descargan solo cuando enciendes la cámara y se quedan en la caché del navegador.",
    title: "Pruébalo en el navegador",
    subtitle:
      "La misma detección de cara y manos que usa la versión de escritorio, más 21 filtros WebGL. La cámara virtual necesita el escritorio: aquí solo te ves a ti mismo.",
    start: "Encender cámara",
    retry: "Reintentar",
    stop: "Apagar cámara",
    cameraLabel: "Cámara",
    loadingVideo: "Preparando la cámara…",
    loadingModels: "Cargando los modelos de visión (unos 11 MB la primera vez)…",
    modelProgress: "Descargando modelo",
    frozenBadge: "CONGELADO",
    mirrorBadge: "ESPEJO",
    overlayHidden: "Superposición oculta",
    handsBadge: "manos",
  },
  camera: {
    insecureTitle: "Necesitas una conexión segura (HTTPS)",
    insecureBody:
      "El navegador solo entrega la cámara en contextos seguros. Abre esta página por HTTPS o en localhost (http://localhost:5173) y vuelve a intentarlo.",
    deniedTitle: "Permiso de cámara denegado",
    deniedBody:
      "Has bloqueado el acceso a la cámara para este sitio. Pulsa el icono de la cámara en la barra de direcciones, elige «Permitir» y reintenta.",
    notFoundTitle: "No se ha encontrado ninguna cámara",
    notFoundBody:
      "Conecta una webcam (o revisa que no la esté usando otra aplicación) y vuelve a intentarlo.",
    unsupportedTitle: "Este navegador no soporta la API de cámara",
    unsupportedBody:
      "Prueba con una versión reciente de Chrome, Edge, Firefox o Safari de escritorio.",
    unknownTitle: "No se pudo abrir la cámara",
    unknownBody: "Algo ha fallado al iniciar el vídeo. Reintenta o elige otra cámara.",
    hint: "Consejo: los modelos se descargan de la CDN de MediaPipe y se cachean en tu navegador.",
    detail: "Detalle técnico",
  },
  webgl: {
    title: "Tu navegador no puede crear un contexto WebGL2",
    body: "Los filtros necesitan WebGL2. Activa la aceleración por hardware o prueba otro navegador. La página sigue funcionando, pero sin filtros.",
  },
  vision: {
    loading: "Cargando modelos",
    ready: "Modelos listos",
    errorTitle: "No se pudieron cargar los modelos de MediaPipe",
    errorBody:
      "Suele ser un corte de red o un bloqueador. Comprueba tu conexión y reintenta: los modelos se descargan de cdn.jsdelivr.net y storage.googleapis.com.",
    retry: "Reintentar carga",
    face: "Rostro",
    hands: "Manos",
    segmenter: "Segmentador",
  },
  hud: {
    title: "Panel en vivo",
    fps: "FPS",
    inference: "Inferencia",
    hands: "Manos",
    filter: "Filtro",
    expression: "Expresión",
    gesture: "Gesto",
    top3: "Top 3 expresiones",
    noHand: "sin mano",
    noFace: "sin rostro",
    paused: "en pausa",
    waiting: "esperando…",
  },
  controls: {
    title: "Controles",
    overlays: "Superposición",
    landmarks: "Índices de landmarks",
    hud: "Panel de estadísticas",
    freeze: "Congelar imagen",
    mirror: "Vista espejo",
    snapshot: "Descargar captura",
    includeOverlay: "Incluir superposición en la captura",
    reset: "Restablecer ajustes",
    next: "Siguiente filtro",
    previous: "Filtro anterior",
    active: "Activo",
  },
  toast: {
    filterChanged: "Filtro",
    snapshotSaved: "Captura descargada",
    snapshotTray: "Captura en la bandeja",
    snapshotFailed: "No se pudo guardar la captura",
    overlayOn: "Superposición activada",
    overlayOff: "Superposición desactivada",
    frozenOn: "Imagen congelada",
    frozenOff: "Imagen en directo",
    languageChanged: "Idioma: Español",
    settingsReset: "Ajustes restablecidos",
    gesture: "Gesto detectado",
  },
  gallery: {
    title: "Galería de filtros",
    subtitle: "21 efectos escritos como fragment shaders. Pulsa cualquiera para aplicarlo a la demo.",
    animated: "Animado",
    mask: "Usa segmentación",
    applied: "Aplicado",
  },
  gestureGuide: {
    title: "Chuleta de gestos",
    subtitle:
      "Cada gesto se clasifica con geometría pura: curvatura de los dedos normalizada por el tamaño de la mano.",
    columns: { emoji: "Gesto", name: "Nombre", action: "Qué hace" },
    note: "Los deslizamientos se detectan por desplazamiento rápido y recto del centro de la mano. Los gestos de control tienen 1 s de enfriamiento para no dispararse en bucle.",
    dynamicTitle: "Gestos dinámicos",
  },
  expressions: {
    title: "Expresiones reconocidas",
    subtitle:
      "Cada expresión es una regla sobre los 52 blendshapes de ARKit, con suavizado exponencial y voto por mayoría para que la etiqueta no parpadee.",
    columns: { emoji: "Expresión", name: "Nombre", what: "Cómo se detecta" },
    note: "El vector de blendshapes siempre se consulta por categoryName, nunca por índice: el orden no está garantizado entre versiones del modelo.",
  },
  shortcuts: {
    title: "Atajos de teclado",
    subtitle: "Funcionan cuando la demo tiene el foco y la cámara está encendida.",
    columns: { keys: "Teclas", action: "Acción" },
    rows: [
      { keys: "N / →", action: "Siguiente filtro" },
      { keys: "P / ←", action: "Filtro anterior" },
      { keys: "1 … 9", action: "Elegir filtro por posición" },
      { keys: "S", action: "Guardar una captura PNG" },
      { keys: "F", action: "Congelar o reanudar la imagen" },
      { keys: "O", action: "Mostrar u ocultar la superposición" },
      { keys: "L", action: "Depurar índices de landmarks" },
      { keys: "H", action: "Mostrar u ocultar el panel de estadísticas" },
      { keys: "M", action: "Activar o desactivar la vista espejo" },
      { keys: "T", action: "Cambiar entre español e inglés" },
      { keys: "R", action: "Restablecer los ajustes" },
    ],
  },
  footer: {
    tagline:
      "MirrorLab es software libre (MIT). La aplicación de escritorio publica la cámara virtual; esta página es una demo en el navegador.",
    repo: "Ver el repositorio en GitHub",
    license: "Licencia MIT",
    privacy: "Privacidad: el vídeo nunca sale del navegador.",
    built: "Hecho con Vite, React y MediaPipe Tasks Vision.",
    createdBy: "Creado por",
    author: "TrinaxCode",
    stats: {
      label: "Estadísticas anónimas de visitas",
      on: "Activadas",
      off: "Desactivadas",
      hint: "Solo páginas vistas y clics en descargar, con Firebase Analytics. Nunca vídeo ni imágenes.",
      refused: "Tu navegador pide no ser rastreado, así que no se activan.",
      failed: "No se pudieron cargar (¿un bloqueador?). La web funciona igual.",
    },
  },
  common: {
    on: "Sí",
    off: "No",
    close: "Cerrar",
    loading: "Cargando…",
    none: "ninguno",
  },
};

export type Dict = typeof es;

const en: Dict = {
  code: "en",
  htmlLang: "en",
  name: "English",
  other: "Español",
  switchLabel: "Switch to Spanish",
  seo: {
    title: "MirrorLab · Virtual camera with gestures for Windows, macOS, Linux",
    description:
      "A free virtual camera for Zoom, Meet and Teams: it blurs your background, keeps you framed, fixes your lighting and is controlled with hand gestures. It runs on your machine and uploads no video. For Windows, macOS and Linux.",
    ogTitle: "MirrorLab: cover the camera with an open palm",
    ogDescription:
      "Background blur, auto-framing and gesture control for your video calls. Free, open source and private.",
    ogLocale: "en_US",
    keywords:
      "virtual camera, blur background video call, auto framing, gesture control, Zoom, Google Meet, Microsoft Teams, OBS, webcam, privacy, open source",
  },
  nav: {
    demo: "Demo",
    features: "Features",
    control: "Gestures",
    download: "Download",
    install: "Install",
    filters: "Filters",
    gestures: "Gestures",
    expressions: "Expressions",
    shortcuts: "Shortcuts",
    reference: "Reference",
    repo: "GitHub",
  },
  hero: {
    title: "Close the camera with an open hand.",
    kicker: "A virtual camera you control with gestures",
    pitch:
      "MirrorLab is a virtual camera for Zoom, Meet and Teams. It blurs your background, keeps you framed and is driven by your hands, so you never hunt for the keyboard mid-meeting.",
    ctaPrimary: "Download the app",
    ctaSecondary: "Try it in the browser",
    platforms: "Windows · macOS · Linux · free and open source",
    commandLabel: "How it starts",
    copy: "Copy",
    copied: "Copied",
    caption: "Hold your palm for 1.6 seconds to cover the camera. Again to open it.",
    monitor: {
      label: "Animated MirrorLab preview: blurred background, framing and a palm covering the camera",
      live: "Live",
      covered: "Camera covered",
      hold: "Palm · 1.6 s",
      source: "MirrorLab Virtual Camera",
      blur: "Blurred background",
      frame: "Framing",
      light: "Light",
    },
  },
  features: {
    title: "What it does",
    subtitle:
      "Four adjustments for what usually goes wrong on a video call, and a shutter for when you need to disappear.",
    items: [
      {
        name: "Background",
        body: "Blur, an image of your own, green screen or black. The person mask is smoothed over time so the outline does not shimmer.",
        readout: "blur · replace · green · black",
      },
      {
        name: "Framing",
        body: "A smooth pan and zoom keep your face in the upper third. It ignores small movements and eases back to the full frame when you stand up.",
        readout: "zoom up to 1.8×",
      },
      {
        name: "Light",
        body: "Exposure is metered on your face, not on the whole picture, so a window behind you no longer leaves you dark.",
        readout: "metered on the face",
      },
      {
        name: "Shutter",
        body: "Cover the picture whenever you want, with a gesture, or automatically after a few seconds with nobody in front.",
        readout: "palm · ctl privacy · --away-after",
      },
      {
        name: "Reactions",
        body: "A thumbs up, a heart or an ok float over your picture for everyone else on the call.",
        readout: "thumb · heart · ok",
      },
    ],
  },
  control: {
    title: "Driven by your hands",
    subtitle:
      "Every gesture has to be held for a moment before it acts. One you make while talking triggers nothing.",
    holdUnit: "s",
    holdLabel: "How long to hold it",
    rows: [
      { emoji: "🖐️", gesture: "Open palm", hold: 1.6, action: "Covers or uncovers the camera" },
      { emoji: "✌️", gesture: "Peace", hold: 1.0, action: "Switches to the next background" },
      { emoji: "👍", gesture: "Thumbs up", hold: 0.6, action: "Floats a thumbs up over your picture" },
      { emoji: "🤟", gesture: "I love you", hold: 0.6, action: "Floats a heart" },
      { emoji: "👌", gesture: "OK", hold: 0.6, action: "Floats an ok" },
    ],
    alt: "Hands busy? mirrorlab ctl privacy from another terminal, or from a keyboard shortcut, does the same as the palm.",
  },
  privacy: {
    title: "What leaves your machine",
    subtitle: "Almost nothing. This is everything that happens on the network.",
    facts: [
      {
        title: "Video is never uploaded",
        body: "The camera is read in your browser and processed on your CPU or GPU. No server receives the picture.",
      },
      {
        title: "Models download once",
        body: "About 11 MB from the MediaPipe CDN, only when you turn the camera on. Your browser caches them.",
      },
      {
        title: "Snapshots do not download themselves",
        body: "They stay in the page's tray until you press Download.",
      },
      {
        title: "No accounts, no tracking",
        body: "This page asks for no sign-up and sets no tracking cookies. If you like, you can turn on anonymous visit statistics from the footer; they are off by default.",
      },
    ],
  },
  download: {
    title: "Download the app",
    subtitle:
      "An app for Windows, macOS and Linux, with a window, a live preview and every control. It installs like any other.",
    recommended: "Recommended for your system",
    cta: "Download for {os}",
    allReleases: "All versions and checksums",
    platforms: [
      {
        id: "windows",
        name: "Windows",
        file: ".exe installer or portable ZIP",
        requirements: "Windows 10 or later, 64-bit",
        note: "To use it in Zoom, Meet or Teams, install OBS Studio: it provides the “OBS Virtual Camera” device.",
      },
      {
        id: "macos",
        name: "macOS",
        file: ".dmg disk image",
        requirements: "macOS 12 or later, Apple silicon",
        note: "The app is not notarised: the first time, right-click › Open. It needs OBS Studio for the virtual camera.",
      },
      {
        id: "linux",
        name: "Linux",
        file: ".deb package or .tar.gz archive",
        requirements: "Ubuntu 22.04 or equivalent, 64-bit",
        note: "For the virtual camera install v4l2loopback: sudo apt install v4l2loopback-dkms.",
      },
    ],
    steps: [
      { title: "Download and install", body: "Open the file for your system and follow the installer." },
      { title: "Turn the camera on", body: "Press “Turn camera on” and pick a background. The app tells you if anything is missing." },
      { title: "Pick it in your call", body: "In Zoom, Meet or Teams, choose “MirrorLab” as your camera." },
    ],
    license:
      "The code is MIT. The installers bundle pyvirtualcam (GPL-2.0), so the binaries are distributed under GPL-2.0.",
    screenshot: {
      src: "/screenshots/desktop-app.png",
      alt: "The MirrorLab desktop window: the camera preview on the left and, on the right, the background, framing, light, gesture and reaction controls.",
      caption: "The desktop app: a live preview and every control.",
    },
  },
  faq: {
    title: "Frequently asked questions",
    subtitle: "What people usually ask before installing it.",
    items: [
      {
        q: "Does MirrorLab upload my video anywhere?",
        a: "No. The camera is read and processed on your machine, on the CPU. The only download is about 12 MB of vision models the first time, and the models are checked against a SHA-256 hash.",
      },
      {
        q: "Does it work with Zoom, Google Meet and Microsoft Teams?",
        a: "Yes. MirrorLab publishes a virtual camera that any video-call app can select, and so can OBS, Discord and the browser.",
      },
      {
        q: "Do I need an NVIDIA graphics card?",
        a: "No. Everything runs on the CPU, on Windows, macOS and Linux. On a mid-range laptop it holds 30 frames per second.",
      },
      {
        q: "Why is OBS or v4l2loopback needed?",
        a: "The operating system needs a virtual camera device and an app cannot create one by itself. On Windows and macOS OBS Studio provides it; on Linux, the v4l2loopback module does. The app tells you what is missing.",
      },
      {
        q: "How do I control it without touching the keyboard?",
        a: "With hand gestures held for a moment: an open palm covers the camera, a peace sign changes the background, and a thumb, heart or OK sign throws a reaction. There is also a command, mirrorlab ctl, that you can bind to a hotkey.",
      },
      {
        q: "Is it free? Who made it?",
        a: "It is free and open source (MIT). It was created by TrinaxCode and the code is at github.com/TrinaxCode/mirrorlab.",
      },
    ],
  },
  install: {
    title: "Or install it with Python",
    subtitle:
      "Python 3.9 to 3.12, CPU only. Windows and macOS need OBS to provide a camera device; Linux uses v4l2loopback.",
    tabsLabel: "Operating system",
    copy: "Copy",
    copied: "Copied",
    notOnPypi: "Not on PyPI yet: install it from source.",
    docs: "Full virtual camera guide",
    platforms: [
      {
        id: "linux",
        name: "Linux",
        steps: [
          { title: "Create the camera device", code: "sudo apt install v4l2loopback-dkms libegl1 libgles2\nsudo modprobe v4l2loopback devices=1 video_nr=10 card_label=\"MirrorLab\" exclusive_caps=1" },
          { title: "Install MirrorLab", code: "git clone https://github.com/TrinaxCode/mirrorlab.git && cd mirrorlab\npython3 -m venv .venv && source .venv/bin/activate\npip install -e \".[vcam]\"" },
          { title: "Check and start", code: "mirrorlab doctor\nmirrorlab cam --profile meeting --device /dev/video10" },
        ],
      },
      {
        id: "macos",
        name: "macOS",
        steps: [
          { title: "Set up OBS once", body: "Install OBS Studio 30 or later, open it, click “Start Virtual Camera”, then “Stop”, and quit." },
          { title: "Install MirrorLab", code: "git clone https://github.com/TrinaxCode/mirrorlab.git && cd mirrorlab\npython3 -m venv .venv && source .venv/bin/activate\npip install -e \".[vcam]\"" },
          { title: "Check and start", code: "mirrorlab doctor\nmirrorlab cam --profile meeting", body: "Your terminal needs camera permission. Keep OBS closed while MirrorLab runs." },
        ],
      },
      {
        id: "windows",
        name: "Windows",
        steps: [
          { title: "Install OBS Studio", body: "Its installer registers the “OBS Virtual Camera” device." },
          { title: "Install MirrorLab", code: "git clone https://github.com/TrinaxCode/mirrorlab.git\ncd mirrorlab\npy -m venv .venv\n.venv\\Scripts\\activate\npip install -e \".[vcam]\"" },
          { title: "Check and start", code: "mirrorlab doctor\nmirrorlab cam --profile meeting", body: "Do not run OBS's own virtual camera at the same time." },
        ],
      },
    ],
  },
  reference: {
    title: "Demo reference",
    subtitle: "Every gesture, expression and shortcut the browser demo recognises.",
    show: "Show",
    hide: "Hide",
  },
  tray: {
    title: "Snapshots",
    empty: "Snapshots taken with a gesture are kept here. Nothing downloads on its own.",
    download: "Download",
    discard: "Discard",
    clear: "Clear tray",
    alt: "Snapshot taken at",
  },
  demo: {
    invite: "The models (about 11 MB) download only when you turn the camera on, and stay in your browser cache.",
    title: "Try it in the browser",
    subtitle:
      "The same face and hand detection the desktop version uses, plus 21 WebGL filters. The virtual camera needs the desktop app: here you only see yourself.",
    start: "Turn camera on",
    retry: "Try again",
    stop: "Turn camera off",
    cameraLabel: "Camera",
    loadingVideo: "Warming up the camera…",
    loadingModels: "Loading the vision models (~11 MB the first time)…",
    modelProgress: "Downloading model",
    frozenBadge: "FROZEN",
    mirrorBadge: "MIRROR",
    overlayHidden: "Overlay hidden",
    handsBadge: "hands",
  },
  camera: {
    insecureTitle: "You need a secure connection (HTTPS)",
    insecureBody:
      "Browsers only hand over the camera in secure contexts. Open this page over HTTPS or on localhost (http://localhost:5173) and try again.",
    deniedTitle: "Camera permission denied",
    deniedBody:
      "You blocked camera access for this site. Click the camera icon in the address bar, choose “Allow” and try again.",
    notFoundTitle: "No camera was found",
    notFoundBody: "Plug in a webcam (or check that another app is not using it) and try again.",
    unsupportedTitle: "This browser has no camera API",
    unsupportedBody: "Try a recent version of desktop Chrome, Edge, Firefox or Safari.",
    unknownTitle: "The camera could not be opened",
    unknownBody: "Something went wrong while starting the video. Retry or pick another camera.",
    hint: "Tip: the models are fetched from the MediaPipe CDN and cached by your browser.",
    detail: "Technical detail",
  },
  webgl: {
    title: "Your browser cannot create a WebGL2 context",
    body: "The filters need WebGL2. Enable hardware acceleration or try another browser. The page still works, just without filters.",
  },
  vision: {
    loading: "Loading models",
    ready: "Models ready",
    errorTitle: "The MediaPipe models could not be loaded",
    errorBody:
      "Usually a network hiccup or a blocker. Check your connection and retry: the models come from cdn.jsdelivr.net and storage.googleapis.com.",
    retry: "Retry loading",
    face: "Face",
    hands: "Hands",
    segmenter: "Segmenter",
  },
  hud: {
    title: "Live panel",
    fps: "FPS",
    inference: "Inference",
    hands: "Hands",
    filter: "Filter",
    expression: "Expression",
    gesture: "Gesture",
    top3: "Top 3 expressions",
    noHand: "no hand",
    noFace: "no face",
    paused: "paused",
    waiting: "waiting…",
  },
  controls: {
    title: "Controls",
    overlays: "Overlay",
    landmarks: "Landmark indices",
    hud: "Stats panel",
    freeze: "Freeze frame",
    mirror: "Mirror view",
    snapshot: "Download snapshot",
    includeOverlay: "Include overlay in the snapshot",
    reset: "Reset settings",
    next: "Next filter",
    previous: "Previous filter",
    active: "Active",
  },
  toast: {
    filterChanged: "Filter",
    snapshotSaved: "Snapshot downloaded",
    snapshotTray: "Snapshot in the tray",
    snapshotFailed: "The snapshot could not be saved",
    overlayOn: "Overlay on",
    overlayOff: "Overlay off",
    frozenOn: "Frame frozen",
    frozenOff: "Back to live",
    languageChanged: "Language: English",
    settingsReset: "Settings reset",
    gesture: "Gesture detected",
  },
  gallery: {
    title: "Filter gallery",
    subtitle: "21 effects written as fragment shaders. Click any of them to apply it to the demo.",
    animated: "Animated",
    mask: "Uses segmentation",
    applied: "Applied",
  },
  gestureGuide: {
    title: "Gesture cheat-sheet",
    subtitle:
      "Every gesture is classified with pure geometry: finger curl normalised by hand size.",
    columns: { emoji: "Gesture", name: "Name", action: "What it does" },
    note: "Swipes are detected from a fast, straight displacement of the hand centre. Control gestures have a 1 s cooldown so they never machine-gun.",
    dynamicTitle: "Dynamic gestures",
  },
  expressions: {
    title: "Recognised expressions",
    subtitle:
      "Each expression is a rule over the 52 ARKit blendshapes, with exponential smoothing and a majority vote so the label never flickers.",
    columns: { emoji: "Expression", name: "Name", what: "How it is detected" },
    note: "The blendshape vector is always looked up by categoryName, never by index: the order is not guaranteed across model versions.",
  },
  shortcuts: {
    title: "Keyboard shortcuts",
    subtitle: "They work while the demo has focus and the camera is running.",
    columns: { keys: "Keys", action: "Action" },
    rows: [
      { keys: "N / →", action: "Next filter" },
      { keys: "P / ←", action: "Previous filter" },
      { keys: "1 … 9", action: "Pick a filter by position" },
      { keys: "S", action: "Save a PNG snapshot" },
      { keys: "F", action: "Freeze or resume the frame" },
      { keys: "O", action: "Show or hide the overlay" },
      { keys: "L", action: "Debug landmark indices" },
      { keys: "H", action: "Show or hide the stats panel" },
      { keys: "M", action: "Toggle the mirror view" },
      { keys: "T", action: "Switch between Spanish and English" },
      { keys: "R", action: "Reset settings" },
    ],
  },
  footer: {
    tagline:
      "MirrorLab is free software (MIT). The desktop app publishes the virtual camera; this page is a browser demo.",
    repo: "View the repository on GitHub",
    license: "MIT licensed",
    privacy: "Privacy: the video never leaves the browser.",
    createdBy: "Created by",
    author: "TrinaxCode",
    stats: {
      label: "Anonymous visit statistics",
      on: "On",
      off: "Off",
      hint: "Only page views and download clicks, with Firebase Analytics. Never video or images.",
      refused: "Your browser asks not to be tracked, so they stay off.",
      failed: "They could not load (a blocker?). The site works the same.",
    },
    built: "Built with Vite, React and MediaPipe Tasks Vision.",
  },
  common: {
    on: "Yes",
    off: "No",
    close: "Close",
    loading: "Loading…",
    none: "none",
  },
};

export const STRINGS: Record<Lang, Dict> = { es, en };

/** Normalise anything that came out of `localStorage` into a supported language. */
export function coerceLang(value: unknown): Lang {
  return value === "en" ? "en" : "es";
}

/** `/en/` serves English; every other path is the Spanish page. `null` when the path says nothing. */
export function langFromPath(pathname: string = typeof window === "undefined" ? "/" : window.location.pathname): Lang | null {
  return /^\/en(\/|$)/.test(pathname) ? "en" : null;
}

/** The URL that serves a language: `/` for Spanish, `/en/` for English. */
export function pathForLang(lang: Lang): string {
  return lang === "en" ? "/en/" : "/";
}

export function nextLang(current: Lang): Lang {
  return current === "es" ? "en" : "es";
}
