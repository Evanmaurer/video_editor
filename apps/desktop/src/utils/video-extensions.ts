export const VIDEO_EXTENSIONS = new Set([".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"]);

export function isVideoFilePath(filePath: string): boolean {
  const lower = filePath.toLowerCase();
  const dot = lower.lastIndexOf(".");
  if (dot === -1) {
    return false;
  }
  return VIDEO_EXTENSIONS.has(lower.slice(dot));
}
