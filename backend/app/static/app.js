const state = {
  users: [],
  sessions: [],
  currentUserId: null,
  currentSessionId: null,
  isStreaming: false,
};

const elements = {
  userSelect: document.getElementById("userSelect"),
  newSessionBtn: document.getElementById("newSessionBtn"),
  interruptBtn: document.getElementById("interruptBtn"),
  themeToggle: document.getElementById("themeToggle"),
  sessionsList: document.getElementById("sessionsList"),
  messagesList: document.getElementById("messagesList"),
  sessionLogsList: document.getElementById("sessionLogsList"),
  promptForm: document.getElementById("promptForm"),
  promptInput: document.getElementById("promptInput"),
  sendBtn: document.getElementById("sendBtn"),
  messageTemplate: document.getElementById("messageTemplate"),
  logTemplate: document.getElementById("logTemplate"),
};

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("theme", theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  applyTheme(current === "dark" ? "light" : "dark");
}

function formatTime(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function messageText(message) {
  if (!message) {
    return "";
  }

  if (message.raw_text) {
    return message.raw_text;
  }

  const payload = message.payload || {};

  if (payload.result && typeof payload.result === "string") {
    return payload.result;
  }

  if (typeof payload.content === "string") {
    return payload.content;
  }

  if (Array.isArray(payload.content)) {
    const texts = payload.content
      .map((item) => {
        if (!item || typeof item !== "object") {
          return "";
        }
        return item.text || item.thinking || "";
      })
      .filter(Boolean);
    if (texts.length > 0) {
      return texts.join("\n");
    }
  }

  if (payload.prompt) {
    return payload.prompt;
  }

  return JSON.stringify(payload, null, 2);
}

function renderSessions() {
  elements.sessionsList.innerHTML = "";
  state.sessions.forEach((session) => {
    const div = document.createElement("div");
    div.className = "session-item";
    if (session.id === state.currentSessionId) {
      div.classList.add("active");
    }

    const title = document.createElement("div");
    title.textContent = session.title;

    const meta = document.createElement("div");
    meta.className = "session-meta";
    meta.textContent = `${session.model} | ${session.permission_mode}`;

    div.appendChild(title);
    div.appendChild(meta);

    div.addEventListener("click", () => selectSession(session.id));
    elements.sessionsList.appendChild(div);
  });
}

function renderMessage(message) {
  const fragment = elements.messageTemplate.content.cloneNode(true);
  const wrapper = fragment.querySelector(".message-item");
  const role = fragment.querySelector(".message-role");
  const time = fragment.querySelector(".message-time");
  const content = fragment.querySelector(".message-content");

  role.textContent = `${message.role} · ${message.message_type}`;
  time.textContent = formatTime(message.created_at);
  content.textContent = messageText(message);

  if (message.role === "result" && message.payload && message.payload.is_error) {
    wrapper.classList.add("is-error");
  }

  elements.messagesList.appendChild(fragment);
  elements.messagesList.scrollTop = elements.messagesList.scrollHeight;
}

function renderMessages(messages) {
  elements.messagesList.innerHTML = "";
  messages.forEach(renderMessage);
}

function renderLogs(logs) {
  elements.sessionLogsList.innerHTML = "";
  logs.forEach((log) => {
    const fragment = elements.logTemplate.content.cloneNode(true);
    fragment.querySelector(".log-type").textContent = log.event_type;
    fragment.querySelector(".log-time").textContent = formatTime(log.created_at);
    fragment.querySelector(".log-content").textContent = JSON.stringify(log.details || {}, null, 2);
    elements.sessionLogsList.appendChild(fragment);
  });
  elements.sessionLogsList.scrollTop = elements.sessionLogsList.scrollHeight;
}

async function loadUsers() {
  state.users = await fetchJSON("/api/users");
  elements.userSelect.innerHTML = "";

  state.users.forEach((user) => {
    const option = document.createElement("option");
    option.value = user.id;
    option.textContent = `${user.display_name} (@${user.username})`;
    elements.userSelect.appendChild(option);
  });

  if (state.users.length === 0) {
    throw new Error("No users found. Seed users were not created.");
  }

  state.currentUserId = state.users[0].id;
  elements.userSelect.value = state.currentUserId;
}

async function loadSessions() {
  if (!state.currentUserId) {
    return;
  }
  state.sessions = await fetchJSON(`/api/users/${state.currentUserId}/sessions`);
  renderSessions();

  if (!state.currentSessionId || !state.sessions.some((item) => item.id === state.currentSessionId)) {
    state.currentSessionId = state.sessions[0] ? state.sessions[0].id : null;
  }

  renderSessions();
  if (state.currentSessionId) {
    await refreshConversation(state.currentSessionId);
  } else {
    renderMessages([]);
    renderLogs([]);
  }
}

async function selectSession(sessionId) {
  state.currentSessionId = sessionId;
  renderSessions();
  await refreshConversation(sessionId);
}

async function refreshConversation(sessionId) {
  const [messages, logs] = await Promise.all([
    fetchJSON(`/api/sessions/${sessionId}/messages`),
    fetchJSON(`/api/sessions/${sessionId}/logs`),
  ]);
  renderMessages(messages);
  renderLogs(logs);
}

async function createSession() {
  if (!state.currentUserId) {
    return;
  }

  const session = await fetchJSON("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ user_id: state.currentUserId, title: "New Session" }),
  });

  state.currentSessionId = session.id;
  await loadSessions();
}

function setStreaming(enabled) {
  state.isStreaming = enabled;
  elements.sendBtn.disabled = enabled;
  elements.promptInput.disabled = enabled;
}

function parseSSEChunk(rawChunk, onEnvelope) {
  const lines = rawChunk.split("\n");
  for (const line of lines) {
    if (!line.startsWith("data: ")) {
      continue;
    }
    const payload = line.slice(6).trim();
    if (!payload) {
      continue;
    }
    onEnvelope(JSON.parse(payload));
  }
}

async function streamPrompt(prompt) {
  const response = await fetch(`/api/sessions/${state.currentSessionId}/messages/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });

  if (!response.ok || !response.body) {
    const errorBody = await response.text();
    throw new Error(`Streaming failed: ${response.status} ${response.statusText} ${errorBody}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";

    for (const block of blocks) {
      parseSSEChunk(block, (envelope) => {
        if (envelope.event === "message") {
          renderMessage(envelope.payload);
        }
        if (envelope.event === "error") {
          const errorPayload = {
            role: "system",
            message_type: "error",
            created_at: envelope.payload.created_at,
            payload: { content: envelope.payload.message },
            raw_text: envelope.payload.message,
          };
          renderMessage(errorPayload);
        }
      });
    }
  }
}

async function handlePromptSubmit(event) {
  event.preventDefault();

  const prompt = elements.promptInput.value.trim();
  if (!prompt || !state.currentSessionId || state.isStreaming) {
    return;
  }

  setStreaming(true);

  try {
    await streamPrompt(prompt);
    await refreshConversation(state.currentSessionId);
  } catch (error) {
    const payload = {
      role: "system",
      message_type: "error",
      created_at: new Date().toISOString(),
      payload: { content: error.message },
      raw_text: error.message,
    };
    renderMessage(payload);
  } finally {
    setStreaming(false);
  }
}

async function interruptCurrentSession() {
  if (!state.currentSessionId) {
    return;
  }
  try {
    await fetchJSON(`/api/sessions/${state.currentSessionId}/interrupt`, { method: "POST" });
    await refreshConversation(state.currentSessionId);
  } catch (error) {
    const payload = {
      role: "system",
      message_type: "interrupt-error",
      created_at: new Date().toISOString(),
      payload: { content: error.message },
      raw_text: error.message,
    };
    renderMessage(payload);
  }
}

function bindEvents() {
  elements.themeToggle.addEventListener("click", toggleTheme);
  elements.newSessionBtn.addEventListener("click", createSession);
  elements.interruptBtn.addEventListener("click", interruptCurrentSession);
  elements.userSelect.addEventListener("change", async (event) => {
    state.currentUserId = event.target.value;
    state.currentSessionId = null;
    await loadSessions();
  });
  elements.promptForm.addEventListener("submit", handlePromptSubmit);
}

async function bootstrap() {
  const savedTheme = localStorage.getItem("theme") || "dark";
  applyTheme(savedTheme);
  bindEvents();

  await loadUsers();
  await loadSessions();

  if (!state.currentSessionId) {
    await createSession();
  }
}

bootstrap().catch((error) => {
  elements.messagesList.innerHTML = "";
  renderMessage({
    role: "system",
    message_type: "bootstrap-error",
    created_at: new Date().toISOString(),
    payload: { content: error.message },
    raw_text: error.message,
  });
});
