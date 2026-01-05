const state = {
  search: "",
  gender: "All",
  origin: "All",
  theme: "All",
  letter: "All",
  data: [],
};

const elements = {
  search: document.getElementById("search"),
  gender: document.getElementById("gender-filter"),
  origin: document.getElementById("origin-filter"),
  theme: document.getElementById("theme-filter"),
  letter: document.getElementById("letter-filter"),
  results: document.getElementById("results"),
  total: document.getElementById("total-count"),
  active: document.getElementById("active-count"),
  resultsTitle: document.getElementById("results-title"),
  chipRow: document.getElementById("chip-row"),
  clear: document.getElementById("clear-filters"),
};

const createOption = (value, label = value) => {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  return option;
};

const buildSelect = (select, values) => {
  select.innerHTML = "";
  select.appendChild(createOption("All"));
  values.forEach((value) => select.appendChild(createOption(value)));
};

const normalize = (value) => value.toLowerCase();

const filterData = () => {
  const searchTerm = normalize(state.search);
  return state.data.filter((entry) => {
    const matchesSearch =
      !searchTerm ||
      [entry.name, entry.meaning, entry.origin, entry.theme]
        .filter(Boolean)
        .some((field) => normalize(field).includes(searchTerm));
    const matchesGender = state.gender === "All" || entry.gender === state.gender;
    const matchesOrigin = state.origin === "All" || entry.origin === state.origin;
    const matchesTheme = state.theme === "All" || entry.theme === state.theme;
    const matchesLetter =
      state.letter === "All" || entry.name.startsWith(state.letter);

    return (
      matchesSearch &&
      matchesGender &&
      matchesOrigin &&
      matchesTheme &&
      matchesLetter
    );
  });
};

const renderChips = () => {
  const chips = [];
  if (state.gender !== "All") {
    chips.push({ key: "gender", label: `Gender: ${state.gender}` });
  }
  if (state.origin !== "All") {
    chips.push({ key: "origin", label: `Origin: ${state.origin}` });
  }
  if (state.theme !== "All") {
    chips.push({ key: "theme", label: `Theme: ${state.theme}` });
  }
  if (state.letter !== "All") {
    chips.push({ key: "letter", label: `Letter: ${state.letter}` });
  }

  elements.chipRow.innerHTML = "";
  chips.forEach((chip) => {
    const pill = document.createElement("div");
    pill.className = "chip";
    const text = document.createElement("span");
    text.textContent = chip.label;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "×";
    button.addEventListener("click", () => {
      state[chip.key] = "All";
      syncFilters();
      render();
    });
    pill.append(text, button);
    elements.chipRow.appendChild(pill);
  });
};

const renderCards = (data) => {
  elements.results.innerHTML = "";
  if (!data.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No names match these filters. Try a new search.";
    elements.results.appendChild(empty);
    return;
  }

  data.forEach((entry) => {
    const card = document.createElement("article");
    card.className = "card";

    const title = document.createElement("h4");
    title.textContent = entry.name;

    const meaning = document.createElement("p");
    meaning.textContent = entry.meaning;

    const badges = document.createElement("div");
    badges.className = "badges";
    [entry.gender, entry.origin, entry.theme]
      .filter(Boolean)
      .forEach((value) => {
        const badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent = value;
        badges.appendChild(badge);
      });

    const notes = document.createElement("p");
    notes.textContent = entry.notes;

    card.append(title, meaning, badges, notes);
    elements.results.appendChild(card);
  });
};

const render = () => {
  const filtered = filterData();
  elements.total.textContent = state.data.length.toLocaleString();
  elements.active.textContent = [
    state.gender,
    state.origin,
    state.theme,
    state.letter,
  ].filter((value) => value !== "All").length;

  const heading = state.search
    ? `Results for “${state.search}” (${filtered.length})`
    : `Showing ${filtered.length} name${filtered.length === 1 ? "" : "s"}`;
  elements.resultsTitle.textContent = heading;
  renderChips();
  renderCards(filtered);
};

const syncFilters = () => {
  elements.gender.value = state.gender;
  elements.origin.value = state.origin;
  elements.theme.value = state.theme;
  elements.letter.value = state.letter;
};

const attachListeners = () => {
  elements.search.addEventListener("input", (event) => {
    state.search = event.target.value.trim();
    render();
  });

  [
    [elements.gender, "gender"],
    [elements.origin, "origin"],
    [elements.theme, "theme"],
    [elements.letter, "letter"],
  ].forEach(([element, key]) => {
    element.addEventListener("change", (event) => {
      state[key] = event.target.value;
      render();
    });
  });

  elements.clear.addEventListener("click", () => {
    state.search = "";
    state.gender = "All";
    state.origin = "All";
    state.theme = "All";
    state.letter = "All";
    elements.search.value = "";
    syncFilters();
    render();
  });
};

const init = async () => {
  const response = await fetch("./data/names.json");
  const data = await response.json();
  state.data = data;

  const genders = [...new Set(data.map((entry) => entry.gender))].sort();
  const origins = [...new Set(data.map((entry) => entry.origin))].sort();
  const themes = [...new Set(data.map((entry) => entry.theme))].sort();
  const letters = [
    ...new Set(data.map((entry) => entry.name.charAt(0).toUpperCase())),
  ].sort();

  buildSelect(elements.gender, genders);
  buildSelect(elements.origin, origins);
  buildSelect(elements.theme, themes);
  buildSelect(elements.letter, letters);

  attachListeners();
  render();
};

init();
