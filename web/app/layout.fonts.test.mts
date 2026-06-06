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

test("global theme keeps local fallback font stacks", () => {
  assert.match(globalsSource, /--font-sans:\s*"Segoe UI"/);
  assert.match(globalsSource, /--font-mono:\s*"Cascadia Code"/);
});
