import { createRoot } from "react-dom/client";

import App from "./App";
import "./index.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("MirrorLab: #root container is missing from index.html");
}

// Note: no <StrictMode>. Its development-only double mount would create two
// MediaPipe engines and two WebGL2 contexts, and both own heavyweight WASM/GPU
// resources. All effects here are written with proper cleanup regardless.
createRoot(container).render(<App />);
