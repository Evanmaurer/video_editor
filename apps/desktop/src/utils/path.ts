/** Join path segments (renderer-safe, no Node path module). */
export function joinPath(base: string, segment: string): string {
  const normalized = base.replace(/\/+$/, "");
  return `${normalized}/${segment}`;
}
