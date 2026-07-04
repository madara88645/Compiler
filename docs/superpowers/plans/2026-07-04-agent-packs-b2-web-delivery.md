# Agent Packs B2 — Web Delivery Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the Agent Packs web delivery UX — client-side pack zip from the in-state manifest, an interactive install checklist, a real file tree with per-file download, removal of the dead provider card, and reduced beta hedging.

**Architecture:** All changes live in `web/app/agent-packs/**`. New pure helpers (`lib/packZip.ts`, `lib/fileTree.ts`) and one new component (`components/FileTree.tsx`) are built and unit-tested in isolation first, then wired into `page.tsx`. The whole-pack `.zip` is assembled in the browser from the manifest already in React state using `fflate` (no second server round-trip). Backend, API, and MCP are untouched.

**Tech Stack:** Next.js 16 (App Router, client component), React 19, TypeScript, Tailwind v4, lucide-react icons, Vitest + Testing Library (happy-dom), `fflate` (new dependency, approved).

**Spec:** `docs/superpowers/specs/2026-07-04-agent-packs-b2-web-delivery-design.md`

**Branch:** `feat/agent-packs-web-b2` (already created off `main`; the spec is already committed on it).

---

## File Structure

**New files:**
- `web/app/agent-packs/lib/packZip.ts` — pure: build a `.zip` (bytes + Blob) from `AgentPackFile[]`.
- `web/app/agent-packs/lib/packZip.test.ts` — unit tests (round-trip, empty).
- `web/app/agent-packs/lib/fileTree.ts` — pure: build a nested folder/file tree from `AgentPackFile[]`.
- `web/app/agent-packs/lib/fileTree.test.ts` — unit tests (nesting, ordering).
- `web/app/agent-packs/components/FileTree.tsx` — collapsible tree UI + per-file download button.
- `web/app/agent-packs/components/FileTree.test.tsx` — component tests (a11y names, select, download).
- `web/app/agent-packs/components/InstallChecklist.test.tsx` — component tests for the interactive checklist.

**Modified files:**
- `web/package.json` — add `fflate`.
- `web/app/agent-packs/page.tsx` — client-side download, tree replaces tabs, checklist state, dead card removed, hedging reduced, dead imports removed.
- `web/app/agent-packs/components/InstallChecklist.tsx` — interactive checkboxes + progress.
- `web/app/agent-packs/providerRegistry.ts` — trim `badge`/`summary` wording.
- `web/app/agent-packs/page.test.tsx` — update the tests that assumed tabs/server-download/beta box.

**Unchanged (intentionally):** `installChecklist.ts`, `installChecklist.test.ts`, `claude/download/route.ts`, `proxy-routes.test.ts`, `types.ts`, all backend/API/MCP.

**Command notes:** all commands run from `web/`. Single test file: `npm run test -- <path-relative-to-web>`. Full suite: `npm run test`. Build: `npm run build`.

---

## Task 1: Add the `fflate` dependency

**Files:**
- Modify: `web/package.json` (and `web/package-lock.json` via install)

- [ ] **Step 1: Install fflate**

Run:
```bash
cd web && npm install fflate@^0.8.2
```
Expected: `package.json` gains `"fflate": "^0.8.2"` under `dependencies`; lockfile updates; no errors.

- [ ] **Step 2: Verify it resolves**

Run:
```bash
cd web && node -e "const {zipSync,strToU8,unzipSync,strFromU8}=require('fflate'); const z=zipSync({'a.txt':strToU8('hi')}); console.log(strFromU8(unzipSync(z)['a.txt']))"
```
Expected: prints `hi`.

- [ ] **Step 3: Commit**

```bash
cd .. && git add web/package.json web/package-lock.json
git commit -m "chore(web): add fflate for client-side pack zipping

Approved dependency addition (normally a hard boundary) to build the
Agent Packs download client-side from the in-state manifest.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `lib/packZip.ts` — build the pack zip in the browser

**Files:**
- Create: `web/app/agent-packs/lib/packZip.ts`
- Test: `web/app/agent-packs/lib/packZip.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/app/agent-packs/lib/packZip.test.ts`:
```ts
import { describe, expect, test } from "vitest";
import { unzipSync, strFromU8 } from "fflate";

import { zipPackBytes, buildPackZip } from "./packZip";
import type { AgentPackFile } from "../types";

const files: AgentPackFile[] = [
  { path: "CLAUDE.md", content: "# Memory\n", kind: "claude_md" },
  { path: ".claude/agents/pr-reviewer.md", content: "review agent", kind: "agents" },
];

describe("packZip", () => {
  test("round-trips every file path and content", () => {
    const unzipped = unzipSync(zipPackBytes(files));
    expect(Object.keys(unzipped).sort()).toEqual(
      [".claude/agents/pr-reviewer.md", "CLAUDE.md"].sort(),
    );
    expect(strFromU8(unzipped["CLAUDE.md"])).toBe("# Memory\n");
    expect(strFromU8(unzipped[".claude/agents/pr-reviewer.md"])).toBe("review agent");
  });

  test("buildPackZip returns an application/zip Blob", () => {
    expect(buildPackZip(files).type).toBe("application/zip");
  });

  test("empty file list produces a valid empty zip", () => {
    expect(Object.keys(unzipSync(zipPackBytes([])))).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test -- app/agent-packs/lib/packZip.test.ts`
Expected: FAIL — cannot resolve `./packZip` / `zipPackBytes is not a function`.

- [ ] **Step 3: Write the implementation**

Create `web/app/agent-packs/lib/packZip.ts`:
```ts
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test -- app/agent-packs/lib/packZip.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web/app/agent-packs/lib/packZip.ts web/app/agent-packs/lib/packZip.test.ts
git commit -m "feat(agent-packs): client-side pack zip helper (packZip)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `lib/fileTree.ts` — build a nested file tree

**Files:**
- Create: `web/app/agent-packs/lib/fileTree.ts`
- Test: `web/app/agent-packs/lib/fileTree.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/app/agent-packs/lib/fileTree.test.ts`:
```ts
import { describe, expect, test } from "vitest";

import { buildFileTree, type FileTreeFolderNode } from "./fileTree";
import type { AgentPackFile } from "../types";

const mk = (path: string): AgentPackFile => ({ path, content: path, kind: "files" });

describe("buildFileTree", () => {
  test("a single top-level file becomes one file node", () => {
    const tree = buildFileTree([mk("CLAUDE.md")]);
    expect(tree).toHaveLength(1);
    expect(tree[0]).toMatchObject({ type: "file", name: "CLAUDE.md", path: "CLAUDE.md" });
  });

  test("nested paths build folder nodes with the right segments and paths", () => {
    const tree = buildFileTree([mk(".claude/agents/pr-reviewer.md")]);
    expect(tree).toHaveLength(1);
    const claude = tree[0] as FileTreeFolderNode;
    expect(claude).toMatchObject({ type: "folder", name: ".claude", path: ".claude" });
    const agents = claude.children[0] as FileTreeFolderNode;
    expect(agents).toMatchObject({ type: "folder", name: "agents", path: ".claude/agents" });
    expect(agents.children[0]).toMatchObject({
      type: "file",
      name: "pr-reviewer.md",
      path: ".claude/agents/pr-reviewer.md",
    });
  });

  test("folders sort before files, alphabetically within a level", () => {
    const tree = buildFileTree([mk("README.md"), mk(".claude/settings.json"), mk("AGENTS.md")]);
    expect(tree.map((n) => n.name)).toEqual([".claude", "AGENTS.md", "README.md"]);
    expect(tree[0].type).toBe("folder");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test -- app/agent-packs/lib/fileTree.test.ts`
Expected: FAIL — cannot resolve `./fileTree`.

- [ ] **Step 3: Write the implementation**

Create `web/app/agent-packs/lib/fileTree.ts`:
```ts
import type { AgentPackFile } from "../types";

export interface FileTreeFileNode {
  type: "file";
  name: string;
  path: string;
  file: AgentPackFile;
}

export interface FileTreeFolderNode {
  type: "folder";
  name: string;
  path: string;
  children: FileTreeNode[];
}

export type FileTreeNode = FileTreeFileNode | FileTreeFolderNode;

export function buildFileTree(files: AgentPackFile[]): FileTreeNode[] {
  const root: FileTreeFolderNode = { type: "folder", name: "", path: "", children: [] };

  for (const file of files) {
    const segments = file.path.split("/");
    let cursor = root;
    for (let i = 0; i < segments.length - 1; i += 1) {
      const segment = segments[i];
      const folderPath = segments.slice(0, i + 1).join("/");
      let next = cursor.children.find(
        (child): child is FileTreeFolderNode =>
          child.type === "folder" && child.name === segment,
      );
      if (!next) {
        next = { type: "folder", name: segment, path: folderPath, children: [] };
        cursor.children.push(next);
      }
      cursor = next;
    }
    const name = segments[segments.length - 1];
    cursor.children.push({ type: "file", name, path: file.path, file });
  }

  sortTree(root.children);
  return root.children;
}

function sortTree(nodes: FileTreeNode[]): void {
  nodes.sort((a, b) => {
    if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  for (const node of nodes) {
    if (node.type === "folder") sortTree(node.children);
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test -- app/agent-packs/lib/fileTree.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web/app/agent-packs/lib/fileTree.ts web/app/agent-packs/lib/fileTree.test.ts
git commit -m "feat(agent-packs): pure file-tree builder from manifest paths

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `components/FileTree.tsx` — tree UI + per-file download

**Files:**
- Create: `web/app/agent-packs/components/FileTree.tsx`
- Test: `web/app/agent-packs/components/FileTree.test.tsx`

Folders default to **expanded** so every node is visible in small packs.

- [ ] **Step 1: Write the failing test**

Create `web/app/agent-packs/components/FileTree.test.tsx`:
```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import FileTree from "./FileTree";
import type { AgentPackFile } from "../types";

const files: AgentPackFile[] = [
  { path: "CLAUDE.md", content: "# Memory", kind: "claude_md" },
  { path: ".claude/agents/pr-reviewer.md", content: "agent", kind: "agents" },
];

describe("FileTree", () => {
  test("renders file rows by basename and folder rows by segment", () => {
    render(
      <FileTree files={files} selectedPath={null} onSelect={() => {}} onDownloadFile={() => {}} />,
    );
    expect(screen.getByRole("button", { name: "CLAUDE.md" })).toBeTruthy();
    expect(screen.getByRole("button", { name: ".claude" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "agents" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "pr-reviewer.md" })).toBeTruthy();
  });

  test("selecting a file calls onSelect with its full path", () => {
    const onSelect = vi.fn();
    render(
      <FileTree files={files} selectedPath={null} onSelect={onSelect} onDownloadFile={() => {}} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "pr-reviewer.md" }));
    expect(onSelect).toHaveBeenCalledWith(".claude/agents/pr-reviewer.md");
  });

  test("per-file download button is named by basename and passes the file", () => {
    const onDownloadFile = vi.fn();
    render(
      <FileTree files={files} selectedPath={null} onSelect={() => {}} onDownloadFile={onDownloadFile} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Download pr-reviewer.md" }));
    expect(onDownloadFile).toHaveBeenCalledWith(files[1]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test -- app/agent-packs/components/FileTree.test.tsx`
Expected: FAIL — cannot resolve `./FileTree`.

- [ ] **Step 3: Write the implementation**

Create `web/app/agent-packs/components/FileTree.tsx`:
```tsx
"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Download, FileText, Folder } from "lucide-react";

import type { AgentPackFile } from "../types";
import { buildFileTree, type FileTreeNode } from "../lib/fileTree";

interface FileTreeProps {
  files: AgentPackFile[];
  selectedPath: string | null;
  onSelect: (path: string) => void;
  onDownloadFile: (file: AgentPackFile) => void;
}

export default function FileTree({ files, selectedPath, onSelect, onDownloadFile }: FileTreeProps) {
  const nodes = buildFileTree(files);
  return (
    <ul className="space-y-0.5">
      {nodes.map((node) => (
        <FileTreeItem
          key={node.path}
          node={node}
          depth={0}
          selectedPath={selectedPath}
          onSelect={onSelect}
          onDownloadFile={onDownloadFile}
        />
      ))}
    </ul>
  );
}

interface FileTreeItemProps {
  node: FileTreeNode;
  depth: number;
  selectedPath: string | null;
  onSelect: (path: string) => void;
  onDownloadFile: (file: AgentPackFile) => void;
}

function FileTreeItem({ node, depth, selectedPath, onSelect, onDownloadFile }: FileTreeItemProps) {
  const [expanded, setExpanded] = useState(true);
  const indent = { paddingLeft: `${depth * 12 + 8}px` };

  if (node.type === "folder") {
    return (
      <li>
        <button
          type="button"
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
          style={indent}
          className="flex w-full items-center gap-1.5 rounded-lg px-2 py-1 text-left text-xs text-zinc-300 transition hover:bg-white/[0.05] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-500"
        >
          {expanded ? (
            <ChevronDown size={13} aria-hidden="true" />
          ) : (
            <ChevronRight size={13} aria-hidden="true" />
          )}
          <Folder size={13} className="text-cyan-300/70" aria-hidden="true" />
          <span className="font-mono">{node.name}</span>
        </button>
        {expanded && (
          <ul className="space-y-0.5">
            {node.children.map((child) => (
              <FileTreeItem
                key={child.path}
                node={child}
                depth={depth + 1}
                selectedPath={selectedPath}
                onSelect={onSelect}
                onDownloadFile={onDownloadFile}
              />
            ))}
          </ul>
        )}
      </li>
    );
  }

  const active = node.path === selectedPath;
  return (
    <li className="flex items-center gap-1">
      <button
        type="button"
        onClick={() => onSelect(node.path)}
        style={indent}
        className={`flex min-w-0 flex-1 items-center gap-1.5 rounded-lg px-2 py-1 text-left text-xs transition focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-500 ${
          active
            ? "bg-cyan-500/10 text-cyan-100"
            : "text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-200"
        }`}
      >
        <FileText size={13} aria-hidden="true" />
        <span className="truncate font-mono">{node.name}</span>
      </button>
      <button
        type="button"
        onClick={() => onDownloadFile(node.file)}
        aria-label={`Download ${node.name}`}
        title={`Download ${node.name}`}
        className="shrink-0 rounded-lg p-1 text-zinc-500 transition hover:bg-white/[0.05] hover:text-cyan-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-500"
      >
        <Download size={13} aria-hidden="true" />
      </button>
    </li>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test -- app/agent-packs/components/FileTree.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web/app/agent-packs/components/FileTree.tsx web/app/agent-packs/components/FileTree.test.tsx
git commit -m "feat(agent-packs): collapsible file tree with per-file download

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: `page.tsx` — build the download client-side from the manifest

Rewrite `handleDownload` to build the zip from `manifest.files` (no server call), remove the dead `apiFetch` import and `getDownloadFilename` helper, and update the download tests.

**Files:**
- Modify: `web/app/agent-packs/page.tsx`
- Modify: `web/app/agent-packs/page.test.tsx`

- [ ] **Step 1: Update the download tests first (they should fail against current code)**

In `web/app/agent-packs/page.test.tsx`:

(a) Remove `apiFetch` from the hoisted mock. Change the top mock block:
```tsx
const { apiJson, apiFetch } = vi.hoisted(() => ({
  apiJson: vi.fn(),
  apiFetch: vi.fn(),
}));

vi.mock("@/config", () => ({
  apiJson,
  apiFetch,
  buildGeneratorApiHeaders: (headers: HeadersInit = {}) => headers,
  describeRequestError: (error: unknown) =>
    error instanceof Error && error.message === "Failed to fetch"
      ? "The service is temporarily unavailable or still waking up. Please retry in a few seconds."
      : error instanceof Error
        ? error.message
        : "Connection failed.",
}));
```
to:
```tsx
const { apiJson } = vi.hoisted(() => ({
  apiJson: vi.fn(),
}));

vi.mock("@/config", () => ({
  apiJson,
  buildGeneratorApiHeaders: (headers: HeadersInit = {}) => headers,
  describeRequestError: (error: unknown) =>
    error instanceof Error && error.message === "Failed to fetch"
      ? "The service is temporarily unavailable or still waking up. Please retry in a few seconds."
      : error instanceof Error
        ? error.message
        : "Connection failed.",
}));
```

(b) In `beforeEach`, delete the `apiFetch.mockReset();` line and the whole `apiFetch.mockResolvedValue(new Response("zip-bytes", {...}));` block (keep the `apiJson` setup, the `navigator.clipboard` stub, and the `URL` stub).

(c) Replace the test `"downloads the generated pack through the Claude download route"` (the whole `test(...)` block) with:
```tsx
  test("downloads a zip built from the in-state manifest", async () => {
    const clickSpy = vi.fn();
    const anchors: HTMLAnchorElement[] = [];
    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
      const element = originalCreateElement(tagName);
      if (tagName.toLowerCase() === "a") {
        Object.defineProperty(element, "click", { configurable: true, value: clickSpy });
        anchors.push(element as HTMLAnchorElement);
      }
      return element;
    });

    render(<AgentPacksPage />);
    fireEvent.change(screen.getByLabelText("What should Claude do?"), {
      target: { value: "Create a full project pack." },
    });
    fireEvent.click(screen.getAllByRole("button", { name: /generate claude pack/i })[0]);

    await screen.findByText("Pack Preview");
    fireEvent.click(screen.getByRole("button", { name: /download pack/i }));

    // Built client-side: a blob URL is created and the anchor is clicked, no server call.
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(anchors[anchors.length - 1].download).toBe("saas-pr-reviewer-claude.zip");
    expect(await screen.findByText("Downloaded")).toBeTruthy();
    await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview"));
  });

  test("falls back to agent-pack.zip when the manifest has no download_name", async () => {
    apiJson.mockResolvedValueOnce({
      provider: "claude",
      pack_type: "pr-reviewer",
      download_name: "",
      preview_order: ["claude_md"],
      files: [{ path: "CLAUDE.md", content: "x", kind: "claude_md" }],
    });
    const clickSpy = vi.fn();
    const anchors: HTMLAnchorElement[] = [];
    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
      const element = originalCreateElement(tagName);
      if (tagName.toLowerCase() === "a") {
        Object.defineProperty(element, "click", { configurable: true, value: clickSpy });
        anchors.push(element as HTMLAnchorElement);
      }
      return element;
    });

    render(<AgentPacksPage />);
    fireEvent.change(screen.getByLabelText("What should Claude do?"), {
      target: { value: "x" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: /generate claude pack/i })[0]);

    await screen.findByText("Pack Preview");
    fireEvent.click(screen.getByRole("button", { name: /download pack/i }));

    expect(anchors[anchors.length - 1].download).toBe("agent-pack.zip");
  });
```

(d) Replace BOTH the `"shows a visible error and does not start a download when the pack response is empty"` test and the `"shows a visible error and resets the button when download fails"` test with a single guard test:
```tsx
  test("does not download when the manifest has no files", async () => {
    apiJson.mockResolvedValueOnce({
      provider: "claude",
      pack_type: "pr-reviewer",
      download_name: "empty",
      preview_order: [],
      files: [],
    });
    const clickSpy = vi.fn();
    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
      const element = originalCreateElement(tagName);
      if (tagName.toLowerCase() === "a") {
        Object.defineProperty(element, "click", { configurable: true, value: clickSpy });
      }
      return element;
    });

    render(<AgentPacksPage />);
    fireEvent.change(screen.getByLabelText("What should Claude do?"), {
      target: { value: "x" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: /generate claude pack/i })[0]);

    await screen.findByText("Pack Preview");
    fireEvent.click(screen.getByRole("button", { name: /download pack/i }));

    expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(clickSpy).not.toHaveBeenCalled();
  });
```

- [ ] **Step 2: Run the download tests to verify they fail**

Run: `cd web && npm run test -- app/agent-packs/page.test.tsx -t "download"`
Expected: FAIL (current code still calls `apiFetch` / server route; new assertions don't hold).

- [ ] **Step 3: Rewrite `handleDownload` and remove dead code in `page.tsx`**

(a) Change the config import (line 8) from:
```tsx
import { apiFetch, apiJson, buildGeneratorApiHeaders, describeRequestError } from "@/config";
```
to:
```tsx
import { apiJson, buildGeneratorApiHeaders, describeRequestError } from "@/config";
```

(b) Add the packZip import near the other local imports (after the `providerRegistry` import):
```tsx
import { buildPackZip } from "./lib/packZip";
```

(c) Delete the `getDownloadFilename` helper entirely:
```tsx
function getDownloadFilename(response: Response, fallback: string): string {
  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename=\"?([^"]+)\"?/i);
  return match?.[1] || fallback;
}
```

(d) Replace the entire `handleDownload` function with:
```tsx
  const handleDownload = () => {
    if (!manifest || manifest.files.length === 0) return;

    setDownloading(true);
    setError(null);
    try {
      const blob = buildPackZip(manifest.files);
      const href = URL.createObjectURL(blob);
      const filename = `${manifest.download_name || "agent-pack"}.zip`;
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.download = filename;
      anchor.rel = "noopener";
      anchor.style.display = "none";
      // The anchor must be in the document for the synthetic click to trigger a
      // download in Firefox, and the object URL must outlive the click — revoking
      // it synchronously cancels the download in Chromium-based browsers.
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(href), 0);
      setDownloaded(true);
    } catch (err: unknown) {
      showError(err);
      setError(describeRequestError(err, { fallback: "Failed to download agent pack." }));
    } finally {
      setDownloading(false);
    }
  };
```

- [ ] **Step 4: Run the download tests to verify they pass**

Run: `cd web && npm run test -- app/agent-packs/page.test.tsx -t "download"`
Expected: PASS.

- [ ] **Step 5: Run the whole page test file (nothing else regressed yet)**

Run: `cd web && npm run test -- app/agent-packs/page.test.tsx`
Expected: PASS (tabs, beta, checklist tests still green — those areas are untouched in this task).

- [ ] **Step 6: Commit**

```bash
git add web/app/agent-packs/page.tsx web/app/agent-packs/page.test.tsx
git commit -m "feat(agent-packs): build pack download client-side from the manifest

Download now zips the in-state manifest in the browser (fflate) instead of
re-POSTing to /agent-packs/claude/download. Guarantees the download equals
the preview and drops a redundant server round-trip. The server endpoint and
its proxy route are kept for non-UI clients.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: `page.tsx` — replace group tabs/select with the file tree

**Files:**
- Modify: `web/app/agent-packs/page.tsx`
- Modify: `web/app/agent-packs/page.test.tsx`

- [ ] **Step 1: Update the preview-navigation tests first**

In `web/app/agent-packs/page.test.tsx`, in the test `"submits the selected pack type and renders grouped preview output"`, replace the two assertions:
```tsx
    expect(screen.getByRole("button", { name: "CLAUDE.md" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "agents" })).toBeTruthy();
```
with tree assertions (a top-level file, plus a folder that proves nesting):
```tsx
    expect(screen.getByRole("button", { name: "CLAUDE.md" })).toBeTruthy();
    expect(screen.getByRole("button", { name: ".claude" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "agents" })).toBeTruthy();
```
(The `"closing the preview…"` test's `{ name: "CLAUDE.md" }` assertions still hold — a file row is a button named by basename — so leave that test as is.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd web && npm run test -- app/agent-packs/page.test.tsx -t "grouped preview output"`
Expected: FAIL — `.claude` folder button does not exist yet (current UI renders kind tabs, not a tree).

- [ ] **Step 3: Wire the tree into `page.tsx`**

(a) Add the FileTree import (after the packZip import):
```tsx
import FileTree from "./components/FileTree";
```

(b) Remove the `AgentPackFileKind` type from the type import (it is only used by `PREVIEW_LABELS`/`activeKind`, both deleted). The import becomes:
```tsx
import type {
  AgentPackFile,
  AgentPackManifest,
  AgentPackRequest,
  AgentPackRiskMode,
  AgentPackType,
} from "./types";
```

(c) Delete the `PREVIEW_LABELS` constant:
```tsx
const PREVIEW_LABELS: Record<AgentPackFileKind, string> = {
  claude_md: "CLAUDE.md",
  settings: "settings.json",
  agents: "agents",
  workflow: "workflow",
  mcp: "mcp",
  readme: "README",
  files: "files",
};
```

(d) Remove the `activeKind` state and replace the `previewGroups`/`activeGroup`/`currentFile` derivations. Delete:
```tsx
  const [activeKind, setActiveKind] = useState<AgentPackFileKind | null>(null);
```
Delete:
```tsx
  const previewGroups = useMemo(() => {
    if (!manifest) return [];
    return manifest.preview_order
      .map((kind) => ({
        kind,
        label: PREVIEW_LABELS[kind] ?? kind,
        files: manifest.files.filter((file) => file.kind === kind),
      }))
      .filter((group) => group.files.length > 0);
  }, [manifest]);

  const activeGroup = previewGroups.find((group) => group.kind === activeKind) ?? previewGroups[0] ?? null;
  const currentFile =
    activeGroup?.files.find((file) => file.path === selectedPath) ??
    activeGroup?.files[0] ??
    null;
```
Replace with:
```tsx
  const currentFile = useMemo(() => {
    if (!manifest) return null;
    return manifest.files.find((file) => file.path === selectedPath) ?? manifest.files[0] ?? null;
  }, [manifest, selectedPath]);
```

(e) In `handleGenerate`, remove the `setActiveKind(...)` calls. Change the reset lines from:
```tsx
    setManifest(null);
    setActiveKind(null);
    setSelectedPath(null);
    setDownloaded(false);
```
to:
```tsx
    setManifest(null);
    setSelectedPath(null);
    setDownloaded(false);
```
and change the success lines from:
```tsx
      setManifest(data);
      setActiveKind(data.preview_order[0] ?? null);
      setSelectedPath(data.files[0]?.path ?? null);
```
to:
```tsx
      setManifest(data);
      setSelectedPath(data.files[0]?.path ?? null);
```

(f) In `handleClosePreview`, remove `setActiveKind(null);`:
```tsx
  const handleClosePreview = () => {
    setManifest(null);
    setSelectedPath(null);
    setCopiedState(null);
    setDownloaded(false);
  };
```

(g) Add the per-file download handler (next to `handleDownload`):
```tsx
  const handleDownloadFile = (file: AgentPackFile) => {
    const blob = new Blob([file.content], { type: "text/plain" });
    const href = URL.createObjectURL(blob);
    const basename = file.path.split("/").pop() || "file";
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = basename;
    anchor.rel = "noopener";
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(href), 0);
  };
```

(h) Replace the tabs + `<select>` JSX block. Delete this whole block:
```tsx
                <div className="flex flex-wrap gap-2 border-b border-white/5 px-4 py-3 sm:px-6">
                  {previewGroups.map((group) => (
                    <button
                      key={group.kind}
                      type="button"
                      onClick={() => {
                        setActiveKind(group.kind);
                        setSelectedPath(group.files[0]?.path ?? null);
                      }}
                      className={`rounded-full border px-3 py-1.5 text-[11px] font-mono uppercase tracking-wide transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 ${
                        activeGroup?.kind === group.kind
                          ? "border-cyan-400/40 bg-cyan-500/10 text-cyan-100"
                          : "border-transparent bg-white/[0.03] text-zinc-500 hover:bg-white/[0.07] hover:text-zinc-300"
                      }`}
                    >
                      {group.label}
                    </button>
                  ))}
                </div>

                {activeGroup && activeGroup.files.length > 1 && (
                  <div className="px-4 pt-4 sm:px-6">
                    <label htmlFor="agent-pack-file-select" className="sr-only">
                      Preview file
                    </label>
                    <select
                      id="agent-pack-file-select"
                      value={currentFile?.path ?? activeGroup.files[0].path}
                      onChange={(event) => setSelectedPath(event.target.value)}
                      className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-cyan-500/50"
                    >
                      {activeGroup.files.map((file) => (
                        <option key={file.path} value={file.path}>
                          {file.path}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
```
and replace it with the file tree:
```tsx
                <div className="border-b border-white/5 px-4 py-3 sm:px-6">
                  <div className="mb-2 text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500">
                    Files
                  </div>
                  <FileTree
                    files={manifest.files}
                    selectedPath={currentFile?.path ?? null}
                    onSelect={setSelectedPath}
                    onDownloadFile={handleDownloadFile}
                  />
                </div>
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd web && npm run test -- app/agent-packs/page.test.tsx`
Expected: PASS (grouped-preview + closing-preview tests now resolve to tree nodes; download tests from Task 5 still green).

- [ ] **Step 5: Commit**

```bash
git add web/app/agent-packs/page.tsx web/app/agent-packs/page.test.tsx
git commit -m "feat(agent-packs): replace kind tabs with a real file tree

The preview now shows files in their repo paths as a collapsible tree with
per-file download, replacing the group-by-kind tabs and the file <select>.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Interactive install checklist

Make `InstallChecklist.tsx` render `reviewFirst`/`validationSteps` items as checkboxes with a progress bar, `nextAction` as text, and skip `generatedFiles`. Wire checked-state into `page.tsx`.

**Files:**
- Modify: `web/app/agent-packs/components/InstallChecklist.tsx`
- Modify: `web/app/agent-packs/page.tsx`
- Create: `web/app/agent-packs/components/InstallChecklist.test.tsx`

- [ ] **Step 1: Write the failing component test**

Create `web/app/agent-packs/components/InstallChecklist.test.tsx`:
```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, test } from "vitest";

import InstallChecklist from "./InstallChecklist";
import { buildInstallChecklist } from "../installChecklist";
import type { AgentPackManifest } from "../types";

const manifest: AgentPackManifest = {
  provider: "claude",
  pack_type: "project-pack",
  download_name: "x",
  preview_order: ["claude_md", "settings", "workflow"],
  files: [
    { path: "CLAUDE.md", content: "#", kind: "claude_md" },
    { path: ".claude/settings.json", content: "{}", kind: "settings" },
    { path: ".github/workflows/claude.yml", content: "y", kind: "workflow" },
  ],
};

function Harness() {
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());
  const sections = buildInstallChecklist(manifest);
  return (
    <InstallChecklist
      sections={sections}
      checkedIds={checkedIds}
      onToggle={(id) =>
        setCheckedIds((prev) => {
          const next = new Set(prev);
          if (next.has(id)) next.delete(id);
          else next.add(id);
          return next;
        })
      }
    />
  );
}

describe("InstallChecklist", () => {
  test("renders review/validation items as labelled checkboxes and updates progress", () => {
    render(<Harness />);
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBeGreaterThan(0);
    expect(screen.getByText(`0/${checkboxes.length} done`)).toBeTruthy();

    fireEvent.click(checkboxes[0]);
    expect(screen.getByText(`1/${checkboxes.length} done`)).toBeTruthy();
  });

  test("does not render the generatedFiles section", () => {
    render(<Harness />);
    expect(screen.queryByText(/Add CLAUDE\.md to the matching path/i)).toBeNull();
  });

  test("keeps an accessible checklist heading", () => {
    render(<Harness />);
    expect(screen.getByRole("heading", { name: "Install & review checklist" })).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd web && npm run test -- app/agent-packs/components/InstallChecklist.test.tsx`
Expected: FAIL — current `InstallChecklist` has no checkboxes and different props.

- [ ] **Step 3: Rewrite `InstallChecklist.tsx`**

Replace the entire contents of `web/app/agent-packs/components/InstallChecklist.tsx` with:
```tsx
import { CheckCircle2 } from "lucide-react";

import type { InstallChecklistSection } from "../installChecklist";

interface InstallChecklistProps {
  sections: InstallChecklistSection[];
  checkedIds: Set<string>;
  onToggle: (id: string) => void;
  downloaded?: boolean;
}

const CHECKBOX_SECTION_IDS = new Set(["reviewFirst", "validationSteps"]);

export default function InstallChecklist({
  sections,
  checkedIds,
  onToggle,
  downloaded = false,
}: InstallChecklistProps) {
  const titleId = "agent-pack-install-checklist-title";
  const rendered = sections.filter((section) => section.id !== "generatedFiles");

  const checkboxIds = rendered
    .filter((section) => CHECKBOX_SECTION_IDS.has(section.id))
    .flatMap((section) => section.items.map((_, index) => `${section.id}-${index}`));
  const total = checkboxIds.length;
  const done = checkboxIds.filter((id) => checkedIds.has(id)).length;
  const complete = total > 0 && done === total;

  return (
    <section aria-labelledby={titleId} className="border-b border-white/5 px-4 py-4 sm:px-6">
      <div className="rounded-2xl border border-cyan-400/20 bg-cyan-500/5 p-4">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <h3 id={titleId} className="text-sm font-semibold text-cyan-100">
              Install &amp; review checklist
            </h3>
            <p className="mt-1 text-xs leading-relaxed text-cyan-100/70">
              Generated files are a starting point — review before committing.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {complete ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-200">
                <CheckCircle2 size={12} aria-hidden="true" />
                All steps complete
              </span>
            ) : null}
            {downloaded ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-200">
                <CheckCircle2 size={12} aria-hidden="true" />
                Downloaded
              </span>
            ) : null}
          </div>
        </div>

        {total > 0 ? (
          <div className="mb-3">
            <div className="mb-1 flex items-center justify-between text-[11px] text-cyan-100/70">
              <span>Progress</span>
              <span aria-live="polite">{`${done}/${total} done`}</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-cyan-400 transition-all"
                style={{ width: `${(done / total) * 100}%` }}
              />
            </div>
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2">
          {rendered.map((section) => (
            <div key={section.id} className="rounded-xl border border-white/8 bg-black/20 p-3">
              <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-400">
                {section.title}
              </h4>
              {CHECKBOX_SECTION_IDS.has(section.id) ? (
                <ul className="space-y-2 text-xs leading-relaxed text-zinc-300">
                  {section.items.map((item, index) => {
                    const id = `${section.id}-${index}`;
                    return (
                      <li key={id}>
                        <label className="flex cursor-pointer gap-2">
                          <input
                            type="checkbox"
                            checked={checkedIds.has(id)}
                            onChange={() => onToggle(id)}
                            className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-cyan-400"
                          />
                          <span>{item}</span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <ul className="space-y-2 text-xs leading-relaxed text-zinc-300">
                  {section.items.map((item) => (
                    <li key={`${section.id}-${item}`} className="flex gap-2">
                      <span
                        className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400/80"
                        aria-hidden="true"
                      />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Run the component test to verify it passes**

Run: `cd web && npm run test -- app/agent-packs/components/InstallChecklist.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Wire checked-state into `page.tsx`**

(a) Add the state near the other `useState` hooks (after `downloaded`):
```tsx
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());
```

(b) Add a toggle handler (next to the other handlers):
```tsx
  const toggleChecklistItem = (id: string) => {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
```

(c) Reset it on generate and on close. In `handleGenerate`, add to the reset block:
```tsx
    setManifest(null);
    setSelectedPath(null);
    setDownloaded(false);
    setCheckedIds(new Set());
```
In `handleClosePreview`, add:
```tsx
  const handleClosePreview = () => {
    setManifest(null);
    setSelectedPath(null);
    setCopiedState(null);
    setDownloaded(false);
    setCheckedIds(new Set());
  };
```

(d) Update the `<InstallChecklist ... />` render to pass the new props:
```tsx
                <InstallChecklist
                  sections={installChecklist}
                  checkedIds={checkedIds}
                  onToggle={toggleChecklistItem}
                  downloaded={downloaded}
                />
```

- [ ] **Step 6: Replace the closing-preview page test to also cover checklist reset**

In `web/app/agent-packs/page.test.tsx`, replace the entire `"closing the preview clears the generated pack and its labels"` test block with:
```tsx
  test("closing the preview clears the pack, checklist, and checked state", async () => {
    render(<AgentPacksPage />);

    fireEvent.change(screen.getByLabelText("What should Claude do?"), {
      target: { value: "Create a full project pack." },
    });
    fireEvent.click(screen.getAllByRole("button", { name: /generate claude pack/i })[0]);

    expect(await screen.findByText("Pack Preview")).toBeTruthy();
    expect(screen.getByRole("button", { name: "CLAUDE.md" })).toBeTruthy();

    // Tick a checklist item.
    const firstCheckbox = screen.getAllByRole("checkbox")[0];
    fireEvent.click(firstCheckbox);
    const totalBefore = screen.getAllByRole("checkbox").length;
    expect(screen.getByText(`1/${totalBefore} done`)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /close pack preview/i }));

    // The preview, checklist, and file tree are gone; the empty state returns.
    await waitFor(() => expect(screen.queryByText("Pack Preview")).toBeNull());
    expect(screen.queryByRole("heading", { name: "Install & review checklist" })).toBeNull();
    expect(screen.queryByRole("button", { name: "CLAUDE.md" })).toBeNull();
    expect(screen.getByText("Single-click pack generation")).toBeTruthy();

    // Regenerating starts the checklist progress from zero.
    fireEvent.click(screen.getAllByRole("button", { name: /generate claude pack/i })[0]);
    await screen.findByText("Pack Preview");
    const totalAfter = screen.getAllByRole("checkbox").length;
    expect(screen.getByText(`0/${totalAfter} done`)).toBeTruthy();
  });
```

- [ ] **Step 7: Run the page tests to verify they pass**

Run: `cd web && npm run test -- app/agent-packs/page.test.tsx`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add web/app/agent-packs/components/InstallChecklist.tsx web/app/agent-packs/components/InstallChecklist.test.tsx web/app/agent-packs/page.tsx web/app/agent-packs/page.test.tsx
git commit -m "feat(agent-packs): interactive install checklist with progress

Review/validation steps are now tickable checkboxes with a progress bar;
state is in-session and resets on generate/close. The file list moves to the
tree, so the checklist no longer duplicates it.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Remove the dead provider card and dial back beta hedging

**Files:**
- Modify: `web/app/agent-packs/page.tsx`
- Modify: `web/app/agent-packs/providerRegistry.ts`
- Modify: `web/app/agent-packs/page.test.tsx`

- [ ] **Step 1: Tighten the beta messaging test first**

In `web/app/agent-packs/page.test.tsx`, replace the `"surfaces beta messaging"` test with:
```tsx
  test("surfaces a single, calm beta caveat", () => {
    render(<AgentPacksPage />);

    expect(screen.getAllByText("Beta")).toHaveLength(1);
    expect(screen.queryByText("Experimental Feature")).toBeNull();
    expect(screen.queryByText("API Key (Optional)")).toBeNull();
  });
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd web && npm run test -- app/agent-packs/page.test.tsx -t "single, calm beta caveat"`
Expected: FAIL — currently multiple "Beta" nodes and an "Experimental Feature" box exist.

- [ ] **Step 3: Trim `providerRegistry.ts`**

In `web/app/agent-packs/providerRegistry.ts`, change:
```tsx
    badge: "Beta Preview",
    summary: "Generate repo-ready Claude assets from one short brief, then review them before production use.",
```
to:
```tsx
    badge: "",
    summary: "Generate repo-ready Claude assets from one short brief.",
```

- [ ] **Step 4: Remove the dead card, the Experimental box, and the "beta-stage" heading in `page.tsx`**

(a) Change the intro heading from:
```tsx
                  <h2 className="text-xl font-semibold text-white">Generate beta-stage agent assets for your repo</h2>
```
to:
```tsx
                  <h2 className="text-xl font-semibold text-white">Generate agent assets for your repo</h2>
```

(b) Delete the dead provider card button entirely:
```tsx
            <button
              type="button"
              className={`group flex items-center justify-between rounded-2xl border border-white/10 p-4 text-left transition-all hover:border-cyan-400/30 hover:bg-white/[0.05] ${manifest ? "bg-white/[0.05]" : "bg-white/[0.02]"}`}
              aria-label="Claude provider card"
            >
              <div>
                <div className="mb-1 text-sm font-semibold text-white">{provider.name}</div>
                <div className="text-xs text-zinc-500">
                  Beta preview. Good for fast bootstrapping, but you should still review prompts, permissions,
                  workflows, and generated files before shipping.
                </div>
              </div>
              <div className={`rounded-xl bg-gradient-to-br ${provider.accentClass} px-3 py-2 text-xs font-semibold text-white shadow-lg shadow-cyan-500/10`}>
                Beta
              </div>
            </button>
```

(c) Delete the "Experimental Feature" amber box entirely:
```tsx
            <div className="rounded-2xl border border-amber-400/30 bg-amber-500/10 p-4 text-sm leading-relaxed text-amber-100/90">
              <div className="mb-1 text-xs font-semibold uppercase tracking-[0.25em] text-amber-200">Experimental Feature</div>
              Agent Packs is in beta and gives you a starting point, not a finished install. After generation, follow the
              install checklist on the right, review sensitive files, then commit only what you trust.
            </div>
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd web && npm run test -- app/agent-packs/page.test.tsx -t "single, calm beta caveat"`
Expected: PASS (only the header `Beta` pill remains).

- [ ] **Step 6: Run the whole page test file**

Run: `cd web && npm run test -- app/agent-packs/page.test.tsx`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/app/agent-packs/page.tsx web/app/agent-packs/providerRegistry.ts web/app/agent-packs/page.test.tsx
git commit -m "refactor(agent-packs): remove dead provider card, dial back beta hedging

Delete the no-op Claude provider card and the Experimental Feature box; keep a
single honest Beta badge in the header plus one review caveat in the checklist.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Full verification gate

**Files:** none (verification only).

- [ ] **Step 1: Run the full web test suite**

Run: `cd web && npm run test`
Expected: PASS — all agent-packs suites (packZip, fileTree, FileTree, InstallChecklist, page, installChecklist, proxy-routes) plus the rest of the web tests green.

- [ ] **Step 2: Type/lint via build**

Run: `cd web && npm run build`
Expected: SUCCESS — Next.js compiles with no type errors (this catches any leftover unused import such as `apiFetch`, `AgentPackFileKind`, `getDownloadFilename`, `useMemo` usage).

- [ ] **Step 3: Lint (optional but recommended)**

Run: `cd web && npm run lint`
Expected: no errors (unused-variable rules would flag dead imports if any remain).

- [ ] **Step 4: Stop for review — do NOT open a PR automatically**

Per project rules, never push/PR/merge without Mehmet's explicit approval. Report: changed files, out-of-scope changes (the `fflate` dependency, pre-approved), test/build results, and the boundary note (dependency added). Then ask whether to open the PR.

---

## Self-Review

**1. Spec coverage:**
- Client-side download from in-state manifest → Task 2 (helper) + Task 5 (wiring). ✅
- Interactive checklist (checkboxes + progress, in-session, reset on generate/close, nextAction as text, skip generatedFiles) → Task 7. ✅
- File tree + per-file download → Task 3 (builder) + Task 4 (component) + Task 6 (wiring). ✅
- Remove dead provider card → Task 8. ✅
- Dial back beta hedging (single header badge, `toHaveLength(1)`, provider wording, remove Experimental box + "beta-stage" heading) → Task 8. ✅
- Keep `/download` route + `proxy-routes.test.ts` untouched → confirmed (no task modifies them). ✅
- `installChecklist.ts`/`installChecklist.test.ts` untouched → confirmed (Task 7 only touches the component + page). ✅
- `fflate` dependency (approved) → Task 1. ✅
- Empty-manifest guard + test → Task 5 Step 1(d) + Task 2 empty-zip test. ✅
- Download filename + fallback tests → Task 5 Step 1(c). ✅
- FileTree a11y contract (basename file rows, segment folder rows, `Download <basename>`) → Task 4. ✅
- Checklist a11y (labelled checkboxes via `<label>`, `role="checkbox"` by name) → Task 7 test. ✅
- Gate (`npm run test` + `npm run build`) → Task 9. ✅

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N" — every code step shows complete code. ✅

**3. Type/name consistency:**
- `buildPackZip`/`zipPackBytes` (Task 2) used in Task 5. ✅
- `buildFileTree`, `FileTreeFolderNode`, `FileTreeNode` (Task 3) used in Task 4. ✅
- `FileTree` props `files`/`selectedPath`/`onSelect`/`onDownloadFile` (Task 4) match the render in Task 6. ✅
- `InstallChecklist` props `sections`/`checkedIds`/`onToggle`/`downloaded` (Task 7 component) match the render + `Harness` in Task 7. ✅
- `CHECKBOX_SECTION_IDS = {reviewFirst, validationSteps}` and id scheme `${section.id}-${index}` consistent between component and tests. ✅
- `handleDownloadFile`, `toggleChecklistItem`, `checkedIds` names consistent across Task 6/7 page edits. ✅
