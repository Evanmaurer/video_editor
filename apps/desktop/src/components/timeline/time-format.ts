export function formatTimelineTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const frames = Math.floor((ms % 1000) / (1000 / 60));
  if (minutes > 0) {
    return `${minutes}:${seconds.toString().padStart(2, "0")}:${frames.toString().padStart(2, "0")}`;
  }
  return `${seconds}:${frames.toString().padStart(2, "0")}`;
}

export function formatMsShort(ms: number): string {
  const s = ms / 1000;
  if (s < 60) {
    return `${s.toFixed(1)}s`;
  }
  const m = Math.floor(s / 60);
  const rem = Math.floor(s % 60);
  return `${m}:${rem.toString().padStart(2, "0")}`;
}
