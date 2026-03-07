/**
 * frontend/src/api/client.ts
 * --------------------------
 * Axios wrapper for the FastAPI backend.
 *
 * - analyzeRepo(repoUrl)          → POST /analyze-repo
 * - askQuestion(repoUrl, question) → POST /ask-question
 */

import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
  timeout: 300_000, // 5 min — large repos take time to index
});

// ── Types ───────────────────────────────────────────────────────────────────

export interface AnalyzeResponse {
  status: string;
  repo: string;
  files_indexed: number;
  chunks_created: number;
  message: string;
}

export interface AskResponse {
  answer: string;
  sources: string[];
  chunks_used: number;
  model_used: string;
}

export interface FileTreeResponse {
  files: string[];
}

// ── API calls ────────────────────────────────────────────────────────────────

export async function analyzeRepo(repoUrl: string): Promise<AnalyzeResponse> {
  const { data } = await api.post<AnalyzeResponse>("/analyze-repo", {
    repo_url: repoUrl,
  });
  return data;
}

export async function getFileTree(repoUrl: string): Promise<FileTreeResponse> {
  const { data } = await api.get<FileTreeResponse>("/file-tree", {
    params: { repo_url: repoUrl },
    timeout: 10_000,
  });
  return data;
}

export async function askQuestion(
  repoUrl: string,
  question: string
): Promise<AskResponse> {
  const { data } = await api.post<AskResponse>("/ask-question", {
    repo_url: repoUrl,
    question,
  });
  return data;
}

export interface StreamCallbacks {
  onToken:  (token: string) => void;
  onDone:   (sources: string[], chunksUsed: number, model: string) => void;
  onError:  (message: string) => void;
}

/**
 * Stream the LLM answer token-by-token via SSE.
 * Calls onToken() for each text chunk and onDone() when the stream ends.
 */
export async function askQuestionStream(
  repoUrl: string,
  question: string,
  callbacks: StreamCallbacks,
): Promise<void> {
  const baseURL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  const response = await fetch(`${baseURL}/ask-question-stream`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ repo_url: repoUrl, question }),
  });

  if (!response.ok || !response.body) {
    callbacks.onError("Failed to connect to streaming endpoint.");
    return;
  }

  const reader  = response.body.getReader();
  const decoder = new TextDecoder();
  let   buffer  = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";      // keep incomplete line in buffer

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const raw = line.slice(6).trim();
      if (raw === "[DONE]") return;

      try {
        const packet = JSON.parse(raw);
        if (packet.error) {
          callbacks.onError(packet.error);
          return;
        }
        if (packet.token !== undefined) {
          callbacks.onToken(packet.token);
        }
        if (packet.done) {
          callbacks.onDone(packet.sources ?? [], packet.chunks_used ?? 0, packet.model ?? "");
          return;
        }
      } catch {
        // malformed SSE line — skip
      }
    }
  }
}
