// India-China Logistics Digest — swipeable card deck.
// All progress (streak/points/read state/position) lives in localStorage, per device/browser.
// The deck for a given day is built ONCE in a fixed order, so "Back" can always
// re-show an earlier card, and the app can resume at the same position after a reload.

const STATE_KEY = "digest_state_v1";
const POINTS_READ = 10;
const POINTS_SKIP = 2;
const POINTS_QUIZ = 15;
const QUIZ_EVERY = 5; // insert one quiz card after every N article cards

const appEl = document.getElementById("app");
const controlsEl = document.getElementById("controls");
const streakStatEl = document.getElementById("streakStat");
const pointsStatEl = document.getElementById("pointsStat");
const deckProgressEl = document.getElementById("deckProgress");
const backBtn = document.getElementById("backBtn");
const skipBtn = document.getElementById("skipBtn");
const readBtn = document.getElementById("readBtn");
const nextBtn = document.getElementById("nextBtn");
const forwardBtnsEl = document.getElementById("forwardBtns");

function todayKey() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function yesterdayKey() {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function loadState() {
  try {
    const raw = localStorage.getItem(STATE_KEY);
    if (!raw) throw new Error("empty");
    const parsed = JSON.parse(raw);
    if (!parsed.progress) parsed.progress = {};
    if (!parsed.weeklySeen) parsed.weeklySeen = [];
    return parsed;
  } catch {
    return { streak: 0, points: 0, lastCompletedDate: null, progress: {}, weeklySeen: [] };
  }
}

function saveState(state) {
  try {
    localStorage.setItem(STATE_KEY, JSON.stringify(state));
  } catch {
    // localStorage unavailable (private mode etc.) — app still works, just won't remember progress.
  }
}

function getDayProgress(state, dateKey) {
  if (!state.progress[dateKey]) {
    state.progress[dateKey] = { position: 0, resolved: {} };
  }
  return state.progress[dateKey];
}

function renderStats(state) {
  streakStatEl.textContent = `🔥 ${state.streak}`;
  pointsStatEl.textContent = `⭐ ${state.points}`;
}

function shuffled(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function buildQuizCard(allArticles, correctArticle) {
  const distractors = shuffled(allArticles.filter((a) => a.id !== correctArticle.id)).slice(0, 3);
  if (distractors.length < 3) return null;
  const options = shuffled([correctArticle, ...distractors]);
  return {
    kind: "quiz",
    id: `quiz-${correctArticle.id}`,
    category: correctArticle.category,
    question: `Which headline was in today's ${correctArticle.category} news?`,
    options: options.map((o) => ({ id: o.id, text: o.title })),
    correctId: correctArticle.id,
  };
}

// Builds the FULL deck once, in a fixed, deterministic order — independent of what's
// already been resolved — so position indices stay stable across back/forward and reloads.
function buildDeck(data, weekly, weeklyAlreadySeen) {
  const deck = [];
  const articles = data.articles || [];

  if (weekly && weekly.summary && !weeklyAlreadySeen) {
    deck.push({ kind: "weekly", id: `weekly-${weekly.week_ending}`, summary: weekly.summary, week_ending: weekly.week_ending });
  }

  articles.forEach((article, idx) => {
    deck.push({ kind: "article", ...article });
    if ((idx + 1) % QUIZ_EVERY === 0) {
      const quiz = buildQuizCard(articles, article);
      if (quiz) deck.push(quiz);
    }
  });

  return deck;
}

function maybeCompleteDay(state, dateKey) {
  if (state.lastCompletedDate === dateKey) return false;
  state.streak = state.lastCompletedDate === yesterdayKey() ? state.streak + 1 : 1;
  state.lastCompletedDate = dateKey;
  return true;
}

function cardTemplate(card, resolution) {
  if (card.kind === "weekly") {
    return `
      <div class="tag weekly">Weekly Big Picture</div>
      <h2>The bigger picture this week</h2>
      <div class="inference">${escapeHtml(card.summary)}</div>
    `;
  }
  if (card.kind === "quiz") {
    const answered = resolution && resolution.chosenId;
    const optionsHtml = card.options
      .map((o) => {
        const classes = ["quiz-option"];
        if (answered) {
          if (o.id === card.correctId) classes.push("correct");
          else if (o.id === resolution.chosenId) classes.push("wrong");
        }
        return `<button class="${classes.join(" ")}" data-id="${o.id}" ${answered ? "disabled" : ""}>${escapeHtml(o.text)}</button>`;
      })
      .join("");
    return `
      <div class="tag quiz">Quick Quiz</div>
      <h2>${escapeHtml(card.question)}</h2>
      <div class="quiz-options">${optionsHtml}</div>
    `;
  }
  const tagClass = card.category === "Spillover" ? "tag spillover" : "tag";
  return `
    <div class="${tagClass}">${escapeHtml(card.category)}</div>
    <h2>${escapeHtml(card.title)}</h2>
    <div class="inference">${escapeHtml(card.inference || "")}</div>
    <div class="meta">${escapeHtml(card.source || "")}</div>
    ${card.link ? `<a class="source-link" href="${card.link}" target="_blank" rel="noopener">View original source ↗</a>` : ""}
  `;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

function renderDone(state) {
  controlsEl.hidden = true;
  appEl.innerHTML = `
    <div class="done-screen">
      <div class="big-flame">🔥</div>
      <h2>All caught up!</h2>
      <p>Streak: ${state.streak} day${state.streak === 1 ? "" : "s"} · ${state.points} points total</p>
      <p>Come back tomorrow for the next digest.</p>
    </div>
  `;
}

function renderEmpty(message) {
  controlsEl.hidden = true;
  appEl.innerHTML = `<div class="state-message">${escapeHtml(message)}</div>`;
}

async function main() {
  const state = loadState();
  renderStats(state);

  let data;
  try {
    const res = await fetch(`data/latest.json?t=${Date.now()}`);
    if (!res.ok) throw new Error("no data yet");
    data = await res.json();
  } catch {
    renderEmpty("No digest yet. The first one arrives after the daily automation runs (or trigger it manually from GitHub Actions).");
    return;
  }

  let weekly = null;
  try {
    const res = await fetch(`data/weekly-summary.json?t=${Date.now()}`);
    if (res.ok) weekly = await res.json();
  } catch {
    weekly = null;
  }

  const dateKey = data.date || todayKey();
  const dayProgress = getDayProgress(state, dateKey);
  const weeklyAlreadySeen = weekly && (state.weeklySeen || []).includes(weekly.week_ending);
  const deck = buildDeck(data, weekly, weeklyAlreadySeen);

  if (deck.length === 0) {
    renderEmpty("No news items today.");
    return;
  }

  controlsEl.hidden = false;

  function currentCard() {
    return deck[dayProgress.position];
  }

  function render() {
    if (dayProgress.position >= deck.length) {
      if (maybeCompleteDay(state, dateKey)) saveState(state);
      renderStats(state);
      renderDone(state);
      return;
    }

    controlsEl.hidden = false;
    const card = currentCard();
    const resolution = dayProgress.resolved[card.id];
    const total = deck.length;
    deckProgressEl.textContent = `${dayProgress.position + 1} / ${total}`;
    backBtn.disabled = dayProgress.position === 0;

    appEl.innerHTML = `<div class="deck"><div class="card" id="currentCard">${cardTemplate(card, resolution)}</div></div>`;

    const alreadyResolved = card.kind === "weekly" ? weeklyAlreadySeenNow() : Boolean(resolution);
    if (card.kind === "quiz" && !resolution) {
      forwardBtnsEl.hidden = true;
      nextBtn.hidden = true;
      attachQuizHandlers(card);
    } else if (alreadyResolved) {
      forwardBtnsEl.hidden = true;
      nextBtn.hidden = false;
    } else {
      forwardBtnsEl.hidden = false;
      nextBtn.hidden = true;
      if (card.kind === "article") attachSwipeHandlers(card);
    }
  }

  function weeklyAlreadySeenNow() {
    const card = currentCard();
    return card.kind === "weekly" && (state.weeklySeen || []).includes(card.week_ending);
  }

  function advance() {
    dayProgress.position += 1;
    saveState(state);
    render();
  }

  function goBack() {
    if (dayProgress.position === 0) return;
    dayProgress.position -= 1;
    saveState(state);
    render();
  }

  function resolveCurrent(outcome) {
    const card = currentCard();
    if (card.kind === "weekly") {
      state.weeklySeen = state.weeklySeen || [];
      if (!state.weeklySeen.includes(card.week_ending)) state.weeklySeen.push(card.week_ending);
    } else if (!dayProgress.resolved[card.id]) {
      dayProgress.resolved[card.id] = outcome;
      state.points += outcome === "read" ? POINTS_READ : POINTS_SKIP;
    }
    saveState(state);
    renderStats(state);
    advance();
  }

  function attachQuizHandlers(card) {
    const cardEl = document.getElementById("currentCard");
    cardEl.querySelectorAll(".quiz-option").forEach((btn) => {
      btn.addEventListener("click", () => {
        const chosenId = btn.dataset.id;
        const correct = chosenId === card.correctId;
        dayProgress.resolved[card.id] = { chosenId, correct };
        if (correct) state.points += POINTS_QUIZ;
        saveState(state);
        renderStats(state);
        render(); // re-render to show correct/wrong highlight + Next button
      });
    });
  }

  function attachSwipeHandlers() {
    const cardEl = document.getElementById("currentCard");
    let startX = 0, currentX = 0, dragging = false;

    const onStart = (x) => { dragging = true; startX = x; cardEl.classList.add("dragging"); };
    const onMove = (x) => {
      if (!dragging) return;
      currentX = x - startX;
      cardEl.style.transform = `translateX(${currentX}px) rotate(${currentX / 20}deg)`;
    };
    const onEnd = () => {
      if (!dragging) return;
      dragging = false;
      cardEl.classList.remove("dragging");
      if (currentX > 100) { animateOut(1); resolveCurrent("read"); }
      else if (currentX < -100) { animateOut(-1); resolveCurrent("skip"); }
      else { cardEl.style.transform = ""; }
      currentX = 0;
    };

    function animateOut(direction) {
      cardEl.style.transform = `translateX(${direction * 500}px) rotate(${direction * 25}deg)`;
      cardEl.style.opacity = "0";
    }

    cardEl.addEventListener("touchstart", (e) => onStart(e.touches[0].clientX));
    cardEl.addEventListener("touchmove", (e) => onMove(e.touches[0].clientX));
    cardEl.addEventListener("touchend", onEnd);
    cardEl.addEventListener("mousedown", (e) => onStart(e.clientX));
    cardEl.addEventListener("mousemove", (e) => onMove(e.clientX));
    cardEl.addEventListener("mouseup", onEnd);
    cardEl.addEventListener("mouseleave", () => { if (dragging) onEnd(); });
  }

  backBtn.addEventListener("click", goBack);
  skipBtn.addEventListener("click", () => resolveCurrent("skip"));
  readBtn.addEventListener("click", () => resolveCurrent("read"));
  nextBtn.addEventListener("click", advance);

  render();
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  });
}

main();
