const MAX_ENTRIES = 90;

const cache = new Map<string, string>();

export function frameCacheKey(
  mediaId: string,
  sourceMs: number,
  quality: string,
): string {
  return `${quality}:${mediaId}:${Math.round(sourceMs)}`;
}

export function getCachedFrame(key: string): string | undefined {
  const value = cache.get(key);
  if (value !== undefined) {
    cache.delete(key);
    cache.set(key, value);
  }
  return value;
}

export function putCachedFrame(key: string, dataUrl: string): void {
  if (cache.has(key)) {
    cache.delete(key);
  }
  cache.set(key, dataUrl);
  while (cache.size > MAX_ENTRIES) {
    const oldest = cache.keys().next().value;
    if (oldest) {
      cache.delete(oldest);
    }
  }
}

export function clearFrameCache(): void {
  cache.clear();
}
