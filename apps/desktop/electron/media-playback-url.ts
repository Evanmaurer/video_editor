import { existsSync } from "fs";
import { pathToMontageFileUrl } from "./media-file-url";

export function resolvePlaybackVideoUrl(
  filePath: string | null | undefined,
  proxyPath: string | null | undefined,
): string | null {
  const candidates = [proxyPath, filePath].filter(
    (value): value is string => Boolean(value && value.trim()),
  );

  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return pathToMontageFileUrl(candidate);
    }
  }

  return null;
}
