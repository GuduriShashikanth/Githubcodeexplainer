/**
 * QuestionBox.tsx
 * ---------------
 * Textarea for the user's question + Submit button.
 * Disabled until a repository is indexed.
 */

import { useState, type FormEvent, type KeyboardEvent } from "react";

interface Props {
  repoUrl: string;
  isIndexed: boolean;
  onAnswer: (answer: string, sources: string[], chunks: number, model: string) => void;
  isAsking: boolean;
  setIsAsking: (v: boolean) => void;
}

export default function QuestionBox({
  repoUrl,
  isIndexed,
  onAnswer,
  isAsking,
  setIsAsking,
}: Props) {
  const [question, setQuestion] = useState("");
  const [error, setError]       = useState<string | null>(null);

  const submit = async () => {
    if (!question.trim() || !isIndexed || isAsking) return;
    setIsAsking(true);
    setError(null);

    try {
      const { askQuestion } = await import("../api/client");
      const res = await askQuestion(repoUrl, question.trim());
      onAnswer(res.answer, res.sources, res.chunks_used, res.model_used);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to get an answer. Please try again.";
      setError(msg);
    } finally {
      setIsAsking(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit();
  };

  // Submit on Ctrl+Enter / Cmd+Enter
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  };

  // Sample questions to help users get started
  const samples = [
    "Explain the overall architecture",
    "How does authentication work?",
    "Where is the database connection defined?",
    "What are the main dependencies?",
  ];

  return (
    <section className={`question-section ${!isIndexed ? "section-disabled" : ""}`}>
      <h2 className="section-title">
        <span className="step-badge">2</span> Ask a Question
        {!isIndexed && <span className="badge-hint">Index a repo first</span>}
      </h2>

      {/* Sample question chips */}
      {isIndexed && (
        <div className="sample-questions">
          {samples.map((s) => (
            <button
              key={s}
              className="chip"
              onClick={() => setQuestion(s)}
              disabled={isAsking}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="question-form">
        <textarea
          className="question-textarea"
          placeholder={
            isIndexed
              ? "How does authentication work? (Ctrl+Enter to submit)"
              : "Index a repository above before asking questions…"
          }
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={!isIndexed || isAsking}
          rows={4}
        />
        <div className="question-footer">
          <span className="char-hint">Ctrl+Enter to submit</span>
          <button
            type="submit"
            className={`btn btn-accent ${isAsking ? "btn-loading" : ""}`}
            disabled={!isIndexed || !question.trim() || isAsking}
          >
            {isAsking ? (
              <>
                <span className="spinner" />
                Thinking…
              </>
            ) : (
              <>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
                Ask
              </>
            )}
          </button>
        </div>
      </form>

      {error && (
        <div className="status-banner status-error">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          {error}
        </div>
      )}
    </section>
  );
}
