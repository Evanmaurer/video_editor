export function pathToMontageFileUrl(filePath: string): string {
  const normalized = filePath.replace(/\\/g, "/");
  const encoded = normalized
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return `montage-file://${encoded}`;
}

export function montageFileUrlToPath(url: string): string {
  const parsed = new URL(url);
  return decodeURIComponent(parsed.pathname);
}
