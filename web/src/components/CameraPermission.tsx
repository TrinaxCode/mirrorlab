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
      return { emoji: "🎥", title: strings.demo.start, body: strings.demo.invite };
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
    <div className="animate-in w-full max-w-md p-2 text-center text-screen-ink">
      <span className="mx-auto grid h-14 w-14 place-items-center rounded-full border border-screen-line text-2xl">
        {copy.emoji}
      </span>
      <h3 className="heading mt-4 text-3xl">{copy.title}</h3>
      <p className="mx-auto mt-2 max-w-[40ch] text-base leading-relaxed text-screen-soft">{copy.body}</p>

      {canPickDevice ? (
        <label className="mx-auto mt-5 flex max-w-xs items-center gap-3 text-left text-sm text-screen-soft">
          <span className="shrink-0">{strings.demo.cameraLabel}</span>
          <select
            value={deviceId ?? ""}
            onChange={(event) => onSelectDevice(event.target.value)}
            className="min-h-10 w-full rounded-lg border border-screen-line bg-screen-raised px-2 text-sm text-screen-ink"
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
          className="btn btn-primary disabled:cursor-wait disabled:opacity-70"
        >
          {starting ? strings.common.loading : error ? strings.demo.retry : strings.demo.start}
        </button>
      </div>

      {error ? <p className="mt-4 text-sm text-screen-soft">{strings.camera.hint}</p> : null}

      {detail ? (
        <details className="mt-3 text-left">
          <summary className="cursor-pointer text-sm text-screen-soft hover:text-screen-ink">
            {strings.camera.detail}
          </summary>
          <pre className="mt-2 overflow-x-auto rounded-lg bg-black/50 p-2 text-xs text-screen-soft">
            {detail}
          </pre>
        </details>
      ) : null}
    </div>
  );
}
