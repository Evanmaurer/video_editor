export function formatDuration(ms: number | null | undefined): string {
  if (ms == null || ms <= 0) {
    return "—";
  }
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function formatResolution(width: number | null, height: number | null): string {
  if (!width || !height) {
    return "—";
  }
  return `${width}×${height}`;
}

export function formatFps(frameRate: number | null | undefined): string {
  if (frameRate == null || frameRate <= 0) {
    return "—";
  }
  return `${frameRate.toFixed(frameRate >= 10 ? 0 : 1)} fps`;
}

export function statusLabel(status: string): string {
  switch (status) {
    case "ready":
      return "Ready";
    case "processing":
      return "Processing";
    case "pending":
      return "Pending";
    case "error":
      return "Error";
    default:
      return status;
  }
}
