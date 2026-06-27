export { isVideoFilePath } from "./video-extensions";

export function collectDropPaths(files: File[], getPathForFile: (file: File) => string | null): string[] {
  const paths: string[] = [];
  for (const file of files) {
    const filePath = getPathForFile(file);
    if (filePath) {
      paths.push(filePath);
    }
  }
  return paths;
}
