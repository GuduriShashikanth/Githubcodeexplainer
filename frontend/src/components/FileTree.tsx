/**
 * components/FileTree.tsx
 * -----------------------
 * VS Code-style collapsible file explorer.
 */

import { useState } from "react";
import { VscFolder, VscFolderOpened, VscFile } from "react-icons/vsc";

// ── Tree data structure ───────────────────────────────────────────────────────

interface TreeNode {
  name:     string;
  path:     string;
  type:     "file" | "dir";
  children: TreeNode[];
}

function buildTree(paths: string[]): TreeNode[] {
  const root: TreeNode = { name: "", path: "", type: "dir", children: [] };

  for (const p of paths) {
    const parts = p.split("/");
    let cur = root;
    parts.forEach((part, i) => {
      const isFile = i === parts.length - 1;
      let child = cur.children.find((c) => c.name === part);
      if (!child) {
        child = { name: part, path: parts.slice(0, i + 1).join("/"),
                  type: isFile ? "file" : "dir", children: [] };
        cur.children.push(child);
      }
      if (!isFile) cur = child;
    });
  }

  const sort = (nodes: TreeNode[]): TreeNode[] =>
    nodes
      .sort((a, b) => {
        if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
        return a.name.localeCompare(b.name);
      })
      .map((n) => ({ ...n, children: sort(n.children) }));

  return sort(root.children);
}

// ── Tree node renderer ────────────────────────────────────────────────────────

function TreeNodeRow({ node, depth }: { node: TreeNode; depth: number }) {
  const [open, setOpen] = useState(depth < 1);

  if (node.type === "dir") {
    return (
      <div>
        <button
          className="ftree-row ftree-row--dir"
          style={{ paddingLeft: `${8 + depth * 14}px` }}
          onClick={() => setOpen((p) => !p)}
        >
          <span className="ftree-arrow">{open ? "▾" : "▸"}</span>
          {open
            ? <VscFolderOpened size={13} color="#e8ab53" style={{ flexShrink: 0 }} />
            : <VscFolder       size={13} color="#e8ab53" style={{ flexShrink: 0 }} />
          }
          <span className="ftree-name">{node.name}</span>
        </button>
        {open && node.children.map((c) => (
          <TreeNodeRow key={c.path} node={c} depth={depth + 1} />
        ))}
      </div>
    );
  }

  return (
    <div
      className="ftree-row ftree-row--file"
      style={{ paddingLeft: `${8 + depth * 14}px` }}
      title={node.path}
    >
      <VscFile size={12} color="#6d8086" style={{ flexShrink: 0 }} />
      <span className="ftree-name">{node.name}</span>
    </div>
  );
}

// ── Public component ──────────────────────────────────────────────────────────

export default function FileTree({ files }: { files: string[] }) {
  const tree = buildTree(files);
  if (tree.length === 0) return <p className="ftree-empty">No files indexed.</p>;
  return (
    <div className="ftree">
      {tree.map((n) => <TreeNodeRow key={n.path} node={n} depth={0} />)}
    </div>
  );
}
