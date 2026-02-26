const STORAGE_KEY = "visit-tracker-data-v1";

const state = {
  establishments: [],
  visits: [],
};

const elements = {
  establishmentForm: document.getElementById("establishment-form"),
  establishmentName: document.getElementById("establishment-name"),
  establishmentType: document.getElementById("establishment-type"),
  visitForm: document.getElementById("visit-form"),
  visitEstablishment: document.getElementById("visit-establishment"),
  visitDate: document.getElementById("visit-date"),
  likedNotes: document.getElementById("liked-notes"),
  dislikedNotes: document.getElementById("disliked-notes"),
  visitList: document.getElementById("visit-list"),
  emptyMessage: document.getElementById("empty-message"),
  clearAll: document.getElementById("clear-all"),
};

const saveState = () => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
};

const loadState = () => {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return;
  }

  try {
    const parsed = JSON.parse(raw);
    state.establishments = Array.isArray(parsed.establishments)
      ? parsed.establishments
      : [];
    state.visits = Array.isArray(parsed.visits) ? parsed.visits : [];
  } catch {
    state.establishments = [];
    state.visits = [];
  }
};

const createId = () =>
  `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

const formatDate = (isoDate) => {
  const parsed = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return isoDate;
  }

  return parsed.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

const syncEstablishmentDropdown = () => {
  elements.visitEstablishment.innerHTML = "";

  if (!state.establishments.length) {
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Add an establishment first";
    elements.visitEstablishment.appendChild(placeholder);
    elements.visitEstablishment.disabled = true;
    return;
  }

  elements.visitEstablishment.disabled = false;

  state.establishments
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .forEach((entry) => {
      const option = document.createElement("option");
      option.value = entry.id;
      option.textContent = `${entry.name} (${entry.type})`;
      elements.visitEstablishment.appendChild(option);
    });
};

const findEstablishment = (id) =>
  state.establishments.find((entry) => entry.id === id);

const renderVisits = () => {
  elements.visitList.innerHTML = "";

  const sortedVisits = state.visits
    .slice()
    .sort((a, b) => b.date.localeCompare(a.date) || b.createdAt - a.createdAt);

  if (!sortedVisits.length) {
    elements.emptyMessage.style.display = "block";
    return;
  }

  elements.emptyMessage.style.display = "none";

  sortedVisits.forEach((visit) => {
    const establishment = findEstablishment(visit.establishmentId);
    const item = document.createElement("li");
    item.className = "visit-item";

    const title = document.createElement("h3");
    title.textContent = establishment
      ? `${establishment.name} · ${establishment.type}`
      : "Unknown establishment";

    const date = document.createElement("p");
    date.className = "meta";
    date.textContent = `Visited on ${formatDate(visit.date)}`;

    const liked = document.createElement("p");
    liked.innerHTML = `<strong>Liked:</strong> ${visit.liked || "—"}`;

    const disliked = document.createElement("p");
    disliked.innerHTML = `<strong>Did not like:</strong> ${visit.disliked || "—"}`;

    item.append(title, date, liked, disliked);
    elements.visitList.appendChild(item);
  });
};

const addEstablishment = (event) => {
  event.preventDefault();

  const name = elements.establishmentName.value.trim();
  const type = elements.establishmentType.value;
  if (!name) {
    return;
  }

  const duplicate = state.establishments.some(
    (entry) => entry.name.toLowerCase() === name.toLowerCase() && entry.type === type,
  );

  if (duplicate) {
    alert("That establishment is already in the list.");
    return;
  }

  state.establishments.push({
    id: createId(),
    name,
    type,
  });

  elements.establishmentForm.reset();
  elements.establishmentType.value = "Restaurant";
  syncEstablishmentDropdown();
  saveState();
};

const addVisit = (event) => {
  event.preventDefault();

  if (!state.establishments.length) {
    alert("Add an establishment first.");
    return;
  }

  const establishmentId = elements.visitEstablishment.value;
  const date = elements.visitDate.value;
  const liked = elements.likedNotes.value.trim();
  const disliked = elements.dislikedNotes.value.trim();

  if (!establishmentId || !date) {
    return;
  }

  state.visits.push({
    id: createId(),
    establishmentId,
    date,
    liked,
    disliked,
    createdAt: Date.now(),
  });

  elements.visitForm.reset();
  elements.visitDate.value = new Date().toISOString().split("T")[0];
  syncEstablishmentDropdown();
  renderVisits();
  saveState();
};

const clearAllData = () => {
  const confirmed = confirm("Clear all establishments and visit history?");
  if (!confirmed) {
    return;
  }

  state.establishments = [];
  state.visits = [];
  syncEstablishmentDropdown();
  renderVisits();
  saveState();
};

const attachListeners = () => {
  elements.establishmentForm.addEventListener("submit", addEstablishment);
  elements.visitForm.addEventListener("submit", addVisit);
  elements.clearAll.addEventListener("click", clearAllData);
};

const init = () => {
  loadState();
  syncEstablishmentDropdown();
  renderVisits();
  attachListeners();
  elements.visitDate.value = new Date().toISOString().split("T")[0];
};

init();
