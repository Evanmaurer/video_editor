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
  if (parsed.protocol !== "montage-file:") {
    throw new Error(`Unsupported media URL: ${url}`);
  }

  if (parsed.hostname) {
    return decodeURIComponent(`/${parsed.hostname}${parsed.pathname}`);
  }

  return decodeURIComponent(parsed.pathname);
}
