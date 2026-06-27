/**
 * Formats fetch failures with URL and stack trace for diagnostics.
 */
export function formatFetchError(url: string, err: unknown): Error {
  if (err instanceof Error) {
    const lines = [err.message, `URL: ${url}`];
    if (err.stack) {
      lines.push(`Stack:\n${err.stack}`);
    }
    return new Error(lines.join("\n"));
  }
  return new Error(`Fetch failed\nURL: ${url}\n${String(err)}`);
}
