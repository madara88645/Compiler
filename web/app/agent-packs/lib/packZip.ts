import { zipSync, strToU8 } from "fflate";

import type { AgentPackFile } from "../types";

/** Zip the given files into raw bytes (in-memory, synchronous). */
export function zipPackBytes(files: AgentPackFile[]): Uint8Array {
  const entries: Record<string, Uint8Array> = {};
  for (const file of files) {
    entries[file.path] = strToU8(file.content);
  }
  return zipSync(entries);
}

/** Build a downloadable application/zip Blob from the given files. */
export function buildPackZip(files: AgentPackFile[]): Blob {
  const bytes = zipPackBytes(files);
  // Copy into an ArrayBuffer-backed view so the bytes satisfy BlobPart
  // (fflate types its output as Uint8Array<ArrayBufferLike>).
  const buffer = new Uint8Array(bytes.length);
  buffer.set(bytes);
  return new Blob([buffer], { type: "application/zip" });
}
