/**
 * components/ChatBubble.tsx
 * -------------------------
 * Renders a single chat message — user or assistant.
 */

import ReactMarkdown from "react-markdown";

export type MessageRole = "user" | "assistant";
export type MessageType = "text" | "loading" | "error" | "indexed";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  type: MessageType;
  content: string;
  streaming?: boolean;   // true while tokens are still arriving
  sources?: string[];
  chunksUsed?: number;
  model?: string;
  timestamp: Date;
}

interface Props {
  message: ChatMessage;
}

export default function ChatBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`chat-row ${isUser ? "chat-row--user" : "chat-row--assistant"}`}>
      {/* Avatar */}
      {!isUser && (
        <div className="chat-avatar chat-avatar--ai">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
          </svg>
        </div>
      )}

      <div className={`chat-bubble ${isUser ? "chat-bubble--user" : "chat-bubble--assistant"}`}>

        {/* Loading dots */}
        {message.type === "loading" && (
          <div className="chat-typing">
            <span /><span /><span />
          </div>
        )}

        {/* Normal text / markdown */}
        {message.type !== "loading" && (
          <div className={`chat-content ${isUser ? "chat-content--plain" : "chat-content--markdown"}`}>
            {isUser ? (
              <p>{message.content}</p>
            ) : (
              <>
                <ReactMarkdown>{message.content}</ReactMarkdown>
                {message.streaming && <span className="stream-cursor" />}
              </>
            )}
          </div>
        )}

        {/* Sources */}
        {message.sources && message.sources.length > 0 && (
          <div className="chat-sources">
            <span className="chat-sources-label">Sources</span>
            <div className="chat-sources-list">
              {message.sources.map((s) => (
                <span key={s} className="chat-source-chip">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                  </svg>
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Meta: chunks + timestamp */}
        {!isUser && message.type !== "loading" && message.chunksUsed !== undefined && (
          <div className="chat-meta">
            <span>{message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
          </div>
        )}
      </div>

      {/* User avatar */}
      {isUser && (
        <div className="chat-avatar chat-avatar--user">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
          </svg>
        </div>
      )}
    </div>
  );
}
