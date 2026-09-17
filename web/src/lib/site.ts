/** Project-wide constants shared by the header, the landing sections and the footer. */

export const SITE_NAME = "MirrorLab";
export const REPO_URL = "https://github.com/TrinaxCode/mirrorlab";
export const SNAPSHOT_PREFIX = "mirrorlab";

/** `mirrorlab-20250101-120000.png` — sortable, local time, no illegal characters. */
export function snapshotFilename(date = new Date()): string {
  const pad = (value: number, size = 2) => String(value).padStart(size, "0");
  const stamp =
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}` +
    `-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
  return `${SNAPSHOT_PREFIX}-${stamp}.png`;
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
  // Give the browser a beat to start the download before revoking.
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}
