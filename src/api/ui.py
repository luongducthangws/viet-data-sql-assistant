from fastapi.responses import HTMLResponse


APP_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Northwind Chatbot</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f5f5f4;
      height: 100vh;
      display: flex;
      flex-direction: column;
      color: #1a1a1a;
    }

    header {
      background: #fff;
      border-bottom: 0.5px solid #e0ddd6;
      padding: 14px 24px;
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .logo {
      width: 36px; height: 36px;
      background: #1D9E75;
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      color: #fff;
      font-weight: 600;
      font-size: 16px;
    }

    header h1 { font-size: 16px; font-weight: 500; }
    header p  { font-size: 13px; color: #888780; }

    .status-dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      background: #1D9E75;
      margin-left: auto;
    }

    #chat {
      flex: 1;
      overflow-y: auto;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .suggestions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 8px;
    }

    .suggestion {
      background: #fff;
      border: 0.5px solid #e0ddd6;
      border-radius: 20px;
      padding: 8px 16px;
      font-size: 13px;
      color: #444441;
      cursor: pointer;
      transition: background 0.15s;
    }
    .suggestion:hover { background: #f1efe8; }

    .msg {
      display: flex;
      gap: 10px;
      max-width: 720px;
    }
    .msg.user { align-self: flex-end; flex-direction: row-reverse; }

    .avatar {
      width: 32px; height: 32px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 13px; font-weight: 500;
      flex-shrink: 0;
    }
    .avatar.bot { background: #e1f5ee; color: #085041; }
    .avatar.user { background: #eeedfe; color: #3c3489; }

    .bubble {
      padding: 12px 16px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.6;
      max-width: 580px;
    }
    .msg.bot .bubble {
      background: #fff;
      border: 0.5px solid #e0ddd6;
      border-top-left-radius: 4px;
    }
    .msg.user .bubble {
      background: #1D9E75;
      color: #fff;
      border-top-right-radius: 4px;
    }

    .sql-block {
      margin-top: 10px;
      background: #f1efe8;
      border-radius: 8px;
      overflow: hidden;
    }
    .sql-toggle {
      font-size: 12px;
      color: #888780;
      padding: 6px 12px;
      cursor: pointer;
      user-select: none;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .sql-toggle:hover { color: #444441; }
    .sql-code {
      display: none;
      padding: 10px 12px;
      font-family: 'Courier New', monospace;
      font-size: 12px;
      color: #3c3489;
      white-space: pre-wrap;
      border-top: 0.5px solid #e0ddd6;
    }
    .sql-code.open { display: block; }

    .meta {
      font-size: 11px;
      color: #b4b2a9;
      margin-top: 6px;
      padding-left: 42px;
    }

    .typing {
      display: flex;
      gap: 4px;
      padding: 14px 16px;
      background: #fff;
      border: 0.5px solid #e0ddd6;
      border-radius: 16px;
      border-top-left-radius: 4px;
      width: fit-content;
    }
    .dot {
      width: 7px; height: 7px;
      border-radius: 50%;
      background: #b4b2a9;
      animation: bounce 1.2s infinite;
    }
    .dot:nth-child(2) { animation-delay: 0.2s; }
    .dot:nth-child(3) { animation-delay: 0.4s; }
    @keyframes bounce {
      0%, 80%, 100% { transform: translateY(0); }
      40% { transform: translateY(-6px); }
    }

    footer {
      background: #fff;
      border-top: 0.5px solid #e0ddd6;
      padding: 16px 24px;
    }

    .input-row {
      display: flex;
      gap: 10px;
      align-items: flex-end;
    }

    #question {
      flex: 1;
      border: 0.5px solid #d3d1c7;
      border-radius: 12px;
      padding: 12px 16px;
      font-size: 14px;
      font-family: inherit;
      resize: none;
      outline: none;
      line-height: 1.5;
      min-height: 48px;
      max-height: 140px;
      overflow-y: auto;
      color: #1a1a1a;
      background: #fff;
    }
    #question:focus { border-color: #1D9E75; }
    #question::placeholder { color: #b4b2a9; }

    #send {
      width: 44px; height: 44px;
      border-radius: 12px;
      background: #1D9E75;
      border: none;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
      transition: background 0.15s;
    }
    #send:hover { background: #0f6e56; }
    #send:disabled { background: #9fe1cb; cursor: not-allowed; }
    #send svg { width: 18px; height: 18px; fill: #fff; }

    .hint { font-size: 12px; color: #b4b2a9; margin-top: 8px; text-align: center; }
  </style>
</head>
<body>

<header>
  <div class="logo">N</div>
  <div>
    <h1>Northwind Chatbot</h1>
    <p>Tr\u1ee3 l\u00fd d\u1eef li\u1ec7u n\u1ed9i b\u1ed9</p>
  </div>
  <div class="status-dot" title="\u0110ang ho\u1ea1t \u0111\u1ed9ng"></div>
</header>

<div id="chat">
  <div class="msg bot">
    <div class="avatar bot">N</div>
    <div>
      <div class="bubble">
        Xin ch\u00e0o! T\u00f4i c\u00f3 th\u1ec3 gi\u00fap b\u1ea1n truy v\u1ea5n d\u1eef li\u1ec7u t\u1eeb h\u1ec7 th\u1ed1ng Northwind. H\u00e3y h\u1ecfi b\u1eb1ng ti\u1ebfng Vi\u1ec7t t\u1ef1 nhi\u00ean.
      </div>
    </div>
  </div>

  <div class="suggestions">
    <button class="suggestion" onclick="ask(this.textContent)">Top 5 s\u1ea3n ph\u1ea9m b\u00e1n ch\u1ea1y nh\u1ea5t?</button>
    <button class="suggestion" onclick="ask(this.textContent)">Doanh thu theo t\u1eebng qu\u1ed1c gia?</button>
    <button class="suggestion" onclick="ask(this.textContent)">Nh\u00e2n vi\u00ean n\u00e0o b\u00e1n h\u00e0ng gi\u1ecfi nh\u1ea5t?</button>
    <button class="suggestion" onclick="ask(this.textContent)">C\u00f3 bao nhi\u00eau \u0111\u01a1n h\u00e0ng b\u1ecb giao tr\u1ec5?</button>
  </div>
</div>

<footer>
  <div class="input-row">
    <textarea id="question" placeholder="H\u1ecfi v\u1ec1 d\u1eef li\u1ec7u kinh doanh..." rows="1"></textarea>
    <button id="send" onclick="sendMsg()">
      <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
    </button>
  </div>
  <p class="hint">Enter \u0111\u1ec3 g\u1eedi \u00b7 Shift+Enter xu\u1ed1ng d\u00f2ng</p>
</footer>

<script>
  const chat = document.getElementById('chat');
  const input = document.getElementById('question');
  const btn = document.getElementById('send');
  const API = '/api/v1/ask';

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMsg(); }
  });
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 140) + 'px';
  });

  function addMsg(role, html) {
    const el = document.createElement('div');
    el.className = 'msg ' + role;
    const initials = role === 'bot' ? 'N' : 'B';
    el.innerHTML = `<div class="avatar ${role}">${initials}</div><div><div class="bubble">${html}</div></div>`;
    chat.appendChild(el);
    chat.scrollTop = chat.scrollHeight;
    return el;
  }

  function showTyping() {
    const el = document.createElement('div');
    el.className = 'msg bot';
    el.id = 'typing';
    el.innerHTML = `<div class="avatar bot">N</div><div class="typing"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>`;
    chat.appendChild(el);
    chat.scrollTop = chat.scrollHeight;
  }

  function removeTyping() {
    const el = document.getElementById('typing');
    if (el) el.remove();
  }

  async function ask(question) {
    if (!question.trim()) return;
    btn.disabled = true;

    addMsg('user', escHtml(question));
    showTyping();

    try {
      const res = await fetch(API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, debug: false })
      });
      const data = await res.json();
      removeTyping();

      if (!res.ok) {
        addMsg('bot', '<span style="color:#e24b4a">L\u1ed7i: ' + escHtml(data.detail || 'Kh\u00f4ng x\u00e1c \u0111\u1ecbnh') + '</span>');
        return;
      }

      const answerHtml = escHtml(data.answer).replace(/\\n/g, '<br>');
      const sqlId = 'sql-' + Date.now();

      const el = document.createElement('div');
      el.className = 'msg bot';
      el.innerHTML = `
        <div class="avatar bot">N</div>
        <div style="max-width:580px">
          <div class="bubble">
            ${answerHtml}
            ${data.sql ? `
            <div class="sql-block">
              <div class="sql-toggle" onclick="toggleSql('${sqlId}')">
                <span id="${sqlId}-icon">▶</span> Xem c\u00e2u SQL \u0111\u00e3 d\u00f9ng
              </div>
              <div class="sql-code" id="${sqlId}">${escHtml(data.sql)}</div>
            </div>` : ''}
          </div>
          <div class="meta">${data.row_count} d\u00f2ng d\u1eef li\u1ec7u \u00b7 ${data.attempts} l\u1ea7n th\u1eed</div>
        </div>`;
      chat.appendChild(el);
      chat.scrollTop = chat.scrollHeight;

    } catch (e) {
      removeTyping();
      addMsg('bot', '<span style="color:#e24b4a">Kh\u00f4ng k\u1ebft n\u1ed1i \u0111\u01b0\u1ee3c server. H\u00e3y ki\u1ec3m tra uvicorn \u0111ang ch\u1ea1y.</span>');
    }

    btn.disabled = false;
  }

  function sendMsg() {
    const q = input.value.trim();
    if (!q) return;
    input.value = '';
    input.style.height = 'auto';
    ask(q);
  }

  function toggleSql(id) {
    const el = document.getElementById(id);
    const icon = document.getElementById(id + '-icon');
    el.classList.toggle('open');
    icon.textContent = el.classList.contains('open') ? '▼' : '▶';
  }

  function escHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
</script>
</body>
</html>
"""


def render_app() -> HTMLResponse:
    return HTMLResponse(APP_HTML)
