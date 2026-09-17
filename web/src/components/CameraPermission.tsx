import type { CameraDevice, CameraErrorKind } from "../hooks/useCamera";
import type { Dict } from "../lib/i18n";

export interface CameraPermissionProps {
  strings: Dict;
  /** `null` while the camera has never been requested — shows the invite state. */
  error: CameraErrorKind | null;
  detail: string;
  devices: CameraDevice[];
  deviceId: string | null;
  starting: boolean;
  onStart: () => void;
  onSelectDevice: (deviceId: string) => void;
}

interface Copy {
  emoji: string;
  title: string;
  body: string;
}

function copyFor(strings: Dict, error: CameraErrorKind | null): Copy {
  switch (error) {
    case "insecure":
      return { emoji: "🔒", title: strings.camera.insecureTitle, body: strings.camera.insecureBody };
    case "denied":
      return { emoji: "🚫", title: strings.camera.deniedTitle, body: strings.camera.deniedBody };
    case "notfound":
    case "inuse":
      return { emoji: "📷", title: strings.camera.notFoundTitle, body: strings.camera.notFoundBody };
    case "unsupported":
      return {
        emoji: "🧭",
        title: strings.camera.unsupportedTitle,
        body: strings.camera.unsupportedBody,
      };
    case "overconstrained":
    case "unknown":
      return { emoji: "⚠️", title: strings.camera.unknownTitle, body: strings.camera.unknownBody };
    default:
      return { emoji: "🎥", title: strings.demo.start, body: strings.demo.subtitle };
  }
}

/**
 * The panel shown over the stage whenever there is no live picture: the initial
 * invitation, or a specific explanation of what went wrong and how to fix it.
 */
export function CameraPermission(props: CameraPermissionProps) {
  const { strings, error, detail, devices, deviceId, starting, onStart, onSelectDevice } = props;
  const copy = copyFor(strings, error);
  const canPickDevice = devices.length > 1;

  return (
    <div className="animate-in w-full max-w-lg rounded-2xl border border-white/10 bg-ink-900/90 p-6 text-center shadow-2xl shadow-black/40 backdrop-blur">
      <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-white/10 bg-white/[0.04] text-2xl">
        {copy.emoji}
      </span>
      <h3 className="mt-4 text-lg font-semibold text-white">{copy.title}</h3>
      <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-slate-400">{copy.body}</p>

      {canPickDevice ? (
        <label className="mx-auto mt-5 flex max-w-xs items-center gap-3 text-left text-xs text-slate-400">
          <span className="shrink-0 uppercase tracking-wider">{strings.demo.cameraLabel}</span>
          <select
            value={deviceId ?? ""}
            onChange={(event) => onSelectDevice(event.target.value)}
            className="w-full rounded-lg border border-white/10 bg-ink-800 px-2 py-1.5 text-sm text-slate-200 outline-none"
          >
            {devices.map((device) => (
              <option key={device.deviceId} value={device.deviceId}>
                {device.label}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onClick={onStart}
          disabled={starting}
          className="inline-flex items-center gap-2 rounded-xl accent-gradient px-5 py-2.5 text-sm font-semibold text-ink-950 transition-transform hover:-translate-y-0.5 disabled:cursor-wait disabled:opacity-70"
        >
          {starting ? strings.common.loading : error ? strings.demo.retry : strings.demo.start}
        </button>
      </div>

      <p className="mt-4 text-xs text-slate-500">{strings.camera.hint}</p>

      {detail ? (
        <details className="mt-3 text-left">
          <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-300">
            {strings.camera.detail}
          </summary>
          <pre className="mt-2 overflow-x-auto rounded-lg border border-white/5 bg-black/40 p-2 font-mono text-[11px] text-slate-400">
            {detail}
          </pre>
        </details>
      ) : null}
    </div>
  );
}
