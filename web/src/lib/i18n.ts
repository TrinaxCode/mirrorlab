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
  nav: {
    demo: "Demo",
    filters: "Filtros",
    gestures: "Gestos",
    expressions: "Expresiones",
    shortcuts: "Atajos",
    repo: "GitHub",
  },
  hero: {
    badge: "Sin servidor · tu cámara nunca sale del navegador",
    title: "MirrorLab",
    kicker: "Laboratorio de visión en el navegador",
    pitch: "Lee tu cara y tus manos con la webcam y los convierte en filtros en tiempo real. 52 blendshapes faciales, 21 puntos por mano y 21 filtros WebGL ejecutándose en tu dispositivo.",
    ctaPrimary: "Abrir la demo",
    ctaSecondary: "Ver cómo funciona",
    stats: [
      { value: "52", label: "blendshapes" },
      { value: "21", label: "gestos" },
      { value: "21", label: "filtros WebGL" },
      { value: "0", label: "peticiones al servidor" },
    ],
  },
  demo: {
    title: "La demo",
    subtitle:
      "Enciende la cámara y mueve las manos: los gestos controlan la interfaz. Nada se sube a ningún sitio, todo el procesamiento ocurre en tu equipo.",
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
    snapshot: "Guardar captura",
    includeOverlay: "Incluir superposición en la captura",
    reset: "Restablecer ajustes",
    next: "Siguiente filtro",
    previous: "Filtro anterior",
    active: "Activo",
  },
  toast: {
    filterChanged: "Filtro",
    snapshotSaved: "Captura guardada",
    snapshotFailed: "No se pudo guardar la captura",
    overlayOn: "Superposición activada",
    overlayOff: "Superposición desactivada",
    frozenOn: "Imagen congelada",
    frozenOff: "Imagen en directo",
    languageChanged: "Idioma: Español",
    settingsReset: "Ajustes restablecidos",
    gesture: "Gesto detectado",
  },
  how: {
    title: "Cómo funciona",
    subtitle: "Tres pasos, cero servidores. El navegador hace todo el trabajo pesado.",
    steps: [
      {
        emoji: "🎥",
        title: "1. Captura el fotograma",
        body: "getUserMedia entrega el vídeo a un <video> oculto. Cada fotograma se sube a la GPU como textura, sin copiarlo a JavaScript.",
      },
      {
        emoji: "🧠",
        title: "2. Infiere con MediaPipe",
        body: "FaceLandmarker devuelve 478 puntos y 52 blendshapes; HandLandmarker, 21 puntos por mano. Los clasificadores geométricos convierten eso en expresiones y gestos.",
      },
      {
        emoji: "🎨",
        title: "3. Dibuja el resultado",
        body: "Un shader WebGL2 compone el filtro activo en el canvas inferior y un canvas 2D transparente dibuja encima el esqueleto, el rostro y el HUD.",
      },
    ],
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
      "MirrorLab es software libre: el mismo motor de expresiones, gestos y filtros vive también en una aplicación de escritorio en Python.",
    repo: "Ver el repositorio en GitHub",
    license: "Licencia MIT",
    privacy: "Privacidad: el vídeo nunca sale del navegador.",
    built: "Hecho con Vite, React y MediaPipe Tasks Vision.",
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
  nav: {
    demo: "Demo",
    filters: "Filters",
    gestures: "Gestures",
    expressions: "Expressions",
    shortcuts: "Shortcuts",
    repo: "GitHub",
  },
  hero: {
    badge: "No server · your camera never leaves the browser",
    title: "MirrorLab",
    kicker: "A computer-vision lab in your browser",
    pitch: "Reads your face and hands from the webcam and turns them into real-time filters. 52 facial blendshapes, 21 points per hand and 21 WebGL filters running on your own device.",
    ctaPrimary: "Open the demo",
    ctaSecondary: "See how it works",
    stats: [
      { value: "52", label: "blendshapes" },
      { value: "21", label: "gestures" },
      { value: "21", label: "WebGL filters" },
      { value: "0", label: "server round-trips" },
    ],
  },
  demo: {
    title: "The demo",
    subtitle:
      "Turn the camera on and move your hands: gestures drive the interface. Nothing is uploaded anywhere, all processing happens on your machine.",
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
    snapshot: "Save snapshot",
    includeOverlay: "Include overlay in the snapshot",
    reset: "Reset settings",
    next: "Next filter",
    previous: "Previous filter",
    active: "Active",
  },
  toast: {
    filterChanged: "Filter",
    snapshotSaved: "Snapshot saved",
    snapshotFailed: "The snapshot could not be saved",
    overlayOn: "Overlay on",
    overlayOff: "Overlay off",
    frozenOn: "Frame frozen",
    frozenOff: "Back to live",
    languageChanged: "Language: English",
    settingsReset: "Settings reset",
    gesture: "Gesture detected",
  },
  how: {
    title: "How it works",
    subtitle: "Three steps, zero servers. The browser does all the heavy lifting.",
    steps: [
      {
        emoji: "🎥",
        title: "1. Grab the frame",
        body: "getUserMedia feeds a hidden <video>. Every frame is uploaded to the GPU as a texture, never copied into JavaScript.",
      },
      {
        emoji: "🧠",
        title: "2. Infer with MediaPipe",
        body: "FaceLandmarker returns 478 points plus 52 blendshapes; HandLandmarker returns 21 points per hand. Geometric classifiers turn that into expressions and gestures.",
      },
      {
        emoji: "🎨",
        title: "3. Draw the result",
        body: "A WebGL2 shader composites the active filter on the bottom canvas while a transparent 2D canvas draws the skeleton, the face mesh and the HUD on top.",
      },
    ],
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
      "MirrorLab is free software: the same expression, gesture and filter engine also lives in a Python desktop application.",
    repo: "View the repository on GitHub",
    license: "MIT licensed",
    privacy: "Privacy: the video never leaves the browser.",
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

export function nextLang(current: Lang): Lang {
  return current === "es" ? "en" : "es";
}
