/**
 * components/Sidebar.tsx
 * ----------------------
 * Left panel: GitHub URL input + animated pipeline status + file explorer.
 */

import { useState, useEffect, type FormEvent } from "react";
import FileTree from "./FileTree";

export type SidebarState = "idle" | "indexing" | "ready";

interface RepoInfo {
  repo:           string;
  files_indexed:  number;
  chunks_created: number;
}

interface Props {
  state:    SidebarState;
  repoInfo: RepoInfo | null;
  files:    string[];          // all indexed file paths
  onSubmit: (url: string) => void;
  onReset:  () => void;
}

const STEPS = [
  { key: "download", label: "Downloading files"     },
  { key: "chunk",    label: "Chunking code"         },
  { key: "embed",    label: "Generating embeddings" },
  { key: "index",    label: "Building FAISS index"  },
];

const STEP_DURATIONS = [5000, 800, 14000, 500];

export default function Sidebar({ state, repoInfo, files, onSubmit, onReset }: Props) {
  const [url,          setUrl]     = useState("");
  const [stepIdx,      setStepIdx] = useState(0);
  const [treeOpen,     setTreeOpen] = useState(false);

  useEffect(() => {
    if (state !== "indexing") { setStepIdx(0); return; }
    let current = 0;
    const advance = () => {
      current++;
      if (current < STEPS.length) {
        setStepIdx(current);
        timer = setTimeout(advance, STEP_DURATIONS[current]);
      }
    };
    let timer = setTimeout(advance, STEP_DURATIONS[0]);
    return () => clearTimeout(timer);
  }, [state]);

  // Auto-collapse tree when repo changes
  useEffect(() => { setTreeOpen(false); }, [repoInfo]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
  };

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <div className="sidebar-brand-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="16 18 22 12 16 6"/>
            <polyline points="8 6 2 12 8 18"/>
          </svg>
        </div>
        <span>Code Explainer</span>
      </div>

      <div className="sidebar-divider" />

      {/* ── idle ── */}
      {state === "idle" && (
        <form className="sidebar-form" onSubmit={handleSubmit}>
          <label className="sidebar-label">GitHub Repository URL</label>
          <input
            className="sidebar-input"
            type="text"
            placeholder="https://github.com/owner/repo"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            autoFocus
          />
          <button className="sidebar-btn-primary" type="submit" disabled={!url.trim()}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
            Analyse Repository
          </button>
          <p className="sidebar-hint">
            Paste a public GitHub URL to index the codebase and start chatting.
          </p>
        </form>
      )}

      {/* ── indexing ── */}
      {state === "indexing" && (
        <div className="sidebar-pipeline">
          <p className="sidebar-pipeline-title">Analysing repository…</p>
          <div className="sidebar-steps">
            {STEPS.map((step, i) => {
              const done   = i < stepIdx;
              const active = i === stepIdx;
              return (
                <div key={step.key}
                  className={`sidebar-step ${done ? "sidebar-step--done" : active ? "sidebar-step--active" : "sidebar-step--pending"}`}>
                  <div className="sidebar-step-icon">
                    {done ? (
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    ) : active ? (
                      <span className="sidebar-spinner" />
                    ) : (
                      <span className="sidebar-step-dot" />
                    )}
                  </div>
                  <span className="sidebar-step-label">{step.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── ready ── */}
      {state === "ready" && repoInfo && (
        <div className="sidebar-repo">
          <div className="sidebar-repo-name">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
            </svg>
            <span>{repoInfo.repo}</span>
          </div>

          <div className="sidebar-stats">
            <div className="sidebar-stat">
              <span className="sidebar-stat-value">{repoInfo.files_indexed}</span>
              <span className="sidebar-stat-label">Files indexed</span>
            </div>
            <div className="sidebar-stat">
              <span className="sidebar-stat-value">{repoInfo.chunks_created}</span>
              <span className="sidebar-stat-label">Chunks created</span>
            </div>
          </div>

          <div className="sidebar-ready-badge">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            Ready to chat
          </div>

          {/* ── File tree toggle ── */}
          {files.length > 0 && (
            <div className="sidebar-filetree-section">
              <button
                className="sidebar-filetree-toggle"
                onClick={() => setTreeOpen((p) => !p)}
              >
                <span className="sidebar-filetree-arrow">{treeOpen ? "▾" : "▸"}</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
                Files ({files.length})
              </button>
              {treeOpen && (
                <div className="sidebar-filetree-body">
                  <FileTree files={files} />
                </div>
              )}
            </div>
          )}

          <button className="sidebar-btn-secondary" onClick={onReset}>
            Analyse a different repo
          </button>
        </div>
      )}
    </aside>
  );
}
