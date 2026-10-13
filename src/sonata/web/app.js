"use strict";

const $ = (id) => document.getElementById(id);
const colors = ["#dac18a", "#88bad5", "#ce899b", "#9dc7b0", "#ae9bcc", "#da9b72"];
const state = {
  source: "", name: "program.son", run: null, view: "runtime", notes: [],
  events: [], eventTimeline: [], eventNotes: new Map(), lineEvents: new Map(),
  eventIndex: new Map(), eventTimes: new Map(), noteIndices: new Map(), media: null, performances: [],
  selectedEvent: -1, selectedNote: -1, selectedLine: 1, cursor: 0, total: 0,
  lowPitch: 43, highPitch: 84, longest: 0, breakpoints: new Set(),
  playing: false, speed: 1, zoom: 100, request: 0, busy: false,
  audio: null, master: null, active: new Set(), animation: 0, nextNote: 0,
  anchorBeat: 0, anchorAudio: 0, nextBreak: null, examples: [],
  sideBreakpoints: {left: new Set(), right: new Set()},
  transport: 0, comparison: null, side: "left", settings: null,
  loop: {enabled: false, start: 0, end: 1},
  scoreTokens: [], scoreSelection: -1, scorePage: 0, scoreDirty: false,

};

function format(value, depth = 0) {
  if (value && typeof value === "object") {
    if (!Array.isArray(value) && Object.keys(value).length === 1 && typeof value.$int === "string" && /^-?\d+$/.test(value.$int)) return value.$int;
    const array = Array.isArray(value), entries = array ? value : Object.entries(value);
    if (!entries.length) return array ? "[]" : "{}";
    const indentation = "  ".repeat(depth + 1);
    const body = entries.map((entry) => indentation + (array ? format(entry, depth + 1) : `${JSON.stringify(entry[0])}: ${format(entry[1], depth + 1)}`)).join(",\n");
    return `${array ? "[" : "{"}\n${body}\n${"  ".repeat(depth)}${array ? "]" : "}"}`;
  }
  return JSON.stringify(value) ?? "null";
}
const timeLabel = (beats) => {
  const seconds = Math.max(0, beats / 2);
  return `${Math.floor(seconds / 60)}:${(seconds % 60).toFixed(2).padStart(5, "0")}`;
};
const pitchLabel = (pitch) => ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"][pitch % 12] + (Math.floor(pitch / 12) - 1);
const colorFor = (note) => colors[(Number.isInteger(note.voice) ? note.voice : note.channel || 0) % colors.length];

function status(message, mode = "") {
  $("status").textContent = message;
  $("notice").className = `notice ${mode}`;
}

function showError(message) {
  $("error-banner").textContent = message || "";
  $("error-banner").hidden = !message;
}

async function responseJSON(response) {
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.error === "string" ? body.error : format(body.error || body));
  return body;
}

function lowerBound(items, value, key = "start") {
  let low = 0, high = items.length;
  while (low < high) {
    const middle = (low + high) >>> 1;
    if (items[middle][key] < value) low = middle + 1;
    else high = middle;
  }
  return low;
}

function updateControls() {
  const performance = Boolean(state.run?.performance);
  if (performance) $("workspace").classList.add("performance-mode");
  else $("workspace").classList.remove("performance-mode");
  const accepted = Boolean(state.run && !state.busy && !state.scoreDirty);
  const playable = accepted && Boolean(state.notes.length);
  $("compare").disabled = state.busy || performance;
  $("apply-settings").disabled = state.busy || performance;
  $("score-apply").disabled = state.busy || !state.scoreDirty;
  $("score-reset").disabled = state.busy || !state.scoreDirty;
  for (const id of ["token-replace", "token-insert-before", "token-insert-after", "token-delete"]) $(id).disabled = state.busy || !state.run || state.side === "right" || performance;
  $("audition-a").disabled = $("audition-b").disabled = state.busy || !state.comparison;
  $("event-seek").disabled = !accepted || state.view !== "runtime" || !state.events.length;
  $("event-seek").max = Math.max(0, state.events.length - 1);

  $("run").disabled = state.busy || performance;
  $("palette").disabled = state.busy || performance;
  $("code-view").disabled = performance;
  $("run").textContent = state.busy ? "Loading…" : performance ? "✓  Local performance" : "▶  Run source";
  for (const id of ["fixtures", "mapping", "filter-kinds", "filter-functions", "filter-variables", "range-name", "range-min", "range-max", "source-b", "fixtures-b", "copy-to-b"]) $(id).disabled = state.busy || performance;
  $("listening-options").hidden = performance;
  $("comparison-panel").hidden = performance;
  $("performance-notice").hidden = !performance;
  for (const id of ["play", "replay"]) $(id).disabled = !playable;
  $("step").disabled = !accepted || !(state.view === "runtime" ? state.events.length : state.notes.length);
  for (const id of ["export-wav", "export-midi", "export-code"]) $(id).disabled = !accepted || (performance && id === "export-code");
  $("export-midi").textContent = performance ? "Song MIDI" : "Runtime MIDI";
  $("runtime-view").textContent = performance ? "Song performance" : "Execution";
  $("play-label").textContent = state.playing ? "Pause" : "Play";
  $("play-icon").textContent = state.playing ? "Ⅱ" : "▷";
  $("play").setAttribute("aria-label", state.playing ? "Pause playback" : "Play score");
  $("clear-breakpoints").disabled = !state.breakpoints.size || state.view === "code";
  $("current-time").textContent = timeLabel(state.cursor);
  $("total-time").textContent = timeLabel(state.total);
}

function updateGutter() {
  const count = $("source").value.split("\n").length;
  const fragment = document.createDocumentFragment();
  for (let line = 1; line <= count; line++) {
    const button = document.createElement("button");
    button.textContent = String(line);
    button.dataset.line = String(line);
    button.title = state.view === "code" ? `Inspect canonical line ${line}` : `Toggle breakpoint on line ${line}`;
    button.setAttribute("aria-label", button.title);
    if (state.breakpoints.has(line) && state.view === "runtime") button.classList.add("breakpoint");
    button.setAttribute("aria-pressed", String(state.breakpoints.has(line) && state.view === "runtime"));
    fragment.append(button);
  }
  $("line-numbers").replaceChildren(fragment);
  $("line-numbers").scrollTop = $("source").scrollTop;
  highlightLine(state.selectedLine, false);
}

function highlightLine(line, reveal = false) {
  if (!Number.isInteger(line) || line < 1) return;
  state.selectedLine = line;
  const old = $("line-numbers").querySelector(".active");
  if (old) old.classList.remove("active");
  const active = $("line-numbers").children[line - 1];
  if (active) active.classList.add("active");
  const y = 16 + (line - 1) * 22;
  $("source").style.backgroundImage = `linear-gradient(to bottom,transparent ${y}px,#dac18a12 ${y}px,#dac18a12 ${y + 22}px,transparent ${y + 22}px)`;
  $("cursor-line").textContent = `Line ${line}`;
  if (reveal && (y < $("source").scrollTop || y + 22 > $("source").scrollTop + $("source").clientHeight)) {
    $("source").scrollTop = Math.max(0, y - $("source").clientHeight / 2);
    $("line-numbers").scrollTop = $("source").scrollTop;
  }
  const linked = state.view === "code" ? state.notes.filter((note) => note.line === line).length : (state.lineEvents.get(line) || []).length;
  $("source-link").textContent = state.run ? `Line ${line} · ${linked} ${state.view === "code" ? "code notes" : state.run?.performance ? "scheduled MIDI events" : "execution events"}` : "Run to link source to sound.";
  $("previous-line-event").disabled = linked < 2;
  $("next-line-event").disabled = linked < 2;
}

function updateBreakpoints() {
  const lines = [...state.breakpoints].sort((a, b) => a - b);
  $("breakpoint-summary").textContent = state.view === "code" ? "Breakpoints apply to execution view." : lines.length ? `Pause at ${lines.length === 1 ? "line" : "lines"} ${lines.join(", ")}` : "Click a line number to pause there.";
  updateGutter();
  updateControls();
  if (state.playing) findNextBreakpoint();
}

function stopSound() {
  for (const oscillator of state.active) {
    try { oscillator.stop(); } catch (_) { /* Already stopped by its envelope. */ }
  }
  state.active.clear();
}

function pause(quiet = false) {
  state.transport++;
  if (state.playing && state.media) state.cursor = Math.min(state.total, state.media.currentTime * 2);
  if (state.media) state.media.pause();
  if (state.playing && !state.media && state.audio) state.cursor = Math.min(state.total, state.anchorBeat + (state.audio.currentTime - state.anchorAudio) * 2 * state.speed);
  state.playing = false;
  cancelAnimationFrame(state.animation);
  stopSound();
  updateControls();
  drawTimeline();
  if (!quiet && state.run) status(`Paused at ${timeLabel(state.cursor)}.`);
}

function syncMediaPosition() {
  if (state.media) state.media.currentTime = Math.max(0, Math.min(state.total, state.cursor)) / 2;
}

function clearRun() {
  pause(true);
  if (state.media) {
    state.media.removeAttribute("src");
    state.media.load();
    state.media = null;
  }
  state.request++;
  state.busy = false;
  state.run = null;
  state.comparison = null;
  if (state.side === "right") state.breakpoints = state.sideBreakpoints.left;
  state.side = "left";
  state.scoreDirty = false;
  state.scoreTokens = [];
  $("comparison-results").hidden = true;
  $("comparison-summary").textContent = "A and B share a playback cursor";
  $("token-cells").replaceChildren();
  $("event-accessible").textContent = "Run a program to inspect events.";
  state.notes = [];
  state.events = [];
  state.eventTimeline = [];
  state.eventIndex.clear();
  state.eventTimes.clear();
  state.noteIndices.clear();
  state.eventNotes.clear();
  state.lineEvents.clear();
  state.cursor = 0;
  state.total = 0;
  state.selectedEvent = -1;
  state.selectedNote = -1;
  $("note-count").textContent = "0 notes";
  $("run-stats").textContent = "";
  $("timeline-empty").hidden = false;
  $("program-output").textContent = "Run the source to see its output.";
  $("return-value").textContent = "—";
  resetInspector();
  showError("");
  updateControls();
  sizeTimeline();
}

function resetInspector() {
  $("event-position").textContent = "No event selected";
  $("event-kind").textContent = "Ready";
  $("event-id").textContent = "—";
  $("event-description").textContent = "Select a note or step through the program.";
  $("event-data").textContent = "{}";
  $("variables").textContent = "{}";
  $("variable-count").textContent = "0";
  $("stack-depth").textContent = "0";
  $("stack").replaceChildren();
  $("selected-note").textContent = "Click a note to see its pitch and timing.";
  $("state-marker").classList.remove("active");
}

function commaList(text) {
  const entries = [...new Set(text.split(",").map((value) => value.trim()).filter(Boolean))];
  return entries.length ? entries : null;
}

function requestSettings() {
  const ranges = Object.create(null), name = $("range-name").value.trim();
  if (name) {
    const minimum = Number($("range-min").value), maximum = Number($("range-max").value);
    if (!$("range-min").value.trim() || !$("range-max").value.trim() || !Number.isSafeInteger(minimum) || !Number.isSafeInteger(maximum)) throw new Error("Listening range endpoints must be safe integers (between −9007199254740991 and 9007199254740991).");
    if (minimum >= maximum) throw new Error("The listening range maximum must be greater than its minimum.");
    ranges[name] = [minimum, maximum];
  }
  return {
    palette: $("palette").value,
    inputs_json: $("fixtures").value,
    profile: {version: 1, mapping: $("mapping").value, event_kinds: commaList($("filter-kinds").value), functions: commaList($("filter-functions").value), variables: commaList($("filter-variables").value), ranges, event_stride: 0.25},
  };
}

function activateRun(payload) {
  state.run = payload;
  state.events = payload.result.trace;
  state.eventIndex.clear();
  state.eventTimes.clear();
  state.lineEvents.clear();
  state.eventNotes.clear();
  for (let index = 0; index < state.events.length; index++) {
    const event = state.events[index];
    state.eventIndex.set(event.id, index);
    if (!state.lineEvents.has(event.line)) state.lineEvents.set(event.line, []);
    state.lineEvents.get(event.line).push(index);
  }
  const earliest = new Map();
  for (const note of payload.notes) {
    if (!state.eventNotes.has(note.event_id)) state.eventNotes.set(note.event_id, []);
    state.eventNotes.get(note.event_id).push(note);
    earliest.set(note.event_id, Math.min(earliest.get(note.event_id) ?? Infinity, note.start));
  }
  const stride = state.settings?.profile?.event_stride ?? 0.25;
  state.eventTimeline = state.events.map((event, index) => ({start: payload.performance ? event.start : earliest.get(event.id) ?? index * stride, index})).sort((a, b) => a.start - b.start);
  for (const point of state.eventTimeline) state.eventTimes.set(point.index, point.start);
  $("program-output").textContent = payload.result.output.length ? payload.result.output.map((value) => typeof value === "string" ? value : format(value)).join("\n") : "No printed output.";
  $("return-value").textContent = format(payload.result.return_value);
  $("return-value").title = format(payload.result.return_value);
  $("run-stats").textContent = `${state.comparison ? (state.side === "left" ? "A · " : "B · ") : ""}${state.events.length.toLocaleString()} ${payload.performance ? "scheduled MIDI events" : "events"} · ${payload.result.instructions.toLocaleString()} instructions`;
  const error = payload.result.error;
  showError(error ? `${error.kind} at line ${error.line}: ${error.message}` : "");
  state.scoreTokens = (payload.code_tokens || []).map((token) => typeof token === "string" ? token : token.text);
  state.scoreSelection = -1;
  state.scorePage = 0;
  state.scoreDirty = false;
  configureView();
}

async function loadPerformance(id) {
  clearRun();
  const request = ++state.request;
  state.busy = true;
  updateControls();
  status("Loading the local performance and its source links…", "busy");
  try {
    const payload = await responseJSON(await fetch(`/api/performances/${encodeURIComponent(id)}`));
    if (request !== state.request) return;
    state.busy = false;
    state.view = "runtime";
    state.source = payload.source;
    state.name = payload.name;
    state.breakpoints.clear();
    state.loop.enabled = false;
    $("loop-enabled").checked = false;
    $("examples").value = "";
    $("performances").value = id;
    activateRun(payload);
    $("loop-start").value = "0";
    $("loop-end").value = String(state.total);
    state.media = new Audio(payload.performance.audio_url);
    state.media.preload = "auto";
    const media = state.media;
    media.addEventListener("error", () => {
      if (state.media !== media) return;
      pause(true);
      showError("The local WAV could not load. Rebuild the song audio and reload this performance.");
    });
    media.addEventListener("ended", () => {
      if (state.media !== media) return;
      pause(true);
      if (state.loop.enabled) {
        state.cursor = state.loop.start;
        syncMediaPosition();
        play();
        return;
      }
      state.cursor = state.total;
      updateControls();
      drawTimeline();
      status("Performance complete. Press Play to hear it again.");
    });
    status(`${payload.performance.title} is ready. Play follows the rendered audio; select notes to inspect their source.`);
  } catch (error) {
    if (request !== state.request) return;
    state.busy = false;
    showError(error.message);
    status("This local performance could not load.");
    updateControls();
  }
}

async function runSource(compare = false) {
  if (state.run?.performance) return;
  // Click events are not comparison requests.
  compare = compare === true;
  let settings;
  try { settings = requestSettings(); } catch (error) { showError(error.message); return; }
  const source = state.source, sourceB = $("source-b").value, inputsB = $("fixtures-b").value;
  clearRun();
  const request = ++state.request;
  state.busy = true;
  state.settings = settings;
  updateControls();
  status(compare ? "Executing A and B and comparing their traces…" : "Executing the source and writing its score…", "busy");
  try {
    const body = compare ? {left: {source, inputs_json: settings.inputs_json}, right: {source: sourceB, inputs_json: inputsB}, palette: settings.palette, profile: settings.profile} : {source, ...settings};
    const payload = await responseJSON(await fetch(compare ? "/api/compare" : "/api/run", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)}));
    if (request !== state.request) return;
    state.busy = false;
    if (compare) {
      state.comparison = payload;
      state.sideBreakpoints = {left: state.breakpoints, right: new Set()};
      state.side = "left";
      renderComparison();
      $("comparison-panel").open = true;
    }
    activateRun(compare ? payload.left : payload);
    $("loop-end").value = String(Math.max(0.25, state.total));
    state.loop.enabled = false;
    $("loop-enabled").checked = false;
    status(state.run.result.error ? "Execution stopped with an error. Inspect or play the trace up to that point." : compare ? "Comparison ready. A and B use the same beat; switch sides to audition their differences." : "Score ready. Press Play, step through events, or select a note.");
  } catch (error) {
    if (request !== state.request) return;
    state.busy = false;
    showError(error.message);
    status("The source could not run. Correct the error and run again.");
    updateControls();
  }
}

function firstDivergence() {
  return state.comparison?.comparison?.first_divergence ?? state.comparison?.comparison?.first_event_divergence ?? null;
}

function renderComparison() {
  const comparison = state.comparison;
  if (!comparison) return;
  const divergence = firstDivergence();
  $("comparison-results").hidden = false;
  $("jump-divergence").disabled = divergence === null;
  $("comparison-summary").textContent = divergence === null ? "Equivalent semantic traces" : `First divergence at event ${divergence + 1}`;
  $("comparison-detail").textContent = `A returns ${format(comparison.left.result.return_value)}; B returns ${format(comparison.right.result.return_value)}. ${divergence === null ? "No semantic trace difference." : `Event ${divergence + 1} differs; source positions alone do not count.`}`;
  for (const [side, id] of [["left", "comparison-source-a"], ["right", "comparison-source-b"]]) {
    const source = comparison[side].source;
    const line = divergence === null ? null : comparison[side].result.trace[divergence]?.line;
    const fragment = document.createDocumentFragment();
    for (const [index, text] of source.split("\n").entries()) {
      const span = document.createElement("span");
      span.textContent = `${String(index + 1).padStart(3, " ")}  ${text}\n`;
      if (index + 1 === line) span.className = "divergent-line";
      fragment.append(span);
    }
    $(id).replaceChildren(fragment);
  }
}

function switchSide(side) {
  if (!state.comparison || state.busy || !["left", "right"].includes(side)) return;
  if (state.scoreDirty) { showError("Validate or discard the musical draft before switching sides."); return; }
  const resume = state.playing;
  pause(true);
  const beat = state.cursor;
  state.sideBreakpoints[state.side] = state.breakpoints;
  state.side = side;
  state.breakpoints = state.sideBreakpoints[side];
  activateRun(state.comparison[side]);
  state.cursor = Math.min(beat, state.total);
  if (state.view === "runtime") {
    const point = Math.max(0, lowerBound(state.eventTimeline, state.cursor + 0.000001) - 1);
    if (state.eventTimeline[point]) selectEvent(state.eventTimeline[point].index);
  }
  revealCursor();
  drawTimeline();
  updateControls();
  status(`Listening to ${side === "left" ? "A" : "B"} at the shared beat ${state.cursor.toFixed(2)}.`);
  if (resume) play();
}

function jumpDivergence() {
  const divergence = firstDivergence();
  if (divergence === null) return;
  if (state.scoreDirty) { showError("Validate or discard the musical draft before inspecting the divergence."); return; }
  state.view = "runtime";
  configureView();
  seekEvent(Math.min(divergence, state.events.length - 1));
  const beat = divergence * (state.settings?.profile?.event_stride ?? 0.25);
  state.cursor = Math.min(state.total, beat);
  $("loop-start").value = String(Math.max(0, beat - 0.5));
  $("loop-end").value = String(Math.min(state.total, beat + 1.25));
  readLoop();
  revealCursor();
  updateControls();
  drawTimeline();
  status(`First divergence at event ${divergence + 1}. Enable Loop region to compare this phrase repeatedly.`);
}

function readLoop() {
  const start = Number($("loop-start").value), end = Number($("loop-end").value);
  if (!$("loop-start").value.trim() || !$("loop-end").value.trim() || !Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start) throw new Error("The loop end must come after its nonnegative start beat.");
  if ($("loop-enabled").checked && (end > state.total + 0.000001 || start >= state.total)) throw new Error("The loop region must fit within the current score.");
  state.loop = {enabled: $("loop-enabled").checked, start, end};
  drawTimeline();
}

function renderTokens() {
  $("score-editor").hidden = state.view !== "code";
  const pageSize = 48, pages = Math.max(1, Math.ceil(state.scoreTokens.length / pageSize));
  state.scorePage = Math.max(0, Math.min(pages - 1, state.scorePage));
  const fragment = document.createDocumentFragment();
  for (let index = state.scorePage * pageSize; index < Math.min(state.scoreTokens.length, (state.scorePage + 1) * pageSize); index++) {
    const token = state.scoreTokens[index], button = document.createElement("button");
    const notes = state.scoreDirty ? [] : (state.run?.code_notes || []).filter((note) => note.token_index === index);
    button.dataset.tokenIndex = String(index);
    button.setAttribute("aria-pressed", String(state.scoreSelection === index));
    button.setAttribute("aria-label", `Token ${index + 1}: ${token}. ${state.scoreDirty ? "Unvalidated draft" : `${notes.length} encoded notes`}`);
    if (state.scoreDirty) button.className = "draft-cell";
    const label = document.createElement("span"), pitches = document.createElement("span");
    label.className = "token-label"; label.textContent = token;
    pitches.className = "token-pitches"; pitches.setAttribute("aria-hidden", "true");
    for (const note of notes.slice(0, 18)) {
      const mark = document.createElement("i");
      mark.style.height = `${3 + (note.pitch / 127) * 17}px`;
      pitches.append(mark);
    }
    button.append(pitches, label);
    fragment.append(button);
  }
  $("token-cells").replaceChildren(fragment);
  $("token-page-label").textContent = `Page ${state.scorePage + 1} / ${pages} · ${state.scoreTokens.length} tokens`;
  $("token-page-back").disabled = state.scorePage === 0;
  $("token-page-next").disabled = state.scorePage >= pages - 1;
  $("score-draft-status").textContent = state.scoreDirty ? "Draft changed. Validate to hear or export it." : "Validated score. Framing and checksum update automatically.";
  $("token-position").textContent = state.scoreSelection >= 0 ? `Token ${state.scoreSelection + 1} of ${state.scoreTokens.length}` : "Select a musical cell";
}

function chooseToken(index) {
  if (index < 0 || index >= state.scoreTokens.length) return;
  state.scoreSelection = index;
  state.scorePage = Math.floor(index / 48);
  $("token-text").value = state.scoreTokens[index];
  if (!state.scoreDirty) {
    const note = state.notes.findIndex((note) => note.token_index === index);
    if (note >= 0) selectNote(note);
  }
  renderTokens();
}

function editToken(action) {
  if (state.run?.performance) return;
  if (state.side === "right" || state.busy) return;
  const text = $("token-text").value.trim();
  if (action !== "delete" && (!text || /\s/.test(text))) { showError("Enter a single token, such as let, total, 5, <=, or ;."); return; }
  let index = state.scoreSelection;
  if (index < 0 && state.scoreTokens.length) { showError("Select a musical cell first."); return; }
  pause(true);
  if (action === "delete") {
    if (index < 0) return;
    state.scoreTokens.splice(index, 1);
    index = Math.min(index, state.scoreTokens.length - 1);
  } else if (action === "replace" && index >= 0) state.scoreTokens[index] = text;
  else {
    index = Math.max(0, index + (action === "after" ? 1 : 0));
    state.scoreTokens.splice(index, 0, text);
  }
  state.scoreSelection = index;
  state.scorePage = Math.max(0, Math.floor(index / 48));
  state.scoreDirty = true;
  showError("");
  renderTokens();
  updateControls();
}

async function applyScore() {
  if (!state.scoreDirty || state.busy) return;
  let settings;
  try { settings = requestSettings(); } catch (error) { showError(error.message); return; }
  const request = ++state.request, tokens = [...state.scoreTokens];
  state.busy = true;
  updateControls();
  status("Validating musical cells and rebuilding their executable score…", "busy");
  try {
    const payload = await responseJSON(await fetch("/api/score", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({tokens, ...settings})}));
    if (request !== state.request) return;
    state.busy = false;
    state.source = payload.source;
    state.breakpoints.clear();
    state.settings = settings;
    state.comparison = null;
    state.side = "left";
    $("comparison-results").hidden = true;
    activateRun(payload);
    showError(payload.result.error ? `${payload.result.error.kind}: ${payload.result.error.message}` : "");
    status("Musical score accepted. The source and actual encoded pitches now match your cells.");
  } catch (error) {
    if (request !== state.request) return;
    state.busy = false;
    showError(error.message);
    status("The draft is not a valid program yet. Repair its cells or discard the edits.");
    updateControls();
  }
}

function configureView() {
  pause(true);
  const performance = state.run?.performance;
  if (performance) state.view = "runtime";
  const code = state.view === "code";
  $("runtime-view").setAttribute("aria-pressed", String(!code));
  $("code-view").setAttribute("aria-pressed", String(code));
  $("source").readOnly = code || state.side === "right" || Boolean(performance);
  $("source").value = code ? (state.run?.code_source || "Run the source to view its canonical code.") : state.side === "right" ? state.run?.source || "" : state.source;
  $("filename").textContent = code ? "Canonical source for executable score" : state.side === "right" ? "Program B · comparison" : state.name;
  $("source-state").textContent = performance ? "Performance source · read only" : code ? (state.side === "right" ? "Score B · edit Program B in the comparison panel" : "Edit its musical cells below") : state.side === "right" ? "Program B · change it in Compare two executions" : "Editable program A";
  $("score-caption").textContent = performance ? "The supplied arrangement, performed by SONATA" : code ? "The program encoded as playable notes" : "The sound of this execution";
  $("view-explanation").textContent = performance ? "Scheduled MIDI events link to the source catalog and emitted fixture page." : code ? "Executable MIDI contains the program itself. This view uses canonical source." : "Each sound links to a step in your program.";
  $("state-title").textContent = performance ? "Performance event" : code ? "Inside the score" : "At this moment";
  $("state-title").nextElementSibling.textContent = performance ? "Source provenance for the scheduled MIDI message" : code ? "Static token and note information" : "State after the selected event";
  state.notes = [...(code ? state.run?.code_notes || [] : state.run?.notes || [])].sort((a, b) => a.start - b.start || a.id - b.id);
  state.noteIndices.clear();
  for (let index = 0; index < state.notes.length; index++) if (!state.noteIndices.has(state.notes[index].event_id)) state.noteIndices.set(state.notes[index].event_id, index);
  state.cursor = 0;
  state.selectedEvent = -1;
  state.selectedNote = -1;
  state.selectedLine = 1;
  state.total = 0;
  state.longest = 0;
  let low = 127, high = 0;
  for (const note of state.notes) {
    state.total = Math.max(state.total, note.start + note.duration);
    state.longest = Math.max(state.longest, note.duration);
    low = Math.min(low, note.pitch);
    high = Math.max(high, note.pitch);
  }
  if (!performance && state.view === "runtime" && state.events.length) state.total = Math.max(state.total, state.events.length * (state.settings?.profile?.event_stride ?? 0.25));
  if (state.comparison && state.view === "runtime") {
    for (const side of ["left", "right"]) {
      const run = state.comparison[side];
      state.total = Math.max(state.total, run.result.trace.length * (state.settings?.profile?.event_stride ?? 0.25));
      for (const note of run.notes) state.total = Math.max(state.total, note.start + note.duration);
    }
  }
  if (performance) state.total = performance.duration_seconds * 2;
  else if (state.notes.length) state.total += 0.4;
  $("timeline-clock-label").textContent = performance ? "Real time · 1 grid beat = 0.5 seconds" : "120 BPM / time in beats";
  state.lowPitch = state.notes.length ? Math.max(0, Math.min(low - 3, high - 19)) : 43;
  state.highPitch = state.notes.length ? Math.min(127, Math.max(high + 3, low + 19)) : 84;
  $("note-count").textContent = `${state.notes.length.toLocaleString()} notes`;
  $("timeline-empty").hidden = Boolean(state.notes.length);
  $("timeline-empty").querySelector("p").textContent = state.events.length && !code ? "No audible events match these filters." : "Your execution will appear here.";
  $("timeline-empty").querySelector("span:last-child").textContent = state.events.length && !code ? "Step through the trace, or change the listening settings." : "Run the source, then press Play.";
  if (state.loop.enabled && state.loop.end > state.total) { state.loop.enabled = false; $("loop-enabled").checked = false; }
  $("timeline-scroll").scrollLeft = 0;
  $("audition-a").setAttribute("aria-pressed", String(state.side === "left"));
  $("audition-b").setAttribute("aria-pressed", String(state.side === "right"));
  renderTokens();
  const legend = document.createDocumentFragment();
  const voices = [...new Set(state.notes.map((note) => code ? note.channel : note.voice))].slice(0, 6);
  for (const voice of voices) {
    const item = document.createElement("span"), swatch = document.createElement("i");
    swatch.className = "voice-swatch";
    swatch.style.background = colors[(Number(voice) || 0) % colors.length];
    item.append(swatch, document.createTextNode((code || performance) ? (Number(voice) === 9 ? "Drums · channel 10" : `Channel ${Number(voice) + 1}`) : voice === 0 ? "Main voice" : `Depth voice ${voice}`));
    legend.append(item);
  }
  $("voice-legend").replaceChildren(legend);
  resetInspector();
  updateBreakpoints();
  sizeTimeline();
  if (state.view === "runtime" && state.events.length) {
    selectEvent(0, false);
    state.selectedNote = (state.noteIndices.get(state.events[0].id) ?? -1);
  } else if (state.notes.length) selectNote(0, false);
  updateControls();
}

function inspectSound(note) {
  const heading = document.createElement("strong");
  heading.textContent = pitchLabel(note.pitch);
  const details = document.createElement("div");
  details.textContent = `MIDI ${note.pitch} · velocity ${note.velocity} · channel ${note.channel + 1}`;
  const timing = document.createElement("div");
  timing.textContent = state.run?.performance ? `${timeLabel(note.start)} · ${(note.duration / 2).toFixed(3)} seconds long` : `Beat ${note.start.toFixed(3)} · ${note.duration.toFixed(3)} beats long`;
  $("selected-note").replaceChildren(heading, details, timing);
}

function selectEvent(index, reveal = true) {
  const event = state.events[index];
  if (!event) return;
  state.selectedEvent = index;
  $("event-seek").value = String(index);
  $("event-accessible").textContent = `Event ${index + 1} of ${state.events.length}: ${event.kind}, ${event.function || "main"}, line ${event.line}. ${state.eventNotes.has(event.id) ? "Note onset" : state.run?.performance ? "MIDI control, metadata, or note release" : "Muted by listening filters"}.`;
  $("event-position").textContent = `Event ${index + 1} of ${state.events.length} · line ${event.line}`;
  $("event-kind").textContent = event.kind;
  $("event-id").textContent = `#${event.id}`;
  $("event-description").textContent = state.run?.performance ? `${event.kind} at ${timeLabel(event.start)} · catalog line ${event.line} · emission line ${event.data?.emission_line ?? "—"}` : `${event.kind} in ${event.function || "main"} · line ${event.line}, column ${event.col}`;
  $("event-data").textContent = format(event.data || {});
  $("variables").textContent = format(event.variables || {});
  $("variable-count").textContent = String(Object.keys(event.variables || {}).length);
  const stack = event.stack || [];
  $("stack-depth").textContent = String(stack.length);
  const fragment = document.createDocumentFragment();
  for (const name of stack) {
    const item = document.createElement("li");
    item.textContent = String(name);
    fragment.append(item);
  }
  if (!stack.length) {
    const item = document.createElement("li");
    item.className = "muted";
    item.textContent = "Top level";
    fragment.append(item);
  }
  $("stack").replaceChildren(fragment);
  $("state-marker").classList.add("active");
  highlightLine(event.line, reveal);
  const note = (state.eventNotes.get(event.id) || [])[0];
  if (note) inspectSound(note);
  else $("selected-note").textContent = state.run?.performance ? "This MIDI event changes performance state or releases a note." : "This event is muted by the listening filters.";
}

function selectNote(index, seek = true) {
  const note = state.notes[index];
  if (!note) return;
  state.selectedNote = index;
  if (seek) {
    pause(true);
    state.cursor = note.start;
    syncMediaPosition();
  }
  if (state.view === "runtime") {
    const eventIndex = state.eventIndex.get(note.event_id) ?? -1;
    selectEvent(eventIndex);
  } else {
    $("event-position").textContent = `Code note ${index + 1} of ${state.notes.length}`;
    $("event-kind").textContent = note.token || "Framing";
    $("event-id").textContent = `#${note.id}`;
    $("event-description").textContent = note.token ? `Token ${note.token} at canonical line ${note.line}` : "Score framing or checksum";
    $("event-data").textContent = format({token: note.token || null, line: note.line, channel: note.channel});
    if (note.line > 0) highlightLine(note.line, true);
  }
  inspectSound(note);
  revealCursor();
  updateControls();
  drawTimeline();
}

function inspectSourceLine(line) {
  pause(true);
  if (state.view === "code") {
    const index = state.notes.findIndex((note) => note.line === line);
    if (index >= 0) selectNote(index);
  } else {
    const index = (state.lineEvents.get(line) || [])[0];
    if (index !== undefined) {
      selectEvent(index, false);
      const event = state.events[index];
      state.cursor = (state.eventNotes.get(event.id) || [])[0]?.start ?? state.eventTimes.get(index) ?? 0;
      state.selectedNote = state.noteIndices.get(event.id) ?? -1;
      syncMediaPosition();
      revealCursor();
    }
  }
  highlightLine(line, false);
  updateControls();
  drawTimeline();
}

function navigateLine(direction) {
  const line = state.selectedLine;
  if (state.view === "code") {
    const linked = state.notes.map((note, index) => ({note, index})).filter(({note}) => note.line === line).map(({index}) => index);
    const current = linked.indexOf(state.selectedNote);
    if (linked.length) selectNote(linked[(current + direction + linked.length) % linked.length]);
  } else {
    const linked = state.lineEvents.get(line) || [];
    const current = linked.indexOf(state.selectedEvent);
    if (linked.length) seekEvent(linked[(current + direction + linked.length) % linked.length]);
  }
}

async function ensureAudio() {
  if (!state.audio) {
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) throw new Error("This browser cannot play Web Audio. Download the WAV to listen.");
    state.audio = new Audio();
    const compressor = state.audio.createDynamicsCompressor();
    compressor.threshold.value = -18;
    compressor.knee.value = 18;
    compressor.ratio.value = 5;
    compressor.connect(state.audio.destination);
    state.master = state.audio.createGain();
    state.master.gain.value = 0.65;
    state.master.connect(compressor);
  }
  await state.audio.resume();
}

function soundNote(note, when, duration) {
  if (state.active.size >= 512) throw new Error("Playback exceeded 512 simultaneous voices. Export WAV or shorten this program to audition it.");
  const oscillator = state.audio.createOscillator(), gain = state.audio.createGain();
  const palette = $("palette").value;
  oscillator.type = palette === "electronic" ? "sawtooth" : palette === "ambient" ? "sine" : "triangle";
  oscillator.frequency.value = 440 * 2 ** ((note.pitch - 69) / 12);
  const attack = Math.min(duration / 3, palette === "ambient" ? 0.04 : 0.006);
  const release = 0.12 / state.speed;
  gain.gain.setValueAtTime(0, when);
  gain.gain.linearRampToValueAtTime(note.velocity / 127 * 0.19, when + attack);
  gain.gain.setValueAtTime(note.velocity / 127 * 0.15, when + Math.max(attack, duration));
  gain.gain.exponentialRampToValueAtTime(0.0001, when + duration + release);
  oscillator.connect(gain);
  gain.connect(state.master);
  state.active.add(oscillator);
  oscillator.onended = () => {
    state.active.delete(oscillator);
    oscillator.disconnect();
    gain.disconnect();
  };
  oscillator.start(when);
  oscillator.stop(when + duration + release + 0.01);
}

function seekEvent(index) {
  pause(true);
  const event = state.events[index];
  if (!event) return;
  const notes = state.eventNotes.get(event.id) || [];
  state.cursor = notes[0]?.start ?? state.eventTimes.get(index) ?? 0;
  state.selectedNote = state.noteIndices.get(event.id) ?? -1;
  selectEvent(index);
  syncMediaPosition();
  revealCursor();
  updateControls();
  drawTimeline();
}

async function step(direction = 1) {
  if (!state.run || state.scoreDirty || (state.view === "code" ? !state.notes.length : !state.events.length)) return;
  pause(true);
  let notes;
  if (state.view === "code") {
    const index = Math.max(0, Math.min(state.notes.length - 1, state.selectedNote + direction));
    selectNote(index);
    notes = [state.notes[index]];
  } else {
    const index = Math.max(0, Math.min(state.events.length - 1, state.selectedEvent + direction));
    seekEvent(index);
    notes = state.eventNotes.get(state.events[index].id) || [];
  }
  if (state.media) { status(`Stepped to scheduled MIDI event ${state.selectedEvent + 1}. Press Play to hear from here.`); return; }
  const request = state.request;
  const transport = state.transport;
  try {
    await ensureAudio();
    if (request !== state.request || transport !== state.transport) return;
    for (const note of notes) soundNote(note, state.audio.currentTime + 0.012 + (note.start - state.cursor) / (2 * state.speed), note.duration / (2 * state.speed));
    status(state.view === "code" ? "Auditioning the selected code note." : `Stepped to event ${state.selectedEvent + 1}.`);
  } catch (error) {
    stopSound();
    showError(error.message);
  }
}

function findNextBreakpoint() {
  state.nextBreak = null;
  if (state.view !== "runtime") return;
  for (const point of state.eventTimeline) {
    if (point.start > state.cursor + 0.00001 && state.breakpoints.has(state.events[point.index].line)) {
      state.nextBreak = point;
      return;
    }
  }
}

async function play() {
  if (state.playing) { pause(); return; }
  if (!state.run || !state.notes.length || state.scoreDirty) return;
  const request = state.request;
  const transport = ++state.transport;
  try {
    if (!state.media) await ensureAudio();
    if (request !== state.request || transport !== state.transport) return;
    stopSound();
    readLoop();
    if (state.loop.enabled && (state.cursor < state.loop.start || state.cursor >= state.loop.end)) state.cursor = state.loop.start;
    else if (state.cursor >= state.total - 0.01) state.cursor = 0;
    if (state.media) {
      const media = state.media;
      syncMediaPosition();
      media.playbackRate = state.speed;
      media.preservesPitch = true;
      await media.play();
      if (request !== state.request || transport !== state.transport) {
        if (state.media !== media) media.pause();
        return;
      }
      state.playing = true;
      findNextBreakpoint();
      updateControls();
      status("Playing the local arrangement. The source and notes follow its audio clock.", "playing");
      animate();
      return;
    }
    state.anchorBeat = state.cursor;
    state.anchorAudio = state.audio.currentTime + 0.02;
    state.nextNote = lowerBound(state.notes, state.cursor - 0.000001);
    const sustained = lowerBound(state.notes, Math.max(0, state.cursor - state.longest));
    for (let index = sustained; index < state.nextNote; index++) {
      const note = state.notes[index];
      if (note.start < state.cursor && note.start + note.duration > state.cursor) {
        soundNote(note, state.anchorAudio, (note.start + note.duration - state.cursor) / (2 * state.speed));
      }
    }
    state.playing = true;
    findNextBreakpoint();
    updateControls();
    status(state.view === "code" ? "Playing the executable score." : "Playing execution. Source and state follow the sound.", "playing");
    animate();
  } catch (error) {
    if (request !== state.request || transport !== state.transport) return;
    pause(true);
    showError(error.message);
  }
}

function animate() {
  if (!state.playing) return;
  try {
    state.cursor = state.media ? state.media.currentTime * 2 : Math.max(state.anchorBeat, state.anchorBeat + (state.audio.currentTime - state.anchorAudio) * 2 * state.speed);
    if (state.nextBreak && state.cursor >= state.nextBreak.start) {
      const breakpoint = state.nextBreak;
      pause(true);
      state.cursor = breakpoint.start;
      syncMediaPosition();
      selectEvent(breakpoint.index);
      state.selectedNote = lowerBound(state.notes, state.cursor);
      revealCursor();
      updateControls();
      drawTimeline();
      status(`Paused at breakpoint on line ${state.events[breakpoint.index].line}. Press Play to continue.`);
      return;
    }
    if (state.loop.enabled && state.cursor >= state.loop.end) {
      pause(true);
      state.cursor = state.loop.start;
      syncMediaPosition();
      play();
      return;
    }
    if (state.cursor >= state.total) {
      pause(true);
      state.cursor = state.total;
      updateControls();
      drawTimeline();
      status("Performance complete. Press Play to hear it again.");
      return;
    }
    const horizon = Math.min(state.cursor + 0.22 * state.speed, state.nextBreak?.start ?? Infinity, state.loop.enabled ? state.loop.end : Infinity);
    while (!state.media && state.nextNote < state.notes.length && state.notes[state.nextNote].start < horizon) {
      const note = state.notes[state.nextNote++];
      const when = Math.max(state.audio.currentTime, state.anchorAudio + (note.start - state.anchorBeat) / (2 * state.speed));
      soundNote(note, when, note.duration / (2 * state.speed));
    }
    if (state.view === "runtime") {
      let point = lowerBound(state.eventTimeline, state.cursor + 0.000001) - 1;
      if (point >= 0 && state.selectedEvent !== state.eventTimeline[point].index) {
        selectEvent(state.eventTimeline[point].index);
        state.selectedNote = Math.max(0, lowerBound(state.notes, state.eventTimeline[point].start));
      }
    } else {
      const index = Math.max(0, lowerBound(state.notes, state.cursor + 0.000001) - 1);
      if (index !== state.selectedNote) selectNote(index, false);
    }
    $("current-time").textContent = timeLabel(state.cursor);
    revealCursor();
    drawTimeline();
    state.animation = requestAnimationFrame(animate);
  } catch (error) {
    pause(true);
    showError(error.message);
  }
}

function sizeTimeline() {
  const canvas = $("timeline"), width = $("timeline-scroll").clientWidth;
  const height = $("timeline-content").clientHeight;
  const ratio = window.devicePixelRatio || 1;
  canvas.style.width = `${width}px`;
  canvas.width = Math.round(width * ratio);
  canvas.height = Math.round(height * ratio);
  $("timeline-content").style.width = `${Math.max(width, state.total * state.zoom + 90)}px`;
  drawTimeline();
}

function revealCursor() {
  const scroll = $("timeline-scroll"), x = state.cursor * state.zoom;
  const visible = scroll.clientWidth - 60;
  if (x < scroll.scrollLeft || x > scroll.scrollLeft + visible - 30) scroll.scrollLeft = Math.max(0, x - visible * 0.25);
}

function drawTimeline() {
  const canvas = $("timeline"), context = canvas.getContext("2d");
  const width = canvas.clientWidth, height = canvas.clientHeight;
  if (!width || !height) return;
  const ratio = window.devicePixelRatio || 1;
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, width, height);
  const left = 42, top = 28, bottom = 13, offset = $("timeline-scroll").scrollLeft;
  const row = (height - top - bottom) / (state.highPitch - state.lowPitch + 1);
  context.fillStyle = "#151a23";
  context.fillRect(0, 0, width, height);
  context.font = "10px 'DejaVu Sans Mono',monospace";
  for (let pitch = state.lowPitch; pitch <= state.highPitch; pitch++) {
    const y = top + (state.highPitch - pitch) * row;
    if ([1, 3, 6, 8, 10].includes(pitch % 12)) {
      context.fillStyle = "#1b202a";
      context.fillRect(left, y, width - left, row);
    }
    if (pitch % 12 === 0) {
      context.strokeStyle = "#343b48";
      context.beginPath(); context.moveTo(left, y + row); context.lineTo(width, y + row); context.stroke();
      context.fillStyle = "#8f99a4";
      context.fillText(pitchLabel(pitch), 9, y + row / 2 + 3);
    }
  }
  const grid = state.zoom < 65 ? 2 : 1;
  const firstBeat = Math.floor(offset / state.zoom / grid) * grid;
  const lastBeat = (offset + width) / state.zoom;
  for (let beat = firstBeat; beat <= lastBeat; beat += grid) {
    const x = left + beat * state.zoom - offset;
    if (x < left) continue;
    context.strokeStyle = beat % 4 === 0 ? "#434753" : "#2b323e";
    context.beginPath(); context.moveTo(x, top); context.lineTo(x, height - bottom); context.stroke();
    context.fillStyle = beat % 4 === 0 ? "#bbb9ae" : "#6f7a89";
    context.fillText(String(beat), x + 4, 17);
  }
  context.save();
  context.beginPath(); context.rect(left, top, width - left, height - top); context.clip();
  const earliest = Math.max(0, offset / state.zoom - state.longest);
  const first = lowerBound(state.notes, earliest);
  const latest = (offset + width - left) / state.zoom;
  for (let index = first; index < state.notes.length; index++) {
    const note = state.notes[index];
    if (note.start > latest) break;
    const x = left + note.start * state.zoom - offset;
    const y = top + (state.highPitch - note.pitch) * row + 1;
    const noteWidth = Math.max(2, note.duration * state.zoom - 1);
    if (x + noteWidth < left) continue;
    const selected = state.run?.performance && state.playing ? note.start <= state.cursor && note.start + note.duration > state.cursor : state.view === "runtime" ? state.events[state.selectedEvent]?.id === note.event_id : index === state.selectedNote;
    context.fillStyle = colorFor(note);
    context.globalAlpha = selected ? 1 : 0.72;
    context.fillRect(x, y, noteWidth, Math.max(2, row - 2));
    context.globalAlpha = 1;
    if (selected) {
      context.strokeStyle = "#f8f3e2";
      context.lineWidth = 1;
      context.strokeRect(x + 0.5, y + 0.5, Math.max(1, noteWidth - 1), Math.max(1, row - 3));
    }
  }
  if (state.loop.enabled) {
    context.fillStyle = "#88bad516";
    context.fillRect(left + state.loop.start * state.zoom - offset, top, (state.loop.end - state.loop.start) * state.zoom, height - top);
  }
  const divergence = state.view === "runtime" ? firstDivergence() : null;
  if (divergence !== null) {
    const x = left + divergence * (state.settings?.profile?.event_stride ?? 0.25) * state.zoom - offset;
    context.strokeStyle = "#ef9cb5";
    context.lineWidth = 2;
    context.beginPath(); context.moveTo(x, top); context.lineTo(x, height - bottom); context.stroke();
  }
  const cursor = left + state.cursor * state.zoom - offset;
  context.strokeStyle = "#eee5c8";
  context.lineWidth = 1;
  context.beginPath(); context.moveTo(cursor, top); context.lineTo(cursor, height - bottom); context.stroke();
  context.restore();
  context.fillStyle = "#dac18a";
  context.beginPath(); context.moveTo(cursor - 4, 21); context.lineTo(cursor + 4, 21); context.lineTo(cursor, 27); context.fill();
}

async function download(kind, button) {
  if (!state.run) return;
  if (state.run.performance) {
    if (kind === "code-midi") return;
    const link = document.createElement("a");
    link.href = kind === "wav" ? state.run.performance.audio_url : state.run.performance.midi_url;
    link.download = `${state.run.performance.id}.${kind === "wav" ? "wav" : "mid"}`;
    document.body.append(link);
    link.click();
    link.remove();
    status("Downloading the local performance.");
    return;
  }
  const request = state.request;
  const source = state.run.source;
  const settings = {...state.settings, inputs_json: state.side === "right" ? $("fixtures-b").value : state.settings.inputs_json};
  button.disabled = true;
  status(`Preparing ${kind === "wav" ? "WAV audio" : kind === "code-midi" ? "executable MIDI" : "runtime MIDI"}…`, "busy");
  try {
    const response = await fetch(`/api/export/${kind}`, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({source, ...settings}),
    });
    if (!response.ok) { await responseJSON(response); return; }
    const blob = await response.blob();
    if (request !== state.request) return;
    const url = URL.createObjectURL(blob), link = document.createElement("a");
    link.href = url;
    link.download = `sonata-${kind}.${kind === "wav" ? "wav" : "mid"}`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    status("Download ready.");
  } catch (error) {
    if (request === state.request) { showError(error.message); status("Export could not finish."); }
  } finally {
    if (request === state.request) updateControls();
  }
}

$("run").addEventListener("click", runSource);
$("play").addEventListener("click", play);
$("step").addEventListener("click", () => step());
$("replay").addEventListener("click", () => {
  pause(true);
  state.cursor = 0;
  syncMediaPosition();
  if (state.view === "runtime" && state.events.length) {
    selectEvent(0);
    state.selectedNote = (state.noteIndices.get(state.events[0].id) ?? -1);
  } else if (state.notes.length) selectNote(0, false);
  revealCursor();
  updateControls();
  drawTimeline();
  status("Rewound to the beginning. Press Play to listen.");
});
$("source").addEventListener("input", () => {
  if (state.view === "code" || state.side === "right" || state.run?.performance) return;
  state.source = $("source").value;
  clearRun();
  updateGutter();
  status("Source changed. Run it again to update the trace and score.");
});
$("source").addEventListener("scroll", () => { $("line-numbers").scrollTop = $("source").scrollTop; });
$("source").addEventListener("mouseup", () => {
  const line = $("source").value.slice(0, $("source").selectionStart).split("\n").length;
  inspectSourceLine(line);
});
$("source").addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "]" && !$("source").readOnly) {
    event.preventDefault();
    const editor = $("source");
    editor.setRangeText("  ", editor.selectionStart, editor.selectionEnd, "end");
    editor.dispatchEvent(new Event("input", {bubbles: true}));
  }
});
$("line-numbers").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-line]");
  if (!button) return;
  const line = Number(button.dataset.line);
  if (state.view === "code") { inspectSourceLine(line); return; }
  if (state.breakpoints.has(line)) state.breakpoints.delete(line);
  else state.breakpoints.add(line);
  updateBreakpoints();
});
$("clear-breakpoints").addEventListener("click", () => { state.breakpoints.clear(); updateBreakpoints(); });
$("previous-line-event").addEventListener("click", () => navigateLine(-1));
$("next-line-event").addEventListener("click", () => navigateLine(1));
$("runtime-view").addEventListener("click", () => { if (state.scoreDirty) { showError("Validate or discard the musical draft before leaving it."); return; } state.view = "runtime"; configureView(); status("Execution view. Notes follow the runtime trace."); });
$("code-view").addEventListener("click", () => { if (state.run?.performance) return; state.view = "code"; configureView(); status("Executable score view. Notes encode the canonical program."); });
$("palette").addEventListener("change", () => { if (state.run) runSource(Boolean(state.comparison)); });
$("speed").addEventListener("change", () => {
  const resume = state.playing;
  pause(true);
  state.speed = Number($("speed").value);
  if (resume) play();
});
$("zoom").addEventListener("input", () => {
  state.zoom = Number($("zoom").value);
  sizeTimeline();
  revealCursor();
});
$("timeline-scroll").addEventListener("scroll", drawTimeline);
$("timeline").addEventListener("click", (event) => {
  const bounds = $("timeline").getBoundingClientRect();
  const x = event.clientX - bounds.left, y = event.clientY - bounds.top;
  const beat = (x - 42 + $("timeline-scroll").scrollLeft) / state.zoom;
  const row = (bounds.height - 41) / (state.highPitch - state.lowPitch + 1);
  const pitch = state.highPitch - Math.floor((y - 28) / row);
  let index = lowerBound(state.notes, Math.max(0, beat - state.longest - 0.05));
  let nearest = -1, distance = Infinity;
  for (; index < state.notes.length && state.notes[index].start <= beat + 0.1; index++) {
    const note = state.notes[index];
    if (beat < note.start - 3 / state.zoom || beat > note.start + note.duration + 3 / state.zoom) continue;
    const gap = Math.abs(pitch - note.pitch);
    if (gap < distance && gap <= 1) { distance = gap; nearest = index; }
  }
  if (nearest >= 0) selectNote(nearest);
  else if (state.run && beat >= 0) {
    pause(true);
    state.cursor = Math.min(beat, state.total);
    syncMediaPosition();
    if (state.view === "runtime") {
      const point = lowerBound(state.eventTimeline, state.cursor + 0.000001) - 1;
      if (point >= 0) {
        const index = state.eventTimeline[point].index;
        selectEvent(index);
        state.selectedNote = state.noteIndices.get(state.events[index].id) ?? -1;
      }
    } else {
      const position = Math.max(0, lowerBound(state.notes, state.cursor) - 1);
      selectNote(position, false);
    }
    updateControls();
    drawTimeline();
  }
});
for (const [id, kind] of [["export-wav", "wav"], ["export-midi", "midi"], ["export-code", "code-midi"]]) {
  $(id).addEventListener("click", () => download(kind, $(id)));
}
$("examples").addEventListener("change", () => {
  if ($("examples").value === "") return;
  const example = state.examples[Number($("examples").value)];
  if (!example) return;
  $("performances").value = "";
  state.view = "runtime";
  state.source = example.source;
  state.name = example.name;
  $("fixtures").value = example.inputs_json || "[]";
  state.breakpoints.clear();
  clearRun();
  configureView();
  runSource();
});
$("performances").addEventListener("change", () => { if ($("performances").value) loadPerformance($("performances").value); });
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); if (!state.busy) runSource(); return; }
  if (event.key === "Escape") { pause(); return; }
  if (["TEXTAREA", "INPUT", "SELECT", "BUTTON", "SUMMARY"].includes(event.target.tagName)) return;
  if (event.key === " ") { event.preventDefault(); play(); }
  if (event.key === "ArrowRight") { event.preventDefault(); step(); }
  if (event.key === "ArrowLeft") { event.preventDefault(); step(-1); }
  if (event.key === "Home") { event.preventDefault(); if (state.notes.length) $("replay").click(); }
});
document.addEventListener("visibilitychange", () => { if (document.hidden && state.playing) pause(); });
new ResizeObserver(sizeTimeline).observe($("timeline-scroll"));

function invalidateSettings() {
  if (state.run?.performance) return;
  const code = state.view === "code";
  clearRun();
  state.view = "runtime";
  configureView();
  status(code ? "Settings changed. Run the source again before editing its score." : "Settings changed. Run again to update the accepted trace and sound.");
}
for (const id of ["fixtures", "filter-kinds", "filter-functions", "filter-variables", "range-name", "range-min", "range-max", "source-b", "fixtures-b"]) $(id).addEventListener("input", invalidateSettings);
$("mapping").addEventListener("change", invalidateSettings);
$("apply-settings").addEventListener("click", () => runSource());
$("compare").addEventListener("click", () => runSource(true));
$("copy-to-b").addEventListener("click", () => {
  $("source-b").value = state.source;
  $("fixtures-b").value = $("fixtures").value;
  invalidateSettings();
  status("Copied A and its fixture to B. Edit B, then compare the executions.");
});
$("audition-a").addEventListener("click", () => switchSide("left"));
$("audition-b").addEventListener("click", () => switchSide("right"));
$("jump-divergence").addEventListener("click", jumpDivergence);
for (const id of ["loop-enabled", "loop-start", "loop-end"]) $(id).addEventListener("change", () => {
  pause(true);
  try { readLoop(); showError(""); } catch (error) { state.loop.enabled = false; $("loop-enabled").checked = false; showError(error.message); }
});
for (const [id, target] of [["mark-loop-start", "loop-start"], ["mark-loop-end", "loop-end"]]) $(id).addEventListener("click", () => {
  pause(true);
  $(target).value = String(Math.round(state.cursor * 1000) / 1000);
  try { readLoop(); showError(""); } catch (error) { showError(error.message); }
});
$("event-seek").addEventListener("input", () => seekEvent(Number($("event-seek").value)));
$("token-cells").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-token-index]");
  if (button) chooseToken(Number(button.dataset.tokenIndex));
});
for (const [id, action] of [["token-replace", "replace"], ["token-insert-before", "before"], ["token-insert-after", "after"], ["token-delete", "delete"]]) $(id).addEventListener("click", () => editToken(action));
$("token-page-back").addEventListener("click", () => { state.scorePage--; renderTokens(); });
$("token-page-next").addEventListener("click", () => { state.scorePage++; renderTokens(); });
$("score-apply").addEventListener("click", applyScore);
$("score-reset").addEventListener("click", () => { if (state.run) { activateRun(state.run); showError(""); status("Discarded musical-cell edits. The accepted source is unchanged."); } });

async function initialize() {
  const results = await Promise.allSettled([
    fetch("/api/default").then(responseJSON), fetch("/api/examples").then(responseJSON),
    fetch("/api/performances").then(responseJSON),
  ]);
  if (results[1].status === "fulfilled") {
    state.examples = results[1].value.examples;
    for (const [index, example] of state.examples.entries()) {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = example.name;
      $("examples").append(option);
    }
  }
  if (results[2].status === "fulfilled") {
    state.performances = results[2].value.performances || [];
    $("performance-picker").hidden = !state.performances.length;
    for (const performance of state.performances) {
      const option = document.createElement("option");
      option.value = performance.id;
      option.textContent = performance.title || performance.name;
      $("performances").append(option);
    }
  }
  const initial = results[0].status === "fulfilled" ? results[0].value : state.examples[0];
  if (!initial) {
    status("Could not load a program. Enter source and press Run.");
    showError(results[0].reason?.message || "Local server did not respond.");
    updateGutter();
    sizeTimeline();
    return;
  }
  state.source = initial.source;
  state.name = initial.name;
  $("fixtures").value = initial.inputs_json || "[]";
  configureView();
  await runSource();
}

initialize();
