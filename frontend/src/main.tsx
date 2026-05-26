import React, { useState, useRef, useEffect } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

// ── Types ──────────────────────────────────────────────────────────────────────
interface Message {
  role: "user" | "assistant";
  content: string;
  sql?: string;
  row_count?: number;
  attempts?: number;
  error?: boolean;
}

interface HealthStatus {
  status: "ok" | "degraded";
  db_connected: boolean;
  chain_ready: boolean;
  db_error?: string | null;
  llm_provider: string;
  llm_configured: boolean;
  llm_error?: string | null;
}

// ── API ────────────────────────────────────────────────────────────────────────
const api = {
  async ask(question: string) {
    const r = await fetch("/api/v1/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, debug: false }),
    });
    if (!r.ok) throw new Error((await r.json()).detail ?? "Lỗi server");
    return r.json();
  },
  async schema(): Promise<{ tables: string[]; total_tables: number }> {
    const r = await fetch("/api/v1/schema");
    if (!r.ok) throw new Error("Không tải được schema");
    return r.json();
  },
  async health(): Promise<HealthStatus> {
    const r = await fetch("/api/v1/health");
    return r.json();
  },
};

const SUGGESTIONS = [
  "Top 5 sản phẩm bán chạy nhất?",
  "Doanh thu theo từng quốc gia?",
  "Nhân viên nào bán hàng giỏi nhất?",
  "Có bao nhiêu đơn hàng bị giao trễ?",
  "Danh mục nào có doanh thu cao nhất?",
  "Khách hàng nào đặt hàng nhiều nhất?",
];

// ── SQL block ──────────────────────────────────────────────────────────────────
function SqlBlock({ sql }: { sql: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="sql-block">
      <button className="sql-toggle" onClick={() => setOpen((o) => !o)}>
        <span>{open ? "▼" : "▶"}</span> Xem câu SQL đã dùng
      </button>
      {open && <pre className="sql-code">{sql}</pre>}
    </div>
  );
}

// ── App ────────────────────────────────────────────────────────────────────────
function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Xin chào! Tôi có thể giúp bạn truy vấn dữ liệu từ hệ thống Northwind. Hãy hỏi bằng tiếng Việt tự nhiên.",
    },
  ]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<"chat" | "schema">("chat");
  const [tables, setTables] = useState<string[]>([]);
  const [tablesLoaded, setTablesLoaded] = useState(false);
  const [health, setHealth] = useState<"ok" | "degraded" | "error" | "unknown">("unknown");
  const [healthDetail, setHealthDetail] = useState("Dang kiem tra");
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    api.health()
      .then((d) => {
        setHealth(d.status === "ok" ? "ok" : "degraded");
        if (!d.db_connected) {
          setHealthDetail("DB chua ket noi");
        } else if (!d.llm_configured) {
          setHealthDetail(`AI chua cau hinh (${d.llm_provider})`);
        } else if (!d.chain_ready) {
          setHealthDetail("Chain chua san sang");
        } else {
          setHealthDetail("He thong san sang");
        }
      })
      .catch(() => {
        setHealth("error");
        setHealthDetail("Khong goi duoc API");
      });
  }, []);

  async function loadSchema() {
    if (tablesLoaded) return;
    try {
      const d = await api.schema();
      setTables(d.tables ?? []);
      setTablesLoaded(true);
    } catch {
      setTables([]);
    }
  }

  async function send(q: string) {
    if (!q.trim() || busy) return;
    setMessages((m) => [...m, { role: "user", content: q }]);
    setQuestion("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setBusy(true);
    try {
      const d = await api.ask(q);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: d.answer,
          sql: d.sql,
          row_count: d.row_count,
          attempts: d.attempts,
        },
      ]);
    } catch (e: unknown) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: (e as Error).message, error: true },
      ]);
    } finally {
      setBusy(false);
    }
  }

  const healthDot =
    health === "ok" ? "dot-green" : health === "degraded" ? "dot-yellow" : "dot-red";

  return (
    <div className="layout">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">N</div>
          <div>
            <div className="brand-name">Northwind</div>
            <div className="brand-sub">SQL Chatbot</div>
          </div>
        </div>

        <div className="health-row">
          <span className={`dot ${healthDot}`} />
          <span className="health-label" title={healthDetail}>
            {health === "unknown" ? "Dang kiem tra..." : healthDetail}
          </span>
        </div>

        <nav>
          <button
            className={`nav-item${tab === "chat" ? " active" : ""}`}
            onClick={() => setTab("chat")}
          >
            💬 Hỏi đáp dữ liệu
          </button>
          <button
            className={`nav-item${tab === "schema" ? " active" : ""}`}
            onClick={() => {
              setTab("schema");
              loadSchema();
            }}
          >
            🗄️ Schema database
          </button>
        </nav>

        <div className="divider" />

        <div className="sugg-label">Câu hỏi gợi ý</div>
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              className="chip"
              onClick={() => {
                setTab("chat");
                send(s);
              }}
            >
              {s}
            </button>
          ))}
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main">
        {/* Chat */}
        {tab === "chat" && (
          <div className="panel chat-panel">
            <div className="messages">
              {messages.map((msg, i) => (
                <div key={i} className={`msg-row ${msg.role}`}>
                  <div className={`avatar ${msg.role === "assistant" ? "bot" : "user"}`}>
                    {msg.role === "assistant" ? "N" : "B"}
                  </div>
                  <div className="msg-body">
                    <div className={`bubble${msg.error ? " error" : ""}`}>
                      {msg.content
                        .split("\n")
                        .map((line, j) =>
                          line.trim() === "" ? (
                            <br key={j} />
                          ) : (
                            <span key={j} style={{ display: "block" }}>
                              {line}
                            </span>
                          )
                        )}
                      {msg.sql && <SqlBlock sql={msg.sql} />}
                    </div>
                    {msg.role === "assistant" && msg.row_count !== undefined && (
                      <div className="msg-meta">
                        {msg.row_count} dòng dữ liệu · {msg.attempts} lần thử
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {busy && (
                <div className="msg-row assistant">
                  <div className="avatar bot">N</div>
                  <div className="bubble typing">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            <div className="input-bar">
              <textarea
                ref={textareaRef}
                rows={1}
                placeholder="Hỏi về dữ liệu kinh doanh… (Enter để gửi)"
                value={question}
                disabled={busy}
                onChange={(e) => {
                  setQuestion(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = Math.min(e.target.scrollHeight, 140) + "px";
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send(question);
                  }
                }}
              />
              <button
                className="send-btn"
                disabled={busy || !question.trim()}
                onClick={() => send(question)}
              >
                <svg viewBox="0 0 24 24">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                </svg>
              </button>
            </div>
            <div className="input-hint">Enter để gửi · Shift+Enter xuống dòng</div>
          </div>
        )}

        {/* Schema */}
        {tab === "schema" && (
          <div className="panel">
            <div className="panel-head">
              Schema Database
              <span className="muted"> — {tables.length} bảng</span>
            </div>
            {tables.length === 0 ? (
              <div className="empty">
                <div className="empty-icon">🗄️</div>
                <div className="empty-title">Đang tải schema…</div>
              </div>
            ) : (
              <div className="table-grid">
                {tables.map((t) => (
                  <div key={t} className="table-card">
                    <span className="table-icon">📋</span>
                    <span className="table-name">{t}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
