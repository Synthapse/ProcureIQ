# ProcureIQ — Frontend Specification

## Table of Contents

1. [Overview](#overview)
2. [Single API Endpoint](#single-api-endpoint)
3. [Request Format](#request-format)
4. [SSE Event Contract](#sse-event-contract)
5. [Phase State Machine](#phase-state-machine)
6. [Consuming the Stream](#consuming-the-stream)
7. [UI Component Specification](#ui-component-specification)
8. [TypeScript Types](#typescript-types)
9. [Reference Implementation (React + Fetch)](#reference-implementation-react--fetch)
10. [Example Tool Labels](#example-tool-labels)
11. [Error Handling](#error-handling)

---

## Overview

ProcureIQ exposes a **single HTTP endpoint**. All procurement intelligence queries go through it. The backend streams `text/event-stream` (Server-Sent Events) responses so the UI can show real-time progress as the AI agent works through the question — before the final answer is available.

```
User types question
       ↓
POST /api/v1/chat/
       ↓
  SSE stream opens
       ↓
 phase: thinking          ← show spinner / "Analyzing..."
 phase: tool_call         ← show which data source is being queried
 phase: tool_result       ← show that data was retrieved
 phase: tool_call         ← (may repeat for multiple tools)
 phase: tool_result
 phase: generating        ← show "Generating response..."
 type: done               ← render final answer, close stream
```

---

## Single API Endpoint

| Property | Value |
|---|---|
| Method | `POST` |
| URL | `/api/v1/chat/` |
| Request body | `application/json` |
| Response | `text/event-stream` |
| Auth | None (MVP) |

---

## Request Format

```json
{
  "question": "Which vendors create the highest termination risk next quarter?",
  "user_id": "user-001",
  "conversation_id": "uuid-of-current-thread",
  "tenant_id": "tenant-001"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `question` | `string` | ✅ | Natural language procurement question |
| `user_id` | `string` | ✅ | User identifier (conversations are stored per user in Neo4j) |
| `conversation_id` | `string` | ❌ | Omit for a new thread; send to append this turn to the same conversation |
| `tenant_id` | `string` | ❌ | Optional tenant scope (for multi-tenant deployments) |

---

## SSE Event Contract

Every event arrives as a single line:

```
data: <JSON>\n\n
```

There are three event `type` values:

### `"phase"` — Processing progress

Emitted throughout agent execution to communicate the current backend phase.

```ts
// type === "phase"
{
  type: "phase",
  phase: "thinking" | "tool_call" | "tool_result" | "generating",
  tool?: string,    // set only for tool_call and tool_result
  message?: string  // human-readable label for the phase
}
```

| `phase` | `tool` present | Suggested UI |
|---|---|---|
| `thinking` | ❌ | Spinner + "Analyzing your question…" |
| `tool_call` | ✅ | Tool badge turns **active** (pulsing) |
| `tool_result` | ✅ | Tool badge turns **complete** (checkmark) |
| `generating` | ❌ | Spinner + "Generating response…" |

#### All possible `tool` values

| Tool name | What it does |
|---|---|
| `vendor_risk_analysis` | Queries supplier risk profile and linked contracts |
| `renewal_impact_analysis` | Finds contracts expiring within N days |
| `contract_dependency_lookup` | Fetches contract lines, obligations, and invoices |
| `top_risk_suppliers` | Ranks suppliers by average contract risk score |
| `knowledge_base_search` | Searches contract/policy document knowledge base (RAG) |
| `obligation_status_check` | Lists overdue / pending / completed obligations |
| `supplier_concentration_analysis` | Detects vendor concentration and blast-radius risk |
| `ask_digitalocean_agent` | Queries DigitalOcean hosted agent with connected Knowledge Base |

---

### `"done"` — Final answer ready

```ts
// type === "done"
{
  type: "done",
  answer: string,           // full markdown-formatted answer text
  tool_calls: string[],     // ordered list of tools that were called
  conversation_id: string   // send this on the next request to continue the same thread
}
```

- `answer` may contain **markdown** (bold, lists, headings). Render it with a markdown renderer.
- `tool_calls` lists every tool invoked in order — use this to populate a "Sources" / "Data used" section.
- After receiving `done`, close / stop consuming the stream.

---

### `"error"` — Unrecoverable failure

```ts
// type === "error"
{
  type: "error",
  message: string  // human-readable error description
}
```

- Display the `message` as an inline error (not a page-level alert).
- The stream ends after an `error` event — no `done` will follow.

---

## Phase State Machine

```
                     ┌─────────────────────────────────────┐
                     │             IDLE                     │
                     │  (no active question)                │
                     └──────────────┬──────────────────────┘
                                    │ user submits question
                                    ▼
                     ┌─────────────────────────────────────┐
                     │           THINKING                   │
                     │  phase="thinking"                    │
                     └──────────────┬──────────────────────┘
                                    │
                    ┌───────────────┴──────────────────┐
                    │  (repeats per tool invocation)   │
                    ▼                                  │
       ┌────────────────────────┐                      │
       │      TOOL_CALL         │                      │
       │  phase="tool_call"     │                      │
       └────────────┬───────────┘                      │
                    │                                  │
                    ▼                                  │
       ┌────────────────────────┐                      │
       │      TOOL_RESULT       │                      │
       │  phase="tool_result"   ├──────────────────────┘
       └────────────┬───────────┘
                    │
                    ▼
       ┌────────────────────────┐
       │      GENERATING        │
       │  phase="generating"    │
       └────────────┬───────────┘
                    │
          ┌─────────┴────────┐
          │                  │
          ▼                  ▼
   ┌──────────────┐   ┌──────────────┐
   │    DONE      │   │    ERROR     │
   │  type="done" │   │ type="error" │
   └──────────────┘   └──────────────┘
```

---

## Consuming the Stream

### Option A — `EventSource` (simple, GET-only limitation)

`EventSource` only supports `GET` requests and cannot send a body. **Not recommended** for this API since the endpoint requires `POST`.

### Option B — `fetch` + `ReadableStream` (recommended)

```ts
const response = await fetch("/api/v1/chat/", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ question }),
});

const reader = response.body!.getReader();
const decoder = new TextDecoder();

while (true) {
  const { value, done } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value, { stream: true });
  for (const line of chunk.split("\n")) {
    if (line.startsWith("data: ")) {
      const event = JSON.parse(line.slice(6));
      handleEvent(event);
    }
  }
}
```

---

## UI Component Specification

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  ProcureIQ                                     [health dot] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  CONVERSATION AREA                                   │   │
│  │                                                      │   │
│  │  [User message bubble]                               │   │
│  │                                                      │   │
│  │  [Progress tracker — shown while streaming]          │   │
│  │    ● Analyzing...              (thinking)            │   │
│  │    ● Querying vendor graph     (tool_call active)    │   │
│  │    ✓ Data retrieved            (tool_result)         │   │
│  │    ● Generating response...    (generating)          │   │
│  │                                                      │   │
│  │  [AI answer bubble — rendered after "done"]          │   │
│  │    ┌─────────────────────────────────────────────┐   │   │
│  │    │  [Markdown answer text]                     │   │   │
│  │    ├─────────────────────────────────────────────┤   │   │
│  │    │  Data sources: vendor_risk_analysis  +1     │   │   │
│  │    └─────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────┐  ┌───────────┐   │
│  │  Ask a procurement question...       │  │   Send    │   │
│  └──────────────────────────────────────┘  └───────────┘   │
│                                                             │
│  Suggested: "Which vendors have the highest risk?"          │
│             "What contracts expire in 90 days?"             │
└─────────────────────────────────────────────────────────────┘
```

### Component Tree

```
<App>
  └── <ChatPage>
        ├── <MessageList>
        │     └── <MessageBubble>          (repeats per message)
        │           ├── <UserBubble>
        │           └── <AssistantBubble>
        │                 ├── <PhaseTracker>   (visible while streaming)
        │                 │     └── <PhaseStep> (repeats per phase event)
        │                 ├── <MarkdownAnswer> (visible after "done")
        │                 └── <SourcesBadges>  (visible after "done")
        └── <QuestionInput>
              ├── <textarea>
              └── <SendButton>
```

---

### Component: `<PhaseTracker>`

Visible from first `phase` event until `done`/`error` is received.

| Phase | Icon | Label |
|---|---|---|
| `thinking` | `⏳` animated | `"Analyzing your question…"` |
| `tool_call` | `🔄` pulsing | `"Querying {toolLabel}…"` |
| `tool_result` | `✓` green | `"Data retrieved from {toolLabel}"` |
| `generating` | `✍️` animated | `"Generating response…"` |

Steps accumulate — each new phase event adds a row. Completed steps show a static checkmark; the current step shows an animated indicator.

---

### Component: `<SourcesBadges>`

Rendered below the answer after `done`. One pill badge per unique tool in `tool_calls`.

```
[ 📊 Vendor Risk ]  [ 📅 Renewals ]  [ 📄 Knowledge Base ]
```

Use the label mapping from the [Example Tool Labels](#example-tool-labels) section.

---

### Component: `<MarkdownAnswer>`

- Render `answer` using a markdown library (e.g. `react-markdown` with `remark-gfm`).
- Support: bold, italic, unordered lists, ordered lists, inline code, tables.
- Apply a subtle fade-in animation when first rendered.

---

### Component: `<QuestionInput>`

| State | Behaviour |
|---|---|
| Idle | Input enabled, Send button enabled |
| Streaming | Input disabled, Send button shows spinner + "Thinking…", disabled |
| Error | Input re-enabled, error message shown inline above input |

---

## TypeScript Types

```ts
// All possible SSE events from POST /api/v1/chat/
export type PhaseType = "thinking" | "tool_call" | "tool_result" | "generating";

export type ToolName =
  | "vendor_risk_analysis"
  | "renewal_impact_analysis"
  | "contract_dependency_lookup"
  | "top_risk_suppliers"
  | "knowledge_base_search"
  | "obligation_status_check"
  | "supplier_concentration_analysis"
  | "ask_digitalocean_agent";

export interface PhaseEvent {
  type: "phase";
  phase: PhaseType;
  tool?: ToolName;
  message?: string;
}

export interface DoneEvent {
  type: "done";
  answer: string;
  tool_calls: ToolName[];
  conversation_id: string;  // use in next request to keep thread
}

export interface ErrorEvent {
  type: "error";
  message: string;
}

export type StreamEvent = PhaseEvent | DoneEvent | ErrorEvent;

// Request body
export interface ChatRequest {
  question: string;
  user_id: string;
  conversation_id?: string;  // omit for new thread; send to continue same conversation
  tenant_id?: string;
}

// UI state
export type ChatStatus = "idle" | "streaming" | "done" | "error";

export interface PhaseStep {
  phase: PhaseType;
  tool?: ToolName;
  message: string;
  status: "active" | "complete";
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content?: string;        // set on assistant message after "done"
  toolCalls?: ToolName[];  // set on assistant message after "done"
  phases?: PhaseStep[];    // accumulates during streaming
  status: ChatStatus;
  errorMessage?: string;
}
```

---

## Reference Implementation (React + Fetch)

### `useProcureChat` hook

```ts
import { useState, useCallback, useRef } from "react";
import type {
  ChatRequest,
  ChatStatus,
  Message,
  PhaseStep,
  StreamEvent,
  PhaseEvent,
  DoneEvent,
  ErrorEvent,
} from "./types";

const API_URL = "/api/v1/chat/";

function makeId() {
  return Math.random().toString(36).slice(2);
}

export function useProcureChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<ChatStatus>("idle");
  const abortRef = useRef<AbortController | null>(null);

  const [conversationId, setConversationId] = useState<string | null>(null);

  const sendQuestion = useCallback(async (question: string, userId: string, tenantId?: string) => {
    // Cancel any in-flight request
    abortRef.current?.abort();
    const abort = new AbortController();
    abortRef.current = abort;

    const userMsg: Message = { id: makeId(), role: "user", content: question, status: "done" };
    const assistantId = makeId();
    const assistantMsg: Message = { id: assistantId, role: "assistant", phases: [], status: "streaming" };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setStatus("streaming");

    const body: ChatRequest = {
      question,
      user_id: userId,
      ...(conversationId ? { conversation_id: conversationId } : {}),
      ...(tenantId ? { tenant_id: tenantId } : {}),
    };

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: abort.signal,
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep incomplete last line in buffer
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const raw = line.slice(5).trim();
          if (!raw) continue;

          let event: StreamEvent;
          try {
            event = JSON.parse(raw);
          } catch {
            continue;
          }

          handleEvent(event, assistantId);
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name === "AbortError") return;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, status: "error", errorMessage: (err as Error).message }
            : m
        )
      );
      setStatus("error");
    }
  }, []);

  function handleEvent(event: StreamEvent, assistantId: string) {
    if (event.type === "phase") {
      const phase = event as PhaseEvent;
      const step: PhaseStep = {
        phase: phase.phase,
        tool: phase.tool as any,
        message: phase.message ?? phase.phase,
        status: "active",
      };
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== assistantId) return m;
          const prevPhases = (m.phases ?? []).map((p) => ({ ...p, status: "complete" as const }));
          return { ...m, phases: [...prevPhases, step] };
        })
      );
    }

    if (event.type === "done") {
      const done = event as DoneEvent;
      if (done.conversation_id) setConversationId(done.conversation_id);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: done.answer,
                toolCalls: done.tool_calls,
                phases: (m.phases ?? []).map((p) => ({ ...p, status: "complete" })),
                status: "done",
              }
            : m
        )
      );
      setStatus("done");
    }

    if (event.type === "error") {
      const err = event as ErrorEvent;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, status: "error", errorMessage: err.message }
            : m
        )
      );
      setStatus("error");
    }
  }

  return { messages, status, sendQuestion };
}
```

### `<PhaseTracker>` component

```tsx
import type { PhaseStep, ToolName } from "./types";

const TOOL_LABELS: Record<ToolName, string> = {
  vendor_risk_analysis:         "Vendor Risk Graph",
  renewal_impact_analysis:      "Renewal Timeline",
  contract_dependency_lookup:   "Contract Dependencies",
  top_risk_suppliers:           "Risk Rankings",
  knowledge_base_search:        "Knowledge Base (RAG)",
  obligation_status_check:      "Obligation Status",
  supplier_concentration_analysis: "Concentration Risk",
  ask_digitalocean_agent:       "DO Agent (KB)",
};

const PHASE_LABELS: Record<string, string> = {
  thinking:    "Analyzing your question…",
  tool_call:   "Querying data…",
  tool_result: "Data retrieved",
  generating:  "Generating response…",
};

export function PhaseTracker({ steps }: { steps: PhaseStep[] }) {
  return (
    <ul className="phase-tracker">
      {steps.map((step, i) => {
        const isActive = step.status === "active";
        const label =
          step.tool
            ? (step.phase === "tool_call" ? `Querying ${TOOL_LABELS[step.tool] ?? step.tool}…`
                                          : `Retrieved from ${TOOL_LABELS[step.tool] ?? step.tool}`)
            : PHASE_LABELS[step.phase] ?? step.message;

        return (
          <li key={i} className={`phase-step phase-step--${isActive ? "active" : "done"}`}>
            <span className="phase-step__icon">{isActive ? "⏳" : "✓"}</span>
            <span className="phase-step__label">{label}</span>
          </li>
        );
      })}
    </ul>
  );
}
```

---

## Example Tool Labels

Use these human-readable labels anywhere the raw tool name would be shown to end users:

| Tool name | UI label | Icon |
|---|---|---|
| `vendor_risk_analysis` | Vendor Risk Graph | 📊 |
| `renewal_impact_analysis` | Renewal Timeline | 📅 |
| `contract_dependency_lookup` | Contract Details | 📋 |
| `top_risk_suppliers` | Risk Rankings | ⚠️ |
| `knowledge_base_search` | Knowledge Base | 📄 |
| `obligation_status_check` | Obligation Status | ✅ |
| `supplier_concentration_analysis` | Concentration Risk | 🕸️ |
| `ask_digitalocean_agent` | DO Agent (KB) | 🤖 |

---

## Error Handling

| Scenario | What happens | Suggested UI |
|---|---|---|
| Backend error (agent / Neo4j) | `{"type":"error","message":"..."}` event | Inline red message below answer area, "Try again" button |
| Network failure | `fetch` throws | Same inline error treatment |
| HTTP non-200 | `fetch` returns non-ok response | Show `"Service unavailable. Please try again."` |
| Stream ends without `done` | Reader `done=true` before `done` event | Show `"Response incomplete. Please try again."` |
| User submits new question mid-stream | Previous `AbortController` is aborted | Silently discard previous stream, begin new one |

---

## Suggested Starter Questions

Surface these as clickable chips below the input when the conversation is empty:

```ts
const STARTER_QUESTIONS = [
  "Which vendors create the highest termination risk next quarter?",
  "What contracts are expiring in the next 90 days?",
  "Which supplier has the highest concentration risk?",
  "Are there any overdue contract obligations?",
  "What is the risk profile of TechFlow Solutions?",
  "Which renewals are tied to high-risk clauses?",
];
```
