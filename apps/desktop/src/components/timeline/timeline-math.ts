/** Base pixels per second at zoom 1.0 */
export const BASE_PIXELS_PER_SECOND = 80;

export function pixelsPerSecond(zoom: number): number {
  return BASE_PIXELS_PER_SECOND * zoom;
}

export function msToPixels(ms: number, zoom: number): number {
  return (ms / 1000) * pixelsPerSecond(zoom);
}

export function pixelsToMs(pixels: number, zoom: number): number {
  const pps = pixelsPerSecond(zoom);
  return pps > 0 ? (pixels / pps) * 1000 : 0;
}

export const TRACK_HEADER_WIDTH = 120;
export const TRACK_HEIGHT = 48;
export const RULER_HEIGHT = 28;
