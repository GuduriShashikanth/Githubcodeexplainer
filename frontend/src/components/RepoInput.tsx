/**
 * RepoInput.tsx
 * -------------
 * GitHub URL input + Analyze button.
 * Shows a progress indicator while indexing and stats on success.
 */

import { useState, type FormEvent } from "react";

interface Props {
  onAnalyzed: (repoUrl: string, stats: { files: number; chunks: number }) => void;
  isIndexed: boolean;
}

export default function RepoInput({ onAnalyzed, isIndexed: _isIndexed }: Props) {
  const [url, setUrl]           = useState("");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [stats, setStats]       = useState<{ files: number; chunks: number } | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    setError(null);
    setStats(null);

    try {
      const { analyzeRepo } = await import("../api/client");
      const res = await analyzeRepo(url.trim());
      setStats({ files: res.files_indexed, chunks: res.chunks_created });
      onAnalyzed(url.trim(), { files: res.files_indexed, chunks: res.chunks_created });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to analyse repository. Check the URL and try again.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="repo-input-section">
      <h2 className="section-title">
        <span className="step-badge">1</span> Enter GitHub Repository
      </h2>

      <form onSubmit={handleSubmit} className="repo-form">
        <div className="input-row">
          <div className="input-wrapper">
            <span className="input-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
              </svg>
            </span>
            <input
              className="repo-input"
              type="url"
              placeholder="https://github.com/owner/repository"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={loading}
              required
            />
          </div>
          <button
            type="submit"
            className={`btn btn-primary ${loading ? "btn-loading" : ""}`}
            disabled={loading || !url.trim()}
          >
            {loading ? (
              <>
                <span className="spinner" />
                Indexing…
              </>
            ) : (
              <>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
                </svg>
                Analyze Repository
              </>
            )}
          </button>
        </div>
      </form>

      {loading && (
        <div className="status-banner status-loading">
          <span className="spinner-sm" />
          Fetching files, generating embeddings, and building the search index…
          This takes 30–90 seconds for an average-sized repository.
        </div>
      )}

      {error && (
        <div className="status-banner status-error">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          {error}
        </div>
      )}

      {stats && (
        <div className="status-banner status-success">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          Repository indexed! &nbsp;
          <strong>{stats.files} files</strong> → <strong>{stats.chunks} chunks</strong> stored in FAISS.
          Scroll down to ask a question.
        </div>
      )}
    </section>
  );
}
