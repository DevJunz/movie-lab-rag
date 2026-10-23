// Movie Lab 웹 화면 (SPEC-F2013). 서버 API만 부르고, 텍스트는 textContent로 넣는다.

const $ = (id) => document.getElementById(id);
const state = { movie: null, ready: true };
const HISTORY_KEY = "movielab.histories";

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function loadHistories() {
  try { return JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "{}"); } catch { return {}; }
}
const histories = loadHistories();
function saveHistories() {
  try { sessionStorage.setItem(HISTORY_KEY, JSON.stringify(histories)); } catch { /* 저장 못 해도 메모리에는 남는다 */ }
}

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.error?.message || "요청을 처리하지 못했습니다.");
  return data;
}

// 인용 근거 목록 — 번호 · 출처 유형 · 제목 · 원문 링크 · 라이선스
function renderEvidence(target, citations, uncited, notices) {
  target.replaceChildren();
  for (const notice of notices || []) target.append(el("div", notice.message, "notice"));
  if (uncited || !citations.length) {
    target.append(el("div", "이 답변에는 인용된 근거가 없습니다.", "notice"));
    return;
  }
  target.append(el("strong", "근거"));
  const list = el("ul");
  for (const c of citations) {
    const li = el("li");
    li.append(el("span", `[근거 ${c.n}] ${c.source_type} · ${c.title}`));
    if (c.url) {
      li.append(" · ");
      const a = el("a", "원문 ↗");
      a.href = c.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      li.append(a);
    }
    if (c.license) li.append(` · ${c.license}`);
    list.append(li);
  }
  target.append(list);
}

function showError(target, message) {
  target.replaceChildren(el("div", message, "error"));
}

// ---- 영화 선택 ----
async function searchMovies(q) {
  const list = $("movie-list");
  try {
    const movies = await api(`/api/movies?q=${encodeURIComponent(q)}`);
    list.replaceChildren();
    for (const m of movies) {
      const button = el("button", `${m.title} (${m.year})`);
      button.type = "button";
      if (state.movie?.movie_id === m.movie_id) button.classList.add("active");
      button.addEventListener("click", () => selectMovie(m));
      const li = el("li");
      li.append(button);
      list.append(li);
    }
  } catch (error) {
    showError(list, error.message);
  }
}

function selectMovie(movie) {
  state.movie = movie;
  $("selected-movie").textContent = `${movie.title} (${movie.year})`;
  $("answer-area").replaceChildren();
  $("evidence-area").replaceChildren();
  renderHistory();
  searchMovies($("movie-search").value);
}

function requireMovie(target) {
  if (!state.movie) { showError(target, "영화를 먼저 선택하세요."); return false; }
  return true;
}

// ---- 질문하기 ----
function renderHistory() {
  const box = $("history");
  box.replaceChildren();
  const messages = state.movie ? histories[state.movie.movie_id] || [] : [];
  for (const m of messages) box.append(el("div", m.text, `msg ${m.role}`));
}

async function ask(question) {
  const progress = $("progress");
  const answer = $("answer-area");
  const evidence = $("evidence-area");
  const movieId = state.movie.movie_id;
  const history = (histories[movieId] ||= []);
  history.push({ role: "user", text: question });
  saveHistories();
  renderHistory();
  answer.replaceChildren();
  evidence.replaceChildren();
  progress.hidden = false;
  progress.textContent = "문서를 확인하고 답변을 준비하는 중…";
  try {
    const res = await fetch("/api/ask/stream", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ movie_id: movieId, question }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.error?.message || "요청을 처리하지 못했습니다.");
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let index;
      while ((index = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, index).trim();
        buffer = buffer.slice(index + 1);
        if (!line) continue;
        const event = JSON.parse(line);
        if (event.type === "stage") {
          progress.textContent = event.message;
        } else if (event.type === "result") {
          const data = event.data;
          answer.textContent = data.answer;
          renderEvidence(evidence, data.citations, data.uncited, data.notices);
          const seconds = data.timings?.total;
          progress.textContent = seconds ? `완료 (${seconds.toFixed(1)}초)` : "완료";
          history.push({ role: "assistant", text: data.answer });
          saveHistories();
        } else if (event.type === "error") {
          throw new Error(event.error.message);
        }
      }
    }
  } catch (error) {
    progress.textContent = "처리하지 못했습니다";
    showError(answer, error.message);
  }
}

// ---- 관람 가이드 · 사실 판정 · 조건 탐색 ----
async function runGuide() {
  const out = $("guide-output");
  if (!requireMovie(out)) return;
  const status = $("guide-status");
  status.hidden = false;
  status.textContent = "문서를 확인하고 답변을 준비하는 중…";
  out.replaceChildren();
  $("guide-evidence").replaceChildren();
  try {
    const data = await api("/api/guide", { movie_id: state.movie.movie_id });
    out.textContent = data.markdown;
    renderEvidence($("guide-evidence"), data.citations, data.uncited, data.notices);
    status.textContent = "완료";
  } catch (error) {
    status.textContent = "처리하지 못했습니다";
    showError(out, error.message);
  }
}

async function runFactcheck(claim) {
  const out = $("factcheck-output");
  if (!requireMovie(out)) return;
  const status = $("factcheck-status");
  status.hidden = false;
  status.textContent = "문서를 확인하고 답변을 준비하는 중…";
  out.replaceChildren();
  $("factcheck-evidence").replaceChildren();
  try {
    const data = await api("/api/factcheck", { movie_id: state.movie.movie_id, claim });
    out.append(el("div", `주장: ${data.claim}`), el("span", data.verdict, "verdict"), el("p", data.reason));
    renderEvidence($("factcheck-evidence"), data.citations, !data.citations.length, data.notices);
    status.textContent = "완료";
  } catch (error) {
    status.textContent = "처리하지 못했습니다";
    showError(out, error.message);
  }
}

async function runExplore(condition) {
  const out = $("explore-output");
  const status = $("explore-status");
  status.hidden = false;
  status.textContent = "조건을 해석하는 중…";
  out.replaceChildren();
  try {
    const data = await api("/api/explore", { condition });
    status.textContent = data.message || `후보 ${data.candidates}건 중 조건에 맞는 ${data.items.length}건`;
    for (const m of data.items) {
      const card = el("div", null, "card");
      card.append(el("strong", `${m.title} (${m.year})`), el("div", m.caption, "muted small"), el("p", `선정 이유: ${m.reason}`));
      card.tabIndex = 0;
      const go = () => { selectMovie(m); showPage("ask"); };
      card.addEventListener("click", go);
      card.addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
      out.append(card);
    }
  } catch (error) {
    status.textContent = "처리하지 못했습니다";
    showError(out, error.message);
  }
}

// ---- 메뉴 · 시작 점검 ----
function showPage(name) {
  for (const button of document.querySelectorAll(".menu button")) {
    button.classList.toggle("active", button.dataset.page === name);
  }
  for (const page of document.querySelectorAll(".page")) page.hidden = page.id !== `page-${name}`;
}

async function checkHealth() {
  const banner = $("banner");
  try {
    const health = await api("/api/health");
    $("index-counts").textContent = `색인: 영화 ${health.index.meta.toLocaleString()}건 / 문서 ${health.index.docs.toLocaleString()}청크`;
    if (!health.api_key_configured) {
      banner.textContent = "GMS API 키가 설정되지 않았습니다. .env 파일에 GMS_API_KEY와 GMS_BASE_URL을 설정한 뒤 서버를 다시 실행하세요.";
      banner.hidden = false;
    } else if (health.index.meta === 0) {
      banner.textContent = "영화 색인이 비어 있습니다. 터미널에서 python -m scripts.index_meta를 실행하세요.";
      banner.hidden = false;
    }
  } catch (error) {
    banner.textContent = error.message;
    banner.hidden = false;
  }
}

function init() {
  for (const button of document.querySelectorAll(".menu button")) {
    button.addEventListener("click", () => showPage(button.dataset.page));
  }
  let timer;
  $("movie-search").addEventListener("input", (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => searchMovies(e.target.value), 200);
  });
  $("ask-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("question-input");
    const question = input.value.trim();
    if (!requireMovie($("answer-area")) || !question) return;
    input.value = "";
    ask(question);
  });
  $("question-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      $("ask-form").requestSubmit();
    }
  });
  $("clear-history").addEventListener("click", () => {
    if (state.movie) delete histories[state.movie.movie_id];
    saveHistories();
    renderHistory();
  });
  $("guide-button").addEventListener("click", runGuide);
  $("factcheck-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const claim = $("claim-input").value.trim();
    if (claim) runFactcheck(claim);
  });
  $("explore-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const condition = $("condition-input").value.trim();
    if (condition) runExplore(condition);
  });
  checkHealth();
  searchMovies("");
}

init();
