export type ThumbnailLoadState = "idle" | "loading" | "loaded" | "failed";

export async function loadThumbnailSrc(
  filePath: string,
  projectId: string,
  mediaId: string,
): Promise<string | null> {
  const normalized = filePath.trim();
  if (!normalized) {
    return null;
  }

  const api = window.montageAPI;
  if (typeof api.getThumbnailDataUrl === "function") {
    try {
      const dataUrl = await api.getThumbnailDataUrl(normalized);
      if (dataUrl?.startsWith("data:")) {
        return dataUrl;
      }
    } catch {
      // Fall through to backend fetch.
    }
  }

  try {
    const connection = await api.getBackendConnection();
    if (!connection) {
      return null;
    }

    const response = await fetch(
      `${connection.url}/api/v1/projects/${projectId}/media/${mediaId}/thumbnail`,
      {
        headers: {
          "X-Montage-Token": connection.token,
        },
      },
    );
    if (!response.ok) {
      return null;
    }

    const blob = await response.blob();
    if (blob.size === 0) {
      return null;
    }

    return URL.createObjectURL(blob);
  } catch {
    return null;
  }
}
