import { createReadStream, existsSync, statSync } from "fs";
import { extname } from "path";
import { Readable } from "stream";
import { montageFileUrlToPath } from "./media-file-url";

function mimeTypeForPath(filePath: string): string {
  switch (extname(filePath).toLowerCase()) {
    case ".mp4":
    case ".m4v":
      return "video/mp4";
    case ".mov":
      return "video/quicktime";
    case ".webm":
      return "video/webm";
    case ".mkv":
      return "video/x-matroska";
    case ".avi":
      return "video/x-msvideo";
    case ".jpg":
    case ".jpeg":
      return "image/jpeg";
    case ".png":
      return "image/png";
    case ".webp":
      return "image/webp";
    default:
      return "application/octet-stream";
  }
}

export async function handleMontageFileRequest(request: Request): Promise<Response> {
  let filePath: string;
  try {
    filePath = montageFileUrlToPath(request.url);
  } catch {
    return new Response("Bad Request", { status: 400 });
  }

  if (!filePath || !existsSync(filePath)) {
    console.error("[montage-file] Missing file:", filePath, "from", request.url);
    return new Response("Not Found", { status: 404 });
  }

  const stat = statSync(filePath);
  const mime = mimeTypeForPath(filePath);
  const size = stat.size;
  const rangeHeader = request.headers.get("Range");

  if (rangeHeader) {
    const match = /^bytes=(\d+)-(\d*)$/i.exec(rangeHeader.trim());
    if (match) {
      const start = Number.parseInt(match[1]!, 10);
      const end = match[2] ? Number.parseInt(match[2], 10) : size - 1;
      if (start >= 0 && start < size && end >= start && end < size) {
        const chunkSize = end - start + 1;
        const stream = createReadStream(filePath, { start, end });
        return new Response(Readable.toWeb(stream) as ReadableStream, {
          status: 206,
          headers: {
            "Content-Type": mime,
            "Content-Length": String(chunkSize),
            "Content-Range": `bytes ${start}-${end}/${size}`,
            "Accept-Ranges": "bytes",
          },
        });
      }
    }
  }

  const stream = createReadStream(filePath);
  return new Response(Readable.toWeb(stream) as ReadableStream, {
    status: 200,
    headers: {
      "Content-Type": mime,
      "Content-Length": String(size),
      "Accept-Ranges": "bytes",
    },
  });
}
