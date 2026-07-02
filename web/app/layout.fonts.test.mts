import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const thisDir = path.dirname(fileURLToPath(import.meta.url));
const layoutSource = readFileSync(path.join(thisDir, "layout.tsx"), "utf8");
const globalsSource = readFileSync(path.join(thisDir, "globals.css"), "utf8");

test("app layout does not depend on remote Google fonts", () => {
  assert.equal(layoutSource.includes('from "next/font/google"'), false);
  assert.equal(layoutSource.includes("Geist("), false);
  assert.equal(layoutSource.includes("Geist_Mono("), false);
});

test("brand fonts are self-hosted with no remote/CDN fetch", () => {
  // Fonts must be bundled locally so the app stays offline-deterministic.
  assert.match(globalsSource, /@font-face/);
  assert.match(globalsSource, /url\("\/fonts\/IBMPlex/);
  // No @font-face src may reach out to a remote host.
  assert.equal(/src:\s*url\(\s*["']?https?:/i.test(globalsSource), false);
  assert.equal(globalsSource.includes("fonts.googleapis.com"), false);
  assert.equal(globalsSource.includes("fonts.gstatic.com"), false);
});

test("global theme uses IBM Plex with local system fallbacks", () => {
  // IBM Plex is primary; the original local stacks stay as offline fallbacks.
  assert.match(globalsSource, /--font-sans:\s*"IBM Plex Sans",\s*"Segoe UI"/);
  assert.match(globalsSource, /--font-mono:\s*"IBM Plex Mono",\s*"Cascadia Code"/);
});
