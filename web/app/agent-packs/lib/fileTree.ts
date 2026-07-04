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
