/**
 * AnswerDisplay.tsx
 * -----------------
 * Renders the LLM answer as formatted markdown.
 * Shows source file chips and a collapsible model info tag.
 */

import { useState } from "react";
import ReactMarkdown from "react-markdown";

interface Props {
  answer: string;
  sources: string[];
  chunksUsed: number;
  modelUsed: string;
  isAsking: boolean;
}

export default function AnswerDisplay({
  answer,
  sources,
  chunksUsed,
  modelUsed,
  isAsking,
}: Props) {
  const [showSources, setShowSources] = useState(true);

  if (isAsking) {
    return (
      <section className="answer-section">
        <div className="answer-skeleton">
          <div className="skeleton-line skeleton-line--80" />
          <div className="skeleton-line skeleton-line--60" />
          <div className="skeleton-line skeleton-line--90" />
          <div className="skeleton-line skeleton-line--50" />
        </div>
      </section>
    );
  }

  if (!answer) return null;

  return (
    <section className="answer-section">
      <div className="answer-header">
        <h2 className="section-title">
          <span className="step-badge step-badge--green">3</span> Answer
        </h2>
        <div className="answer-meta">
          <span className="meta-chip">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
            </svg>
            {modelUsed}
          </span>
          <span className="meta-chip">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
            </svg>
            {chunksUsed} chunk{chunksUsed !== 1 ? "s" : ""} retrieved
          </span>
        </div>
      </div>

      {/* Markdown answer */}
      <div className="answer-body">
        <ReactMarkdown>{answer}</ReactMarkdown>
      </div>

      {/* Source files */}
      {sources.length > 0 && (
        <div className="sources-section">
          <button
            className="sources-toggle"
            onClick={() => setShowSources((v) => !v)}
          >
            <svg
              width="14" height="14" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2"
              style={{ transform: showSources ? "rotate(90deg)" : "none", transition: "transform 0.2s" }}
            >
              <polyline points="9 18 15 12 9 6"/>
            </svg>
            {showSources ? "Hide" : "Show"} source files ({sources.length})
          </button>

          {showSources && (
            <div className="sources-list">
              {sources.map((s) => (
                <span key={s} className="source-chip">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
                  </svg>
                  {s}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
