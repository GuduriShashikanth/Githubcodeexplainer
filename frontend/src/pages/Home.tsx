/**
 * pages/Home.tsx
 * --------------
 * Two-panel layout:
 *   LEFT  — Sidebar (URL input, pipeline status, repo info)
 *   RIGHT — Chat panel (messages + input bar)
 */

import { useState, useRef, useEffect, type FormEvent, type KeyboardEvent } from "react";
import ChatBubble, { type ChatMessage } from "../components/ChatBubble";
import Sidebar, { type SidebarState } from "../components/Sidebar";
import { analyzeRepo, askQuestion, getFileTree } from "../api/client";
import type { AnalyzeResponse } from "../api/client";

type AppState = "idle" | "indexing" | "ready" | "asking";

const WELCOME: ChatMessage = {
  id:        "welcome",
  role:      "assistant",
  type:      "text",
  content:   `👋 **Welcome!** Paste a GitHub repository URL in the sidebar to get started. Once indexed, you can ask me anything about the codebase.`,
  timestamp: new Date(),
};

function makeId() { return Math.random().toString(36).slice(2, 9); }

export default function Home() {
  const [messages,  setMessages]  = useState<ChatMessage[]>([WELCOME]);
  const [input,     setInput]     = useState("");
  const [appState,  setAppState]  = useState<AppState>("idle");
  const [repoUrl,   setRepoUrl]   = useState("");
  const [repoInfo,  setRepoInfo]  = useState<AnalyzeResponse | null>(null);
  const [indexedFiles, setIndexedFiles] = useState<string[]>([]);
  const scrollRef                 = useRef<HTMLDivElement>(null);  // scroll container
  const bottomRef                 = useRef<HTMLDivElement>(null);  // sentinel
  const stopRef                   = useRef<(() => void) | null>(null); // cancels typewriter
  const userScrolledRef           = useRef(false); // true when user scrolled up manually

  const sidebarState: SidebarState =
    appState === "idle"     ? "idle"     :
    appState === "indexing" ? "indexing" : "ready";

  // Smart auto-scroll: only follow if user hasn't manually scrolled up
  useEffect(() => {
    if (userScrolledRef.current) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Detect manual user scroll — pause auto-scroll when they scroll up
  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    userScrolledRef.current = !nearBottom;
  };

  const addLoading = () => {
    const id = makeId();
    setMessages((prev) => [
      ...prev,
      { id, role: "assistant", type: "loading", content: "", timestamp: new Date() },
    ]);
    return id;
  };

  const removeLoading = () =>
    setMessages((prev) => prev.filter((m) => m.type !== "loading"));

  const addMessage = (msg: Omit<ChatMessage, "id" | "timestamp">) => {
    const full: ChatMessage = { ...msg, id: makeId(), timestamp: new Date() };
    setMessages((prev) => prev.filter((m) => m.type !== "loading").concat(full));
    return full.id;
  };

  // ── Sidebar: analyse repo ─────────────────────────────────────────────────
  const handleAnalyse = async (url: string) => {
    setRepoUrl(url);
    setAppState("indexing");
    setMessages([]); // chat is empty while sidebar shows pipeline progress

    try {
      const res = await analyzeRepo(url);
      setRepoInfo(res);
      // Fetch full file list for sidebar explorer (non-blocking)
      getFileTree(url).then((ft) => setIndexedFiles(ft.files)).catch(() => {});
      setMessages([{
        id:        makeId(),
        role:      "assistant",
        type:      "text",
        content:   `✅ **\`${res.repo}\`** is indexed and ready!\n\nI processed **${res.files_indexed} files** → **${res.chunks_created} chunks**.\n\nAsk me anything about this codebase below.`,
        timestamp: new Date(),
      }]);
      setAppState("ready");
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to load the repository. Please check the URL and try again.";
      setMessages([{
        id:        makeId(),
        role:      "assistant",
        type:      "error",
        content:   `❌ ${detail}`,
        timestamp: new Date(),
      }]);
      setAppState("idle");
      setRepoInfo(null);
    }
  };

  // ── Sidebar: reset ────────────────────────────────────────────────────────
  const handleReset = () => {
    setAppState("idle");
    setRepoUrl("");
    setRepoInfo(null);
    setIndexedFiles([]);
    setMessages([WELCOME]);
  };

  // ── Chat: submit question ─────────────────────────────────────────────────
  const handleSubmit = async (e?: FormEvent) => {
    e?.preventDefault();
    const text = input.trim();
    if (!text || appState !== "ready") return;
    setInput("");

    setMessages((prev) => [
      ...prev,
      { id: makeId(), role: "user", type: "text", content: text, timestamp: new Date() },
    ]);

    setAppState("asking");
    addLoading();

    try {
      const res = await askQuestion(repoUrl, text);

      // Swap loading → empty typewriter bubble
      const writeId = makeId();
      const full    = res.answer;
      setMessages((prev) => [
        ...prev.filter((m) => m.type !== "loading"),
        { id: writeId, role: "assistant", type: "text",
          content: "", streaming: true, timestamp: new Date() },
      ]);

      // Typewriter replay at 60fps — cancellable via stopRef
      let idx = 0;
      const CHARS_PER_TICK = 3;
      const INTERVAL_MS    = 16;

      await new Promise<void>((resolve) => {
        const finalise = (upTo: number) => {
          clearInterval(timer);
          stopRef.current = null;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === writeId
                ? { ...m, content: full.slice(0, upTo), streaming: false,
                    sources: res.sources, chunksUsed: res.chunks_used,
                    model: res.model_used }
                : m
            )
          );
          setAppState("ready");
          resolve();
        };

        // Register stop callback so the button can call it
        stopRef.current = () => finalise(idx);

        const timer = setInterval(() => {
          idx += CHARS_PER_TICK;
          const slice = full.slice(0, idx);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === writeId ? { ...m, content: slice } : m
            )
          );
          if (idx >= full.length) finalise(full.length);
        }, INTERVAL_MS);
      });
    } catch (err: unknown) {
      removeLoading();
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Something went wrong. Please try again.";
      addMessage({ role: "assistant", type: "error", content: `❌ ${detail}` });
    } finally {
      setAppState("ready");
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
  };

  const isAsking = appState === "asking";
  const canChat  = appState === "ready" || isAsking;

  return (
    <div className="home-layout">
      {/* ── Left Sidebar ── */}
      <Sidebar
        state={sidebarState}
        repoInfo={repoInfo}
        files={indexedFiles}
        onSubmit={handleAnalyse}
        onReset={handleReset}
      />

      {/* ── Right Chat Panel ── */}
      <div className="chat-panel">
        <div className="chat-messages" ref={scrollRef} onScroll={handleScroll}>
          {messages.map((msg) => <ChatBubble key={msg.id} message={msg} />)}
          <div ref={bottomRef} />
        </div>

        <form className="chat-input-form" onSubmit={handleSubmit}>
          <div className={`chat-input-wrapper ${!canChat ? "chat-input-wrapper--locked" : ""}`}>
            <textarea
              className="chat-input"
              placeholder={
                appState === "idle"     ? "Index a repository first using the sidebar…" :
                appState === "indexing" ? "Indexing in progress, please wait…" :
                isAsking                ? "Waiting for answer…" :
                "Ask a question about the codebase… (Enter to send)"
              }
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={!canChat || isAsking}
              rows={1}
            />
            <button
              type="submit"
              className="chat-send-btn"
              disabled={!canChat || isAsking || !input.trim()}
            >
              {isAsking ? (
                <span className="spinner" />
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="22" y1="2" x2="11" y2="13"/>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
              )}
            </button>
          </div>
          <p className="chat-input-hint">
            {appState === "ready"
              ? "Enter to send · Shift+Enter for new line"
              : ""}
          </p>
          {/* Stop button — shown while typewriter is running */}
          {isAsking && (
            <div className="chat-stop-row">
              <button
                type="button"
                className="chat-stop-btn"
                onClick={() => stopRef.current?.()}
              >
                <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
                  <rect width="10" height="10" rx="2"/>
                </svg>
                Stop generating
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
