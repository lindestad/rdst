import ReactDOM from "react-dom/client";

import App from "./App";
import "./index.css";

// StrictMode is intentionally off: MapLibre's imperative setup doesn't survive
// the dev-only double-mount without extra guarding, and a fresh map each
// re-mount slows HMR noticeably.
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
