const state = {
  users: [],
  sessions: [],
  currentUserId: null,
  currentSessionId: null,
  isStreaming: false,
  timerIntervalId: null,
  timerStartedAt: null,
  askModalQueue: [],
  askModalIsOpen: false,
  shownAskMessageIds: new Set(),
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
  responseTimer: document.getElementById("responseTimer"),
  messageTemplate: document.getElementById("messageTemplate"),
  logTemplate: document.getElementById("logTemplate"),
  askModal: document.getElementById("askModal"),
  askModalBody: document.getElementById("askModalBody"),
  askModalCloseBtn: document.getElementById("askModalCloseBtn"),
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

function formatElapsed(elapsedMs) {
  const totalTenths = Math.floor(elapsedMs / 100);
  const minutes = Math.floor(totalTenths / 600);
  const seconds = Math.floor((totalTenths % 600) / 10);
  const tenths = totalTenths % 10;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${tenths}`;
}

function setTimerLabel(label) {
  elements.responseTimer.textContent = label;
}

function updateTimerLabel() {
  if (!state.timerStartedAt) {
    setTimerLabel("Response: --:--.-");
    return;
  }
  const elapsed = Date.now() - state.timerStartedAt;
  setTimerLabel(`Response: ${formatElapsed(elapsed)}`);
}

function startResponseTimer() {
  stopResponseTimer();
  state.timerStartedAt = Date.now();
  updateTimerLabel();
  state.timerIntervalId = setInterval(updateTimerLabel, 100);
}

function stopResponseTimer() {
  if (state.timerIntervalId) {
    clearInterval(state.timerIntervalId);
    state.timerIntervalId = null;
  }
  if (state.timerStartedAt) {
    updateTimerLabel();
  }
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

function extractAskUserRequests(message) {
  const payload = message && message.payload;
  const content = payload && payload.content;
  if (!Array.isArray(content)) {
    return [];
  }

  return content
    .filter((item) => item && typeof item === "object" && item.name === "AskUserQuestion")
    .map((item) => ({
      toolUseId: item.id || "",
      questions: Array.isArray(item.input && item.input.questions) ? item.input.questions : [],
    }))
    .filter((item) => item.questions.length > 0);
}

function createAskUserOptionButton(option, index, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ask-user-option";
  button.dataset.optionIndex = String(index);

  const label = document.createElement("span");
  label.className = "ask-user-option-label";
  label.textContent = option.label || `Option ${index + 1}`;
  button.appendChild(label);

  if (option.description) {
    const description = document.createElement("span");
    description.className = "ask-user-option-description";
    description.textContent = option.description;
    button.appendChild(description);
  }

  button.addEventListener("click", onClick);
  return button;
}

function questionTitle(question, index) {
  return question.header || `Question ${index + 1}`;
}

function buildAskUserAnswer(questions, selectedOptionIndexes, textAnswers) {
  const parts = [];

  for (let index = 0; index < questions.length; index += 1) {
    const question = questions[index];
    const title = questionTitle(question, index);
    const options = Array.isArray(question.options) ? question.options : [];
    let answer = "";

    if (options.length > 0) {
      const selected = selectedOptionIndexes[index] || [];
      const selectedLabels = selected
        .map((optionIndex) => options[optionIndex])
        .filter(Boolean)
        .map((option) => option.label || "");
      answer = selectedLabels.join(", ").trim();
    } else {
      answer = (textAnswers[index] || "").trim();
    }

    if (!answer) {
      return null;
    }

    parts.push({ title, answer });
  }

  if (parts.length === 1) {
    return parts[0].answer;
  }

  return parts.map((item) => `${item.title}: ${item.answer}`).join("\n");
}

function askMessageKey(message) {
  if (message && message.id) {
    return message.id;
  }
  return `${message?.created_at || ""}|${message?.role || ""}|${message?.message_type || ""}`;
}

function enqueueAskModal(message, requests) {
  if (!Array.isArray(requests) || requests.length === 0) {
    return;
  }

  const key = askMessageKey(message);
  if (state.shownAskMessageIds.has(key)) {
    return;
  }
  state.shownAskMessageIds.add(key);

  state.askModalQueue.push({
    key,
    requests,
  });
  openNextAskModal();
}

function clearAskModal() {
  elements.askModalBody.innerHTML = "";
  elements.askModal.classList.add("is-hidden");
  elements.askModal.setAttribute("aria-hidden", "true");
  state.askModalIsOpen = false;
}

function closeAskModal() {
  clearAskModal();
  openNextAskModal();
}

function resetAskModalState() {
  state.askModalQueue = [];
  if (state.askModalIsOpen) {
    clearAskModal();
  }
}

function openNextAskModal() {
  if (state.askModalIsOpen) {
    return;
  }
  const entry = state.askModalQueue.shift();
  if (!entry) {
    return;
  }

  state.askModalIsOpen = true;
  elements.askModal.classList.remove("is-hidden");
  elements.askModal.setAttribute("aria-hidden", "false");
  elements.askModalBody.innerHTML = "";

  entry.requests.forEach((request, requestIndex) => {
    const requestWrapper = document.createElement("div");
    requestWrapper.className = "ask-modal-request";

    const requestTitle = document.createElement("p");
    requestTitle.className = "ask-modal-request-title";
    requestTitle.textContent = `Request ${requestIndex + 1}`;
    requestWrapper.appendChild(requestTitle);

    requestWrapper.appendChild(
      renderAskUserRequest(request, requestIndex, () => {
        closeAskModal();
      }),
    );
    elements.askModalBody.appendChild(requestWrapper);
  });
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

function renderMessage(message, options = {}) {
  const fragment = elements.messageTemplate.content.cloneNode(true);
  const wrapper = fragment.querySelector(".message-item");
  const role = fragment.querySelector(".message-role");
  const time = fragment.querySelector(".message-time");
  const content = fragment.querySelector(".message-content");

  role.textContent = `${message.role} · ${message.message_type}`;
  time.textContent = formatTime(message.created_at);
  content.textContent = messageText(message);

  const askUserRequests = extractAskUserRequests(message);
  if (askUserRequests.length > 0 && options.showAskModal !== false) {
    enqueueAskModal(message, askUserRequests);
  }

  if (message.role === "result" && message.payload && message.payload.is_error) {
    wrapper.classList.add("is-error");
  }

  elements.messagesList.prepend(fragment);
  elements.messagesList.scrollTop = 0;
}

function renderMessages(messages) {
  elements.messagesList.innerHTML = "";
  messages.forEach((message) => renderMessage(message, { showAskModal: false }));
}

function renderLogs(logs) {
  elements.sessionLogsList.innerHTML = "";
  logs.forEach((log) => {
    const fragment = elements.logTemplate.content.cloneNode(true);
    fragment.querySelector(".log-type").textContent = log.event_type;
    fragment.querySelector(".log-time").textContent = formatTime(log.created_at);
    fragment.querySelector(".log-content").textContent = JSON.stringify(log.details || {}, null, 2);
    elements.sessionLogsList.prepend(fragment);
  });
  elements.sessionLogsList.scrollTop = 0;
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
  resetAskModalState();
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

  resetAskModalState();
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
          if (envelope.payload && envelope.payload.message_type === "ResultMessage") {
            stopResponseTimer();
          }
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
          stopResponseTimer();
        }
      });
    }
  }
}

async function submitPrompt(prompt) {
  startResponseTimer();
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
    throw error;
  } finally {
    stopResponseTimer();
    setStreaming(false);
  }
}

function renderAskUserRequest(request, requestIndex, onSubmitted) {
  const form = document.createElement("div");
  form.className = "ask-user-form";

  const selectedOptionIndexes = {};
  const textAnswers = {};

  request.questions.forEach((question, questionIndex) => {
    const section = document.createElement("div");
    section.className = "ask-user-section";

    const title = document.createElement("div");
    title.className = "ask-user-title";
    title.textContent = questionTitle(question, questionIndex);
    section.appendChild(title);

    const questionText = document.createElement("p");
    questionText.className = "ask-user-question";
    questionText.textContent = question.question || "Please provide your answer.";
    section.appendChild(questionText);

    const options = Array.isArray(question.options) ? question.options : [];
    if (options.length > 0) {
      const optionsContainer = document.createElement("div");
      optionsContainer.className = "ask-user-options";
      const multiSelect = Boolean(question.multiSelect);
      selectedOptionIndexes[questionIndex] = [];

      const refreshSelectionState = () => {
        optionsContainer.querySelectorAll(".ask-user-option").forEach((button, optionIndex) => {
          const selected = selectedOptionIndexes[questionIndex].includes(optionIndex);
          button.classList.toggle("selected", selected);
        });
      };

      options.forEach((option, optionIndex) => {
        const button = createAskUserOptionButton(option, optionIndex, () => {
          const current = selectedOptionIndexes[questionIndex];
          if (multiSelect) {
            if (current.includes(optionIndex)) {
              selectedOptionIndexes[questionIndex] = current.filter((item) => item !== optionIndex);
            } else {
              selectedOptionIndexes[questionIndex] = [...current, optionIndex];
            }
          } else {
            selectedOptionIndexes[questionIndex] = [optionIndex];
          }
          refreshSelectionState();
        });
        optionsContainer.appendChild(button);
      });

      section.appendChild(optionsContainer);
    } else {
      const input = document.createElement("textarea");
      input.rows = 3;
      input.className = "ask-user-input";
      input.placeholder = "Type your answer...";
      input.addEventListener("input", () => {
        textAnswers[questionIndex] = input.value;
      });
      section.appendChild(input);
    }

    form.appendChild(section);
  });

  const actions = document.createElement("div");
  actions.className = "ask-user-actions";

  const submitButton = document.createElement("button");
  submitButton.type = "button";
  submitButton.className = "ask-user-submit";
  submitButton.textContent = "Submit Answers";
  actions.appendChild(submitButton);

  const status = document.createElement("p");
  status.className = "ask-user-status";
  actions.appendChild(status);

  submitButton.addEventListener("click", async () => {
    if (state.isStreaming || !state.currentSessionId) {
      return;
    }

    const answer = buildAskUserAnswer(request.questions, selectedOptionIndexes, textAnswers);
    if (!answer) {
      status.textContent = "Please answer all questions before submitting.";
      status.classList.add("is-error");
      return;
    }

    status.textContent = `Submitting answers for request ${requestIndex + 1}...`;
    status.classList.remove("is-error");
    submitButton.disabled = true;

    try {
      await submitPrompt(answer);
      status.textContent = "Submitted.";
      if (onSubmitted) {
        onSubmitted();
      }
    } catch (error) {
      status.textContent = error.message || "Failed to submit.";
      status.classList.add("is-error");
      submitButton.disabled = false;
    }
  });

  form.appendChild(actions);
  return form;
}

async function handlePromptSubmit(event) {
  event.preventDefault();

  const prompt = elements.promptInput.value.trim();
  if (!prompt || !state.currentSessionId || state.isStreaming) {
    return;
  }

  try {
    await submitPrompt(prompt);
  } catch {
    // Error message is already rendered by submitPrompt.
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
  elements.askModalCloseBtn.addEventListener("click", closeAskModal);
  elements.askModal.addEventListener("click", (event) => {
    if (event.target === elements.askModal) {
      closeAskModal();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.askModalIsOpen) {
      closeAskModal();
    }
  });
  elements.userSelect.addEventListener("change", async (event) => {
    resetAskModalState();
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
  setTimerLabel("Response: --:--.-");

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
