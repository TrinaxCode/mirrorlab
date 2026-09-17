/**
 * Webcam access: permissions, device enumeration and a friendly error model.
 *
 * Every failure mode the browser can produce is mapped to a specific, bilingual
 * message (see `CameraPermission`), because "NotAllowedError" is not something a
 * visitor should ever have to read.
 */

import { useCallback, useEffect, useRef, useState } from "react";

export type CameraErrorKind =
  | "insecure"
  | "unsupported"
  | "denied"
  | "notfound"
  | "inuse"
  | "overconstrained"
  | "unknown";

export type CameraStatus = "idle" | "starting" | "live" | "error";

export interface CameraDevice {
  deviceId: string;
  label: string;
}

export interface UseCameraResult {
  status: CameraStatus;
  error: CameraErrorKind | null;
  /** Raw browser message, shown behind a "technical detail" disclosure. */
  detail: string;
  devices: CameraDevice[];
  deviceId: string | null;
  start: (deviceId?: string) => Promise<void>;
  stop: () => void;
  selectDevice: (deviceId: string) => void;
}

function classifyError(error: unknown): { kind: CameraErrorKind; detail: string } {
  const name = error instanceof Error ? error.name : "";
  const detail = error instanceof Error ? error.message : String(error);
  switch (name) {
    case "NotAllowedError":
    case "SecurityError":
      return { kind: "denied", detail };
    case "NotFoundError":
    case "DevicesNotFoundError":
      return { kind: "notfound", detail };
    case "NotReadableError":
    case "TrackStartError":
      return { kind: "inuse", detail };
    case "OverconstrainedError":
    case "ConstraintNotSatisfiedError":
      return { kind: "overconstrained", detail };
    default:
      return { kind: "unknown", detail };
  }
}

function listDevices(): Promise<CameraDevice[]> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.enumerateDevices) {
    return Promise.resolve([]);
  }
  return navigator.mediaDevices
    .enumerateDevices()
    .then((devices) =>
      devices
        .filter((device) => device.kind === "videoinput")
        .map((device, index) => ({
          deviceId: device.deviceId,
          label: device.label || `Camera ${index + 1}`,
        })),
    )
    .catch(() => []);
}

export function useCamera(videoRef: React.RefObject<HTMLVideoElement | null>): UseCameraResult {
  const [status, setStatus] = useState<CameraStatus>("idle");
  const [error, setError] = useState<CameraErrorKind | null>(null);
  const [detail, setDetail] = useState("");
  const [devices, setDevices] = useState<CameraDevice[]>([]);
  const [deviceId, setDeviceId] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const mountedRef = useRef(true);

  const stop = useCallback(() => {
    const stream = streamRef.current;
    streamRef.current = null;
    if (stream) for (const track of stream.getTracks()) track.stop();
    const video = videoRef.current;
    if (video) {
      video.pause();
      video.srcObject = null;
    }
    if (mountedRef.current) setStatus("idle");
  }, [videoRef]);

  const start = useCallback(
    async (requestedId?: string) => {
      const video = videoRef.current;
      if (!video) return;

      // A page served over plain HTTP is not a secure context, and the browser
      // will refuse the camera without ever asking the user.
      if (typeof window !== "undefined" && window.isSecureContext === false) {
        setError("insecure");
        setDetail("");
        setStatus("error");
        return;
      }
      if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
        setError("unsupported");
        setDetail("");
        setStatus("error");
        return;
      }

      setStatus("starting");
      setError(null);
      setDetail("");

      // Release a previous stream first: two open tracks on the same camera
      // would fail with NotReadableError on most systems.
      const previous = streamRef.current;
      if (previous) {
        streamRef.current = null;
        for (const track of previous.getTracks()) track.stop();
      }

      const target = requestedId ?? deviceId ?? undefined;
      const constraints: MediaStreamConstraints = {
        audio: false,
        video: target
          ? { width: 1280, height: 720, deviceId: { exact: target } }
          : { width: 1280, height: 720, facingMode: "user" },
      };

      try {
        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        if (!mountedRef.current) {
          for (const track of stream.getTracks()) track.stop();
          return;
        }
        streamRef.current = stream;
        video.srcObject = stream;
        video.muted = true;
        video.playsInline = true;
        await video.play().catch(() => undefined);
        const settings = stream.getVideoTracks()[0]?.getSettings();
        if (settings?.deviceId) setDeviceId(settings.deviceId);
        const available = await listDevices();
        if (!mountedRef.current) return;
        setDevices(available);
        setStatus("live");
      } catch (caught) {
        if (!mountedRef.current) return;
        const classified = classifyError(caught);
        streamRef.current = null;
        setError(classified.kind);
        setDetail(classified.detail);
        setStatus("error");
        // Labels are only exposed after a grant, but the count still helps.
        void listDevices().then((available) => {
          if (mountedRef.current) setDevices(available);
        });
      }
    },
    [deviceId, videoRef],
  );

  const selectDevice = useCallback(
    (next: string) => {
      setDeviceId(next);
      void start(next);
    },
    [start],
  );

  useEffect(() => {
    mountedRef.current = true;
    const video = videoRef.current;
    void listDevices().then((available) => {
      if (mountedRef.current) setDevices(available);
    });

    const onDeviceChange = () => {
      void listDevices().then((available) => {
        if (mountedRef.current) setDevices(available);
      });
    };
    navigator.mediaDevices?.addEventListener?.("devicechange", onDeviceChange);

    return () => {
      mountedRef.current = false;
      navigator.mediaDevices?.removeEventListener?.("devicechange", onDeviceChange);
      const stream = streamRef.current;
      streamRef.current = null;
      if (stream) for (const track of stream.getTracks()) track.stop();
      if (video) {
        video.pause();
        video.srcObject = null;
      }
    };
  }, [videoRef]);

  return { status, error, detail, devices, deviceId, start, stop, selectDevice };
}
