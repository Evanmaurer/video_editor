import { constants } from "fs";
import { access, readFile } from "fs/promises";
import { extname } from "path";

const THUMBNAIL_MIME: Record<string, string> = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".webp": "image/webp",
};

export async function readImageDataUrl(filePath: string): Promise<string | null> {
  const normalized = filePath.trim();
  if (!normalized) {
    return null;
  }

  try {
    await access(normalized, constants.R_OK);
    const data = await readFile(normalized);
    if (data.length === 0) {
      return null;
    }
    const mime = THUMBNAIL_MIME[extname(normalized).toLowerCase()] ?? "image/jpeg";
    return `data:${mime};base64,${data.toString("base64")}`;
  } catch {
    return null;
  }
}
