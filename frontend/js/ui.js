// DOM update logic + page wiring. Depends on window.api from api.js.

const AMENITY_FLAGS = {
  parking: "Parking",
  balcony: "Balcony",
  gym: "Gym",
  swimming_pool: "Swimming Pool",
  lift: "Lift",
};

// Cached response from the last successful /recommend or /recommend/recalculate.
// Chat POSTs this back so the backend doesn't recompute pricing per question;
// the analyst's chosen comp set flows through unchanged.
let lastRecommendation = null;

const inr = (n) =>
  new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(Number(n) || 0);

function refreshIcons() {
  if (window.lucide && typeof window.lucide.createIcons === "function") {
    window.lucide.createIcons();
  }
}

function populatePropertyDropdown(properties) {
  const sel = document.getElementById("property-select");
  if (!sel) return;
  if (!properties.length) {
    sel.innerHTML = `<option value="">No properties found</option>`;
    return;
  }
  sel.innerHTML = properties
    .map(
      (p) =>
        `<option value="${p.property_id}">${p.property_name} — ${p.locality}</option>`
    )
    .join("");
}

function renderPropertyDetails(p) {
  const addressEl = document.getElementById("property-address");
  if (addressEl) addressEl.textContent = `${p.property_name}, ${p.address}`;

  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  };
  setText("property-bedrooms", p.bedrooms);
  setText("property-bathrooms", p.bathrooms);
  setText("property-sqft", p.area_sqft);

  const amen = document.getElementById("property-amenities");
  if (amen) {
    const chips = Object.entries(AMENITY_FLAGS)
      .filter(([key]) => Number(p[key]) === 1)
      .map(
        ([, label]) =>
          `<span class="text-xs px-2.5 py-1 rounded-full bg-white ring-1 ring-gray-200 text-gray-600">${label}</span>`
      );
    amen.innerHTML = chips.length
      ? chips.join("")
      : `<span class="text-xs text-gray-400">None listed</span>`;
  }
}

function renderComparables(comps) {
  const grid = document.getElementById("comparables-grid");
  if (!grid) return;

  if (!comps.length) {
    grid.innerHTML = `<p class="text-sm text-gray-500 col-span-full">No comparables found.</p>`;
    updateRecalculateButton();
    return;
  }

  grid.innerHTML = comps
    .map((c) => {
      const pct = Math.round((c.similarity_score ?? 0) * 100);
      return `
        <div data-comp-card class="rounded-xl p-4 ring-1 transition-colors ring-blue-300 bg-blue-50/40">
          <div class="flex items-start justify-between mb-2">
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked data-comp-id="${c.property_id}" class="comp-checkbox w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
            </label>
            <span class="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-green-50 text-green-700 ring-1 ring-inset ring-green-200">
              ${pct}% match
            </span>
          </div>
          <h3 class="text-sm font-semibold text-gray-900 mb-0.5">${c.property_name}</h3>
          <p class="text-lg font-bold text-gray-900 mb-1">₹${inr(c.current_rent)}<span class="text-xs font-medium text-gray-400">/mo</span></p>
          <p class="text-xs text-gray-500 flex items-center gap-1 mb-3">
            <i data-lucide="map-pin" class="w-3.5 h-3.5"></i>
            ${c.locality}
          </p>
          <div class="flex flex-wrap gap-1.5">
            <span class="text-[11px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-200">${c.bedrooms} BR</span>
            <span class="text-[11px] px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 ring-1 ring-inset ring-purple-200">${c.area_sqft} sqft</span>
          </div>
        </div>
      `;
    })
    .join("");

  grid.querySelectorAll(".comp-checkbox").forEach((cb) => {
    cb.addEventListener("change", onCompCheckboxChange);
  });

  updateRecalculateButton();
  refreshIcons();
}

function renderComparablesPlaceholder(message) {
  const grid = document.getElementById("comparables-grid");
  if (!grid) return;
  grid.innerHTML = `<p class="text-sm text-gray-500 col-span-full">${message}</p>`;
  updateRecalculateButton();
}

function getSelectedCompIds() {
  return Array.from(document.querySelectorAll(".comp-checkbox"))
    .filter((cb) => cb.checked)
    .map((cb) => cb.dataset.compId);
}

function updateRecalculateButton() {
  const btn = document.getElementById("recalculate-btn");
  if (!btn) return;
  const total = document.querySelectorAll(".comp-checkbox").length;
  const selected = getSelectedCompIds().length;

  let label;
  if (total === 0) {
    btn.disabled = true;
    label = "Recalculate Recommendation";
  } else if (selected === 0) {
    btn.disabled = true;
    label = "Select at least one comparable";
  } else {
    btn.disabled = false;
    label = `Recalculate with ${selected} comparable${selected === 1 ? "" : "s"}`;
  }
  btn.innerHTML = `<i data-lucide="refresh-cw" class="w-4 h-4"></i> ${label}`;
  refreshIcons();
}

function onCompCheckboxChange(event) {
  const cb = event.target;
  const card = cb.closest("[data-comp-card]");
  if (card) {
    if (cb.checked) {
      card.classList.remove("ring-gray-200", "bg-white");
      card.classList.add("ring-blue-300", "bg-blue-50/40");
    } else {
      card.classList.remove("ring-blue-300", "bg-blue-50/40");
      card.classList.add("ring-gray-200", "bg-white");
    }
  }
  updateRecalculateButton();
}

const CONFIDENCE_PILL_CLASSES = {
  high: "bg-green-50 text-green-700 ring-green-200",
  medium: "bg-amber-50 text-amber-700 ring-amber-200",
  low: "bg-red-50 text-red-700 ring-red-200",
};

function renderRecommendation(rec) {
  lastRecommendation = rec;
  updateChatSendButton();

  const pill = document.getElementById("recommendation-confidence");
  if (pill) {
    const pct = Math.round((rec.confidence?.score ?? 0) * 100);
    const level = rec.confidence?.level ?? "low";
    const colours = CONFIDENCE_PILL_CLASSES[level] ?? CONFIDENCE_PILL_CLASSES.low;
    pill.className = `inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full ring-1 ring-inset ${colours}`;
    pill.innerHTML = `
      <i data-lucide="check-circle-2" class="w-3.5 h-3.5"></i>
      ${pct}% Confidence (${level})
    `;
  }

  const rent = document.getElementById("recommendation-rent");
  if (rent) {
    rent.innerHTML =
      rec.recommended_rent != null
        ? `₹${inr(rec.recommended_rent)}<span class="text-lg font-medium text-gray-500">/month</span>`
        : `<span class="text-gray-400">—</span>`;
  }

  const range = document.getElementById("recommendation-range");
  if (range) {
    const { min, max } = rec.price_range ?? {};
    range.textContent =
      min != null && max != null ? `Range: ₹${inr(min)} – ₹${inr(max)}` : "";
  }

  const notesEl = document.getElementById("recommendation-notes");
  if (notesEl) {
    const notes = rec.pricing_factors?.notes ?? [];
    notesEl.innerHTML = notes.length
      ? notes
          .map(
            (n) => `
              <li class="flex items-start gap-2 text-sm text-gray-700">
                <i data-lucide="check" class="w-4 h-4 text-blue-600 mt-0.5 shrink-0"></i>
                <span>${n}</span>
              </li>
            `
          )
          .join("")
      : `<li class="text-sm text-gray-500">No pricing factors reported.</li>`;
  }

  const updated = document.getElementById("recommendation-updated");
  if (updated) {
    const now = new Date();
    updated.innerHTML = `
      <i data-lucide="clock" class="w-3.5 h-3.5"></i>
      Last updated: ${now.toLocaleString()}
    `;
  }

  refreshIcons();
}

function renderRecommendationPlaceholder(message) {
  lastRecommendation = null;
  updateChatSendButton();

  const pill = document.getElementById("recommendation-confidence");
  if (pill) {
    pill.className = "hidden";
    pill.innerHTML = "";
  }
  const rent = document.getElementById("recommendation-rent");
  if (rent) rent.innerHTML = `<span class="text-gray-400">—</span>`;
  const range = document.getElementById("recommendation-range");
  if (range) range.textContent = "";
  const notesEl = document.getElementById("recommendation-notes");
  if (notesEl) notesEl.innerHTML = `<li class="text-sm text-gray-500">${message}</li>`;
  const updated = document.getElementById("recommendation-updated");
  if (updated) updated.innerHTML = "";
}

async function onPropertyChange(propertyId) {
  if (!propertyId) return;
  clearChatTranscript();
  try {
    const p = await window.api.getProperty(propertyId);
    renderPropertyDetails(p);
    renderComparablesPlaceholder(
      "Click Find Comparables to see the top 5 similar properties."
    );
    renderRecommendationPlaceholder(
      "Click Generate AI Recommendation to see the analysis."
    );
  } catch (err) {
    console.error("Failed to load property details:", err);
  }
}

async function onRecalculate() {
  const sel = document.getElementById("property-select");
  const btn = document.getElementById("recalculate-btn");
  if (!sel || !btn || !sel.value) return;

  const ids = getSelectedCompIds();
  if (!ids.length) return;

  btn.disabled = true;
  btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Recalculating…`;
  refreshIcons();
  renderRecommendationPlaceholder("Recalculating with selected comparables…");

  try {
    const rec = await window.api.recalculateRecommendation(sel.value, ids);
    renderRecommendation(rec);
  } catch (err) {
    console.error("Recalculate failed:", err);
    renderRecommendationPlaceholder(
      "Failed to recalculate. Check the backend on :8001."
    );
  } finally {
    updateRecalculateButton();
  }
}

async function onGenerateRecommendation() {
  const sel = document.getElementById("property-select");
  const btn = document.getElementById("generate-recommendation-btn");
  if (!sel || !btn || !sel.value) return;

  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Analyzing…`;
  refreshIcons();
  renderRecommendationPlaceholder("Analyzing comparables…");

  try {
    const rec = await window.api.getRecommendation(sel.value);
    renderRecommendation(rec);
  } catch (err) {
    console.error("Failed to load recommendation:", err);
    renderRecommendationPlaceholder(
      "Failed to load recommendation. Check the backend on :8001."
    );
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalHtml;
    refreshIcons();
  }
}

async function onFindComparables() {
  const sel = document.getElementById("property-select");
  const btn = document.getElementById("find-comparables-btn");
  if (!sel || !btn || !sel.value) return;

  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Loading…`;
  refreshIcons();
  renderComparablesPlaceholder("Finding comparables…");

  try {
    const comps = await window.api.getComparables(sel.value);
    renderComparables(comps);
  } catch (err) {
    console.error("Failed to load comparables:", err);
    renderComparablesPlaceholder("Failed to load comparables. Check the backend on :8001.");
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalHtml;
    refreshIcons();
  }
}

// ---------- Chat panel ----------

function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = String(str ?? "");
  return d.innerHTML;
}

function scrollTranscriptToBottom() {
  const t = document.getElementById("chat-transcript");
  if (t) t.scrollTop = t.scrollHeight;
}

function removeChatEmptyHint() {
  const hint = document.getElementById("chat-empty-hint");
  if (hint) hint.remove();
}

function clearChatTranscript() {
  const t = document.getElementById("chat-transcript");
  if (!t) return;
  t.innerHTML = `
    <p id="chat-empty-hint" class="text-sm text-gray-500 text-center py-6">
      Generate a recommendation first, then ask a follow-up question below.
    </p>
  `;
}

function appendUserBubble(text) {
  const t = document.getElementById("chat-transcript");
  if (!t) return;
  removeChatEmptyHint();
  const wrap = document.createElement("div");
  wrap.className = "flex justify-end mb-3";
  wrap.innerHTML = `
    <div class="max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed bg-blue-600 text-white rounded-br-sm whitespace-pre-wrap">${escapeHtml(text)}</div>
    <div class="w-7 h-7 rounded-full bg-gray-300 flex items-center justify-center ml-2 shrink-0 text-[11px] font-medium text-gray-600">AN</div>
  `;
  t.appendChild(wrap);
  scrollTranscriptToBottom();
}

function appendAssistantBubble(text, references) {
  const t = document.getElementById("chat-transcript");
  if (!t) return;
  removeChatEmptyHint();
  const chips = (references ?? [])
    .map(
      (r) => `
        <span class="text-[11px] px-2 py-0.5 rounded-full bg-white ring-1 ring-inset ring-gray-200 text-gray-600">
          ${escapeHtml(r.property_id)} · ${escapeHtml(r.locality ?? "")} · ₹${inr(r.current_rent)}
        </span>`
    )
    .join("");
  const wrap = document.createElement("div");
  wrap.className = "flex justify-start mb-3";
  wrap.innerHTML = `
    <div class="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center mr-2 shrink-0">
      <i data-lucide="sparkles" class="w-3.5 h-3.5 text-white"></i>
    </div>
    <div class="max-w-[80%]">
      <div class="rounded-2xl px-4 py-2.5 text-sm leading-relaxed bg-gray-100 text-gray-800 rounded-bl-sm whitespace-pre-wrap">${escapeHtml(text)}</div>
      ${chips ? `<div class="mt-2 flex flex-wrap gap-1.5">${chips}</div>` : ""}
    </div>
  `;
  t.appendChild(wrap);
  scrollTranscriptToBottom();
  refreshIcons();
}

function appendErrorBubble(text) {
  const t = document.getElementById("chat-transcript");
  if (!t) return;
  removeChatEmptyHint();
  const wrap = document.createElement("div");
  wrap.className = "flex justify-start mb-3";
  wrap.innerHTML = `
    <div class="w-7 h-7 rounded-full bg-red-100 flex items-center justify-center mr-2 shrink-0">
      <i data-lucide="alert-triangle" class="w-3.5 h-3.5 text-red-600"></i>
    </div>
    <div class="max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed bg-red-50 text-red-800 ring-1 ring-inset ring-red-200 rounded-bl-sm">
      ${escapeHtml(text)}
    </div>
  `;
  t.appendChild(wrap);
  scrollTranscriptToBottom();
  refreshIcons();
}

function updateChatSendButton() {
  const btn = document.getElementById("chat-send-btn");
  if (!btn) return;
  const hasContext = lastRecommendation != null;
  btn.disabled = !hasContext;
  const label = hasContext ? "Send" : "Generate a recommendation first";
  btn.innerHTML = `<i data-lucide="send" class="w-4 h-4"></i><span class="hidden sm:inline">${label}</span>`;
  refreshIcons();
}

async function onSendChat() {
  const input = document.getElementById("chat-input");
  const btn = document.getElementById("chat-send-btn");
  const sel = document.getElementById("property-select");
  if (!input || !btn || !sel || !sel.value) return;

  const question = input.value.trim();
  if (!question) return;
  if (!lastRecommendation) {
    appendErrorBubble("Generate a recommendation first — chat needs the pricing context.");
    return;
  }

  appendUserBubble(question);
  input.value = "";

  btn.disabled = true;
  btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span class="hidden sm:inline">Thinking…</span>`;
  refreshIcons();

  try {
    const res = await window.api.chat(sel.value, question, lastRecommendation);
    appendAssistantBubble(res.answer || "(empty response)", res.references || []);
  } catch (err) {
    console.error("Chat failed:", err);
    appendErrorBubble(err.message || "Chat request failed.");
  } finally {
    updateChatSendButton();
  }
}

async function init() {
  try {
    const props = await window.api.listProperties();
    populatePropertyDropdown(props);

    const sel = document.getElementById("property-select");
    if (sel) sel.addEventListener("change", (e) => onPropertyChange(e.target.value));

    const btn = document.getElementById("find-comparables-btn");
    if (btn) btn.addEventListener("click", onFindComparables);

    const genBtn = document.getElementById("generate-recommendation-btn");
    if (genBtn) genBtn.addEventListener("click", onGenerateRecommendation);

    const recalcBtn = document.getElementById("recalculate-btn");
    if (recalcBtn) recalcBtn.addEventListener("click", onRecalculate);

    const sendBtn = document.getElementById("chat-send-btn");
    if (sendBtn) sendBtn.addEventListener("click", onSendChat);
    const chatInput = document.getElementById("chat-input");
    if (chatInput) {
      chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          onSendChat();
        }
      });
    }

    renderComparablesPlaceholder(
      "Select a property and click Find Comparables to see the top 5 similar properties."
    );
    renderRecommendationPlaceholder(
      "Select a property and click Generate AI Recommendation to see the analysis."
    );
    updateChatSendButton();

    if (props.length) await onPropertyChange(props[0].property_id);
  } catch (err) {
    console.error("Init failed:", err);
  }
}

document.addEventListener("DOMContentLoaded", init);
