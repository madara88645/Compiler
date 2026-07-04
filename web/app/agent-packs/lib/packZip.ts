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
  return new Blob([zipPackBytes(files)], { type: "application/zip" });
}
