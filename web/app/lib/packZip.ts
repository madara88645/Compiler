import { zipSync, strToU8 } from "fflate";

/**
 * Minimal shape zipping needs. Kept intentionally narrower than
 * `AgentPackFile` (see `../agent-packs/types`) so any export result shaped
 * like `{ path, content }` — e.g. agent-generator/skills-generator export
 * files — can be zipped without an extra mapping step.
 */
export interface ZipEntryFile {
  path: string;
  content: string;
}

/** Zip the given files into raw bytes (in-memory, synchronous). */
export function zipPackBytes(files: ZipEntryFile[]): Uint8Array {
  const entries: Record<string, Uint8Array> = {};
  for (const file of files) {
    entries[file.path] = strToU8(file.content);
  }
  return zipSync(entries);
}

/** Build a downloadable application/zip Blob from the given files. */
export function buildPackZip(files: ZipEntryFile[]): Blob {
  const bytes = zipPackBytes(files);
  // Copy into an ArrayBuffer-backed view so the bytes satisfy BlobPart
  // (fflate types its output as Uint8Array<ArrayBufferLike>).
  const buffer = new Uint8Array(bytes.length);
  buffer.set(bytes);
  return new Blob([buffer], { type: "application/zip" });
}
