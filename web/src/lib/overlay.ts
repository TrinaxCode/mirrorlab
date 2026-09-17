/**
 * The transparent 2-D canvas that sits on top of the WebGL filter canvas:
 * hand skeletons, face landmarks, badges and the FPS counter.
 *
 * Everything is drawn in *display* space: when the preview is mirrored the
 * normalised `x` is flipped here, once, so text and badges stay readable while
 * the skeleton still lines up with the video.
 */

import type { HandObservation } from "./gestures";

export interface OverlayBadge {
  emoji: string;
  label: string;
  detail?: string;
  /** 0..1 confidence, drawn as a thin progress bar under the text. */
  score?: number;
}

export interface OverlayParams {
  ctx: CanvasRenderingContext2D;
  width: number;
  height: number;
  mirrored: boolean;
  face: readonly { x: number; y: number }[] | null;
  hands: readonly HandObservation[];
  /** Draw landmark indices next to the points. */
  debug: boolean;
  expression: OverlayBadge | null;
  gesture: OverlayBadge | null;
  fps: number;
  frozen: boolean;
}

export const HAND_CONNECTIONS: readonly (readonly [number, number])[] = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 4],
  [0, 5],
  [5, 6],
  [6, 7],
  [7, 8],
  [5, 9],
  [9, 10],
  [10, 11],
  [11, 12],
  [9, 13],
  [13, 14],
  [14, 15],
  [15, 16],
  [13, 17],
  [17, 18],
  [18, 19],
  [19, 20],
  [0, 17],
];

/** Landmarks worth labelling in debug mode — the joints, not all 478 points. */
const FACE_DEBUG_INDICES = [
  1, 10, 33, 61, 133, 152, 159, 145, 263, 291, 334, 362, 386, 13, 14, 468, 473,
];

export const THEME = {
  teal: "#5eead4",
  violet: "#a78bfa",
  ink: "rgba(5, 7, 13, 0.72)",
  border: "rgba(148, 163, 184, 0.35)",
  text: "#e2e8f0",
} as const;

function toPixel(
  point: { x: number; y: number },
  width: number,
  height: number,
  mirrored: boolean,
): [number, number] {
  const x = mirrored ? 1 - point.x : point.x;
  return [x * width, point.y * height];
}

function roundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
): void {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + width - r, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + r);
  ctx.lineTo(x + width, y + height - r);
  ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctx.lineTo(x + r, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

/** Draw a pill and return its width, so callers can stack them. */
function drawBadge(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  badge: OverlayBadge,
  scale: number,
): number {
  const fontSize = Math.round(15 * scale);
  const padding = Math.round(10 * scale);
  ctx.font = `600 ${fontSize}px ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif`;
  const text = `${badge.emoji} ${badge.label}`;
  const textWidth = ctx.measureText(text).width;
  const detailWidth = badge.detail
    ? ctx.measureText(badge.detail).width
    : 0;
  const width = Math.max(textWidth, detailWidth) + padding * 2;
  const height = (badge.detail ? fontSize * 2.5 : fontSize * 1.9) + (badge.score === undefined ? 0 : 5 * scale);

  ctx.fillStyle = THEME.ink;
  ctx.strokeStyle = THEME.border;
  ctx.lineWidth = 1;
  roundedRect(ctx, x, y, width, height, 10 * scale);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = THEME.text;
  ctx.textBaseline = "top";
  ctx.textAlign = "left";
  ctx.fillText(text, x + padding, y + padding * 0.7);

  if (badge.detail) {
    ctx.fillStyle = "rgba(226, 232, 240, 0.65)";
    ctx.font = `500 ${Math.round(fontSize * 0.78)}px ui-sans-serif, system-ui, sans-serif`;
    ctx.fillText(badge.detail, x + padding, y + padding * 0.7 + fontSize * 1.25);
  }

  if (badge.score !== undefined) {
    const barY = y + height - 7 * scale;
    const barWidth = width - padding * 2;
    ctx.fillStyle = "rgba(148, 163, 184, 0.25)";
    roundedRect(ctx, x + padding, barY, barWidth, 4 * scale, 2 * scale);
    ctx.fill();
    const gradient = ctx.createLinearGradient(x + padding, barY, x + padding + barWidth, barY);
    gradient.addColorStop(0, THEME.teal);
    gradient.addColorStop(1, THEME.violet);
    ctx.fillStyle = gradient;
    roundedRect(ctx, x + padding, barY, Math.max(2, barWidth * badge.score), 4 * scale, 2 * scale);
    ctx.fill();
  }

  return width;
}

export function drawOverlay(params: OverlayParams): void {
  const { ctx, width, height, mirrored, face, hands, debug, expression, gesture, fps, frozen } = params;
  ctx.clearRect(0, 0, width, height);
  if (width < 2 || height < 2) return;

  const scale = Math.max(width / 1280, 0.6);
  ctx.save();
  ctx.lineJoin = "round";
  ctx.lineCap = "round";

  // --- face ------------------------------------------------------------- //
  if (face && face.length > 0) {
    ctx.fillStyle = "rgba(94, 234, 212, 0.45)";
    const dot = Math.max(1.1, 1.6 * scale);
    for (const point of face) {
      const [px, py] = toPixel(point, width, height, mirrored);
      ctx.fillRect(px - dot / 2, py - dot / 2, dot, dot);
    }

    if (debug) {
      ctx.font = `500 ${Math.round(11 * scale)}px ui-monospace, SFMono-Regular, Menlo, monospace`;
      ctx.fillStyle = "rgba(167, 139, 250, 0.95)";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      for (const index of FACE_DEBUG_INDICES) {
        const point = face[index];
        if (!point) continue;
        const [px, py] = toPixel(point, width, height, mirrored);
        ctx.fillText(String(index), px + 4 * scale, py);
      }
    }
  }

  // --- hands ------------------------------------------------------------ //
  hands.forEach((hand, handIndex) => {
    const points = hand.landmarks.map((landmark) =>
      toPixel(landmark, width, height, mirrored),
    );
    const hue = handIndex === 0 ? THEME.teal : THEME.violet;

    ctx.strokeStyle = hue;
    ctx.globalAlpha = 0.85;
    ctx.lineWidth = Math.max(1.6, 2.4 * scale);
    ctx.beginPath();
    for (const [from, to] of HAND_CONNECTIONS) {
      const a = points[from];
      const b = points[to];
      if (!a || !b) continue;
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(b[0], b[1]);
    }
    ctx.stroke();

    ctx.globalAlpha = 1;
    ctx.fillStyle = "#f8fafc";
    const radius = Math.max(2, 3.2 * scale);
    for (const [px, py] of points) {
      ctx.beginPath();
      ctx.arc(px, py, radius, 0, Math.PI * 2);
      ctx.fill();
    }

    if (debug) {
      ctx.font = `500 ${Math.round(11 * scale)}px ui-monospace, SFMono-Regular, Menlo, monospace`;
      ctx.fillStyle = "rgba(248, 250, 252, 0.9)";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      points.forEach(([px, py], index) => {
        ctx.fillText(String(index), px + 5 * scale, py - 5 * scale);
      });
    }
  });
  ctx.globalAlpha = 1;

  // --- badges ----------------------------------------------------------- //
  const margin = Math.round(16 * scale);
  let top = margin;
  if (expression) {
    drawBadge(ctx, margin, top, expression, scale);
    top += Math.round(52 * scale);
  }
  if (gesture) {
    drawBadge(ctx, margin, top, gesture, scale);
  }

  // --- FPS -------------------------------------------------------------- //
  const fpsText = `${Math.round(fps)} FPS`;
  ctx.font = `600 ${Math.round(14 * scale)}px ui-monospace, SFMono-Regular, Menlo, monospace`;
  const fpsWidth = ctx.measureText(fpsText).width + 22 * scale;
  ctx.fillStyle = THEME.ink;
  ctx.strokeStyle = THEME.border;
  roundedRect(ctx, width - fpsWidth - margin, margin, fpsWidth, 30 * scale, 8 * scale);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = THEME.teal;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(fpsText, width - fpsWidth / 2 - margin, margin + 15 * scale);

  if (frozen) {
    const text = "FROZEN";
    ctx.font = `700 ${Math.round(13 * scale)}px ui-sans-serif, system-ui, sans-serif`;
    const badgeWidth = ctx.measureText(text).width + 24 * scale;
    ctx.fillStyle = "rgba(167, 139, 250, 0.22)";
    ctx.strokeStyle = THEME.violet;
    roundedRect(ctx, width / 2 - badgeWidth / 2, margin, badgeWidth, 30 * scale, 8 * scale);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = THEME.violet;
    ctx.fillText(text, width / 2, margin + 15 * scale);
  }

  ctx.restore();
}

/** Placeholder used before the first frame arrives. */
export function clearOverlay(ctx: CanvasRenderingContext2D): void {
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
}
