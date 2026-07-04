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
