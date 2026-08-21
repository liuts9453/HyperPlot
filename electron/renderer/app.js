"use strict";

const api = window.hyperplot;
const elements = {
  backendStatus: document.querySelector("#backendStatus"),
  openButton: document.querySelector("#openButton"),
  curveList: document.querySelector("#curveList"),
  selectionCount: document.querySelector("#selectionCount"),
  selectAllButton: document.querySelector("#selectAllButton"),
  invertButton: document.querySelector("#invertButton"),
  reloadButton: document.querySelector("#reloadButton"),
  legendInput: document.querySelector("#legendInput"),
  palette: document.querySelector("#palette"),
  fastCsvInput: document.querySelector("#fastCsvInput"),
  plotButton: document.querySelector("#plotButton"),
  axisButton: document.querySelector("#axisButton"),
  outputInput: document.querySelector("#outputInput"),
  outputButton: document.querySelector("#outputButton"),
  tabs: [...document.querySelectorAll(".tab")],
  previewTab: document.querySelector("#previewTab"),
  messagesTab: document.querySelector("#messagesTab"),
  previewEmpty: document.querySelector("#previewEmpty"),
  previewCanvas: document.querySelector("#previewCanvas"),
  previewImage: document.querySelector("#previewImage"),
  messageCount: document.querySelector("#messageCount"),
  messageLog: document.querySelector("#messageLog"),
  clearMessagesButton: document.querySelector("#clearMessagesButton"),
  stageBusy: document.querySelector("#stageBusy"),
  templateButton: document.querySelector("#templateButton"),
  properties: document.querySelector("#properties"),
  contextMenu: document.querySelector("#contextMenu"),
  curveDialog: document.querySelector("#curveDialog"),
  curveLegendInput: document.querySelector("#curveLegendInput"),
  curveStyleInput: document.querySelector("#curveStyleInput"),
  curveAxisInput: document.querySelector("#curveAxisInput"),
  curveApplyButton: document.querySelector("#curveApplyButton"),
  propertyDialog: document.querySelector("#propertyDialog"),
  propertyDialogTitle: document.querySelector("#propertyDialogTitle"),
  propertyNameInput: document.querySelector("#propertyNameInput"),
  propertyValueInput: document.querySelector("#propertyValueInput"),
  propertyAddButton: document.querySelector("#propertyAddButton"),
  dropOverlay: document.querySelector("#dropOverlay"),
  toastStack: document.querySelector("#toastStack"),
};

const scalarPropertyOrder = [
  "plot_type",
  "right_axis_color",
  "loc",
  "plot_dpi",
  "fig_width_cm",
  "fig_height_cm",
  "show_legend",
  "legend_line_length",
  "legend_frame",
  "label_decimal",
  "marks",
  "background_alpha",
  "background_points",
  "seperator",
  "xmin",
  "xmax",
  "grid",
  "plot_format",
  "fill",
];

let appState = {
  elements: [],
  preferences: {},
  palette: {},
};
let selected = new Set();
let contextIndex = null;
let editingCurveIndex = null;
let propertyParent = null;
let messageTotal = 0;
let dragDepth = 0;

function setBackendStatus(status, text) {
  elements.backendStatus.className = `backend-status ${status || ""}`.trim();
  elements.backendStatus.lastChild.textContent = ` ${text}`;
}

function setBusy(isBusy, message = "Rendering with Matplotlib…") {
  elements.stageBusy.querySelector("p").textContent = message;
  elements.stageBusy.classList.toggle("hidden", !isBusy);
  for (const button of [
    elements.plotButton,
    elements.outputButton,
    elements.reloadButton,
  ]) {
    button.disabled = isBusy;
  }
}

function timeStamp() {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function logMessage(message, isError = false) {
  if (!message) return;
  for (const line of String(message).split(/\r?\n/).filter(Boolean)) {
    const row = document.createElement("div");
    row.className = `message-line${isError ? " error" : ""}`;
    const time = document.createElement("time");
    time.textContent = timeStamp();
    row.append(time, document.createTextNode(line));
    elements.messageLog.append(row);
    messageTotal += 1;
  }
  elements.messageCount.textContent = String(messageTotal);
  elements.messageLog.scrollTop = elements.messageLog.scrollHeight;
}

function toast(message, isError = false) {
  const item = document.createElement("div");
  item.className = `toast${isError ? " error" : ""}`;
  item.textContent = message;
  elements.toastStack.append(item);
  setTimeout(() => item.remove(), isError ? 5200 : 3300);
}

async function request(action, payload = {}) {
  try {
    const response = await api.request(action, payload);
    for (const line of response.logs || []) logMessage(line);
    return response.result;
  } catch (error) {
    const message = error?.message || String(error);
    logMessage(message, true);
    toast(message, true);
    throw error;
  }
}

function applyState(nextState) {
  if (!nextState) return;
  appState = nextState;
  selected = new Set(
    [...selected].filter((index) => index >= 0 && index < appState.elements.length),
  );
  renderWorkbench();
  renderPalette();
  renderProperties();
}

function renderWorkbench() {
  elements.curveList.replaceChildren();
  const rows = appState.elements || [];
  elements.curveList.classList.toggle("has-items", rows.length > 0);

  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = `
      <div class="empty-icon">
        <svg viewBox="0 0 64 64" aria-hidden="true">
          <path d="M10 46 23 29l10 8 20-25"></path>
          <path d="M10 10v44h44"></path>
        </svg>
      </div>
      <h3>Drop your data here</h3>
      <p>CSV data, HyperPlot SVG/PNG state, or a plot template</p>
      <button class="button button-secondary empty-open">Choose files</button>`;
    empty.querySelector(".empty-open").addEventListener("click", chooseAndImport);
    elements.curveList.append(empty);
    updateSelectionSummary();
    return;
  }

  for (const row of rows) {
    const item = document.createElement("div");
    item.className = `curve-row${selected.has(row.index) ? " selected" : ""}`;
    item.dataset.index = String(row.index);

    const check = document.createElement("input");
    check.className = "curve-check";
    check.type = "checkbox";
    check.checked = selected.has(row.index);
    check.setAttribute("aria-label", `Select ${row.label}`);
    check.addEventListener("change", () => {
      if (check.checked) selected.add(row.index);
      else selected.delete(row.index);
      item.classList.toggle("selected", check.checked);
      updateSelectionSummary();
    });

    const source = document.createElement("div");
    source.className = "curve-source";
    const sourceName = document.createElement("strong");
    sourceName.textContent = row.file_name || "Restored data";
    sourceName.title = row.source_path || sourceName.textContent;
    const xLabel = document.createElement("small");
    const pathParts = (row.source_path || "").split(/[\\/]/).filter(Boolean);
    const parentDirectory =
      pathParts.length > 1 ? pathParts[pathParts.length - 2] : "";
    xLabel.textContent = `${parentDirectory ? `${parentDirectory} · ` : ""}x: ${row.x_label || "x"}`;
    xLabel.title = row.source_path || "";
    source.append(sourceName, xLabel);

    const name = document.createElement("div");
    name.className = "curve-name";
    name.textContent = row.label || `Curve ${row.index + 1}`;
    name.title = name.textContent;

    const style = document.createElement("code");
    style.className = "style-code";
    style.textContent = row.ls || "-";

    const axisCell = document.createElement("div");
    axisCell.className = "axis-cell";
    if (row.is_background) {
      const background = document.createElement("span");
      background.className = "background-tag";
      background.textContent = "BG";
      axisCell.append(background);
    }
    const axis = document.createElement("span");
    axis.className = `axis-tag${row.axis === "right" ? " right" : ""}`;
    axis.textContent = row.axis || "left";
    axisCell.append(axis);

    item.append(check, source, name, style, axisCell);
    item.addEventListener("click", (event) => {
      if (event.target === check) return;
      if (event.ctrlKey || event.metaKey) {
        if (selected.has(row.index)) selected.delete(row.index);
        else selected.add(row.index);
      } else {
        selected.clear();
        selected.add(row.index);
      }
      renderWorkbench();
    });
    item.addEventListener("dblclick", () => openCurveEditor(row.index));
    item.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      if (!selected.has(row.index)) {
        selected.clear();
        selected.add(row.index);
        renderWorkbench();
      }
      contextIndex = row.index;
      showContextMenu(event.clientX, event.clientY);
    });
    elements.curveList.append(item);
  }
  updateSelectionSummary();
}

function updateSelectionSummary() {
  const count = selected.size;
  elements.selectionCount.textContent = `${count} selected`;
  elements.selectAllButton.textContent =
    appState.elements.length > 0 && count === appState.elements.length
      ? "Clear"
      : "All";
  elements.axisButton.disabled = count === 0;
  elements.plotButton.disabled = count === 0;
  elements.outputButton.disabled = count === 0;
}

function readableTextColor(color) {
  const match = /^#([0-9a-f]{6})$/i.exec(color || "");
  if (!match) return ["white", "transparent", "#273638"].includes(color)
    ? "#ffffff"
    : "#172b35";
  const value = Number.parseInt(match[1], 16);
  const red = (value >> 16) & 255;
  const green = (value >> 8) & 255;
  const blue = value & 255;
  return red * 0.299 + green * 0.587 + blue * 0.114 > 155
    ? "#172b35"
    : "#ffffff";
}

function renderPalette() {
  elements.palette.replaceChildren();
  for (const [code, color] of Object.entries(appState.palette || {})) {
    const chip = document.createElement("span");
    chip.className = "palette-chip";
    chip.textContent = code;
    chip.title = `${code} = ${color}`;
    chip.style.background = color;
    chip.style.color = readableTextColor(color);
    elements.palette.append(chip);
  }
}

function propertyInput(name, value, nestedParent = null) {
  let input;
  if (!nestedParent && ["grid", "show_legend", "legend_frame"].includes(name)) {
    input = document.createElement("select");
    for (const optionValue of ["true", "false"]) {
      const option = document.createElement("option");
      option.value = optionValue;
      option.textContent = optionValue;
      input.append(option);
    }
    input.value = String(value).toLowerCase();
  } else {
    input = document.createElement("input");
    input.type = "text";
    input.value =
      value === null || value === undefined
        ? "None"
        : typeof value === "object"
          ? JSON.stringify(value)
          : String(value);
    input.spellcheck = false;
  }
  input.dataset.property = name;
  if (nestedParent) input.dataset.parent = nestedParent;
  const save = () => commitPropertyInput(input);
  input.addEventListener("change", save);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      input.blur();
    }
  });
  return input;
}

function scalarGroup() {
  const details = document.createElement("details");
  details.className = "property-group";
  details.open = true;
  const summary = document.createElement("summary");
  summary.append(document.createTextNode("General"));
  const count = document.createElement("small");
  const names = scalarPropertyOrder.filter((name) =>
    Object.hasOwn(appState.preferences, name),
  );
  count.textContent = `${names.length} settings`;
  summary.append(count);
  details.append(summary);

  for (const name of names) {
    const row = document.createElement("div");
    row.className = "property-row";
    const label = document.createElement("label");
    label.textContent = name;
    label.title = name;
    const spacer = document.createElement("span");
    row.append(label, propertyInput(name, appState.preferences[name]), spacer);
    details.append(row);
  }
  return details;
}

function objectGroup(name, value) {
  const details = document.createElement("details");
  details.className = "property-group";
  details.open = name === "color_palette";
  const summary = document.createElement("summary");
  summary.addEventListener("click", (event) => {
    if (event.target.closest(".property-add")) event.preventDefault();
  });
  summary.append(document.createTextNode(name));
  const add = document.createElement("button");
  add.className = "property-add";
  add.type = "button";
  add.textContent = "+ Add";
  add.addEventListener("click", (event) => {
    event.stopPropagation();
    openPropertyDialog(name);
  });
  const count = document.createElement("small");
  count.textContent = `${Object.keys(value || {}).length} entries`;
  summary.append(add, count);
  details.append(summary);

  for (const [key, itemValue] of Object.entries(value || {})) {
    const row = document.createElement("div");
    row.className = "property-row";
    const label = document.createElement("label");
    label.textContent = key;
    label.title = key;
    const remove = document.createElement("button");
    remove.className = "property-delete";
    remove.type = "button";
    remove.textContent = "×";
    remove.title = `Delete ${key}`;
    remove.addEventListener("click", () => deleteNestedProperty(name, key));
    row.append(label, propertyInput(key, itemValue, name), remove);
    details.append(row);
  }
  return details;
}

function renderProperties() {
  elements.properties.replaceChildren();
  elements.properties.append(scalarGroup());
  for (const name of ["axis_labels", "color_palette"]) {
    elements.properties.append(
      objectGroup(name, appState.preferences[name] || {}),
    );
  }
}

async function commitPropertyInput(input) {
  const name = input.dataset.property;
  const parent = input.dataset.parent;
  const previous = parent
    ? appState.preferences[parent]?.[name]
    : appState.preferences[name];
  if (String(previous) === input.value) return;

  let preferences;
  if (parent) {
    preferences = {
      [parent]: {
        ...(appState.preferences[parent] || {}),
        [name]: input.value,
      },
    };
  } else {
    preferences = { [name]: input.value };
  }
  try {
    const result = await request("set_preferences", { preferences });
    applyState(result.state);
    logMessage(`Updated property: ${parent ? `${parent}.` : ""}${name}`);
  } catch {
    renderProperties();
  }
}

async function deleteNestedProperty(parent, name) {
  const next = { ...(appState.preferences[parent] || {}) };
  delete next[name];
  try {
    const result = await request("set_preferences", {
      preferences: { [parent]: next },
    });
    applyState(result.state);
    logMessage(`Deleted property: ${parent}.${name}`);
  } catch {
    renderProperties();
  }
}

function selectedIndices() {
  return [...selected].sort((a, b) => a - b);
}

async function chooseAndImport() {
  const paths = await api.chooseFiles();
  if (paths.length) await importFiles(paths);
}

async function importFiles(paths) {
  if (!paths?.length) return;
  setBusy(true, "Importing data…");
  try {
    const result = await request("import_files", {
      paths,
      fastCsv: elements.fastCsvInput.checked,
      legends: elements.legendInput.value,
    });
    applyState(result.state);
    for (const message of result.messages || []) logMessage(message);
    if (result.suggestedOutput) {
      elements.outputInput.value = result.suggestedOutput;
    }
    toast(`Imported ${paths.length} file${paths.length === 1 ? "" : "s"}.`);
  } finally {
    setBusy(false);
  }
}

async function plotSelected() {
  const indices = selectedIndices();
  if (!indices.length) {
    toast("Select at least one curve to plot.", true);
    return;
  }
  setTab("preview");
  setBusy(true);
  try {
    const result = await request("preview", {
      indices,
      legends: elements.legendInput.value,
    });
    elements.previewImage.src = result.preview;
    elements.previewEmpty.classList.add("hidden");
    elements.previewCanvas.classList.remove("hidden");
    applyState(result.state);
    logMessage(`Rendered ${indices.length} selected curve(s).`);
  } finally {
    setBusy(false);
  }
}

async function exportPlot() {
  const indices = selectedIndices();
  if (!indices.length) {
    toast("Select at least one curve to export.", true);
    return;
  }
  let suggestedName = elements.outputInput.value.trim();
  if (!suggestedName) {
    const now = new Date();
    const part = (value) => String(value).padStart(2, "0");
    suggestedName = `${now.getFullYear()}${part(now.getMonth() + 1)}${part(now.getDate())}_${part(now.getHours())}${part(now.getMinutes())}${part(now.getSeconds())}.svg`;
  }
  const outputPath = await api.choosePlotOutput(suggestedName);
  if (!outputPath) return;

  setBusy(true, "Exporting plot…");
  try {
    const result = await request("save_plot", {
      path: outputPath,
      indices,
      legends: elements.legendInput.value,
    });
    applyState(result.state);
    elements.outputInput.value = result.path.split(/[\\/]/).pop();
    logMessage(`Plot exported: ${result.path}`);
    toast(`Saved ${result.path.split(/[\\/]/).pop()}`);
  } finally {
    setBusy(false);
  }
}

async function toggleAxis() {
  const indices = selectedIndices();
  if (!indices.length) return;
  const result = await request("toggle_axis", { indices });
  applyState(result.state);
  logMessage(`Toggled axis for ${result.changed.length} curve(s).`);
}

async function reloadSources() {
  setBusy(true, "Reloading source CSV files…");
  try {
    const result = await request("reload");
    applyState(result.state);
    logMessage(
      `Reloaded ${result.reload.element_count} element(s) from ${result.reload.paths.length} file(s).`,
    );
    if (result.reload.missing?.length) {
      logMessage(
        `Missing source files: ${result.reload.missing.join(", ")}`,
        true,
      );
    }
  } finally {
    setBusy(false);
  }
}

function selectAllOrClear() {
  if (
    appState.elements.length > 0 &&
    selected.size === appState.elements.length
  ) {
    selected.clear();
  } else {
    selected = new Set(appState.elements.map((row) => row.index));
  }
  renderWorkbench();
}

function invertSelection() {
  selected = new Set(
    appState.elements
      .map((row) => row.index)
      .filter((index) => !selected.has(index)),
  );
  renderWorkbench();
}

function setTab(name) {
  for (const tab of elements.tabs) {
    tab.classList.toggle("active", tab.dataset.tab === name);
  }
  elements.previewTab.classList.toggle("active", name === "preview");
  elements.messagesTab.classList.toggle("active", name === "messages");
}

function showContextMenu(x, y) {
  const menu = elements.contextMenu;
  menu.classList.remove("hidden");
  const bounds = menu.getBoundingClientRect();
  menu.style.left = `${Math.min(x, window.innerWidth - bounds.width - 8)}px`;
  menu.style.top = `${Math.min(y, window.innerHeight - bounds.height - 8)}px`;
}

function hideContextMenu() {
  elements.contextMenu.classList.add("hidden");
}

async function openCurveEditor(index) {
  hideContextMenu();
  const result = await request("element_detail", { index });
  editingCurveIndex = index;
  elements.curveLegendInput.value = result.detail.label || "";
  elements.curveStyleInput.value = result.detail.ls || "-";
  elements.curveAxisInput.value = result.detail.axis || "left";
  elements.curveDialog.showModal();
  elements.curveLegendInput.focus();
}

async function applyCurveEdit(event) {
  event.preventDefault();
  if (editingCurveIndex === null) return;
  const result = await request("update_element_style", {
    index: editingCurveIndex,
    label: elements.curveLegendInput.value.trim(),
    ls: elements.curveStyleInput.value.trim() || "-",
    axis: elements.curveAxisInput.value,
  });
  elements.curveDialog.close();
  applyState(result.state);
  logMessage(`Updated curve style (${result.count} element(s)).`);
}

async function setContextAsXAxis() {
  if (contextIndex === null) return;
  const result = await request("set_x_axis", { index: contextIndex });
  applyState(result.state);
  const change = result.change;
  logMessage(
    `Set '${change.x_label}' as X axis for ${change.file_name || "the selected source"} (${change.curve_count} curves).`,
  );
}

async function exportSelectedCsv() {
  const indices = selectedIndices();
  if (!indices.length) return;
  let name = elements.outputInput.value.trim() || "selected_curves.csv";
  name = name.replace(/\.[^.]+$/, "") + ".csv";
  const outputPath = await api.chooseCsvOutput(name);
  if (!outputPath) return;
  const result = await request("export_csv", { indices, path: outputPath });
  logMessage(`Selected curves exported: ${result.path}`);
  toast(`Saved ${result.path.split(/[\\/]/).pop()}`);
}

async function setBackground(enabled) {
  const indices = selectedIndices();
  if (!indices.length) return;
  const action = enabled ? "set_background" : "unset_background";
  const result = await request(action, { indices });
  applyState(result.state);
  logMessage(
    `${enabled ? "Set" : "Unset"} background for ${result.count} curve(s).`,
  );
}

async function deleteSelected() {
  const indices = selectedIndices();
  if (!indices.length) return;
  if (!window.confirm(`Delete ${indices.length} selected curve(s)?`)) return;
  const result = await request("delete_elements", { indices });
  selected.clear();
  applyState(result.state);
  logMessage(`Deleted ${result.count} curve(s).`);
}

async function handleContextAction(action) {
  hideContextMenu();
  if (action === "edit") await openCurveEditor(contextIndex);
  else if (action === "x-axis") await setContextAsXAxis();
  else if (action === "export-csv") await exportSelectedCsv();
  else if (action === "background") await setBackground(true);
  else if (action === "unbackground") await setBackground(false);
  else if (action === "delete") await deleteSelected();
}

function openPropertyDialog(parent) {
  propertyParent = parent;
  elements.propertyDialogTitle.textContent =
    parent === "axis_labels" ? "Add axis label" : "Add palette color";
  elements.propertyNameInput.value = "";
  elements.propertyValueInput.value = "";
  elements.propertyDialog.showModal();
  elements.propertyNameInput.focus();
}

async function addNestedProperty(event) {
  event.preventDefault();
  const name = elements.propertyNameInput.value.trim();
  const value = elements.propertyValueInput.value.trim();
  if (!name || !value || !propertyParent) return;
  const result = await request("set_preferences", {
    preferences: {
      [propertyParent]: {
        ...(appState.preferences[propertyParent] || {}),
        [name]: value,
      },
    },
  });
  elements.propertyDialog.close();
  applyState(result.state);
  logMessage(`Added property: ${propertyParent}.${name}`);
}

async function saveTemplate() {
  const result = await request("save_template");
  logMessage(`Template saved: ${result.path}`);
  toast(`Saved ${result.path.split(/[\\/]/).pop()}`);
}

function registerEvents() {
  elements.openButton.addEventListener("click", chooseAndImport);
  elements.selectAllButton.addEventListener("click", selectAllOrClear);
  elements.invertButton.addEventListener("click", invertSelection);
  elements.reloadButton.addEventListener("click", reloadSources);
  elements.plotButton.addEventListener("click", plotSelected);
  elements.axisButton.addEventListener("click", toggleAxis);
  elements.outputButton.addEventListener("click", exportPlot);
  elements.templateButton.addEventListener("click", saveTemplate);
  elements.clearMessagesButton.addEventListener("click", () => {
    elements.messageLog.replaceChildren();
    messageTotal = 0;
    elements.messageCount.textContent = "0";
  });
  for (const tab of elements.tabs) {
    tab.addEventListener("click", () => setTab(tab.dataset.tab));
  }
  elements.contextMenu.addEventListener("click", (event) => {
    const action = event.target.closest("button")?.dataset.action;
    if (action) handleContextAction(action);
  });
  elements.curveApplyButton.addEventListener("click", applyCurveEdit);
  elements.propertyAddButton.addEventListener("click", addNestedProperty);
  document.addEventListener("click", (event) => {
    if (!event.target.closest("#contextMenu")) hideContextMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Delete" &&
      !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)
    ) {
      deleteSelected();
    }
  });

  window.addEventListener("dragenter", (event) => {
    event.preventDefault();
    dragDepth += 1;
    elements.dropOverlay.classList.remove("hidden");
  });
  window.addEventListener("dragover", (event) => event.preventDefault());
  window.addEventListener("dragleave", (event) => {
    event.preventDefault();
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) elements.dropOverlay.classList.add("hidden");
  });
  window.addEventListener("drop", async (event) => {
    event.preventDefault();
    dragDepth = 0;
    elements.dropOverlay.classList.add("hidden");
    const paths = [...event.dataTransfer.files]
      .map((file) => api.droppedFilePath(file))
      .filter(Boolean);
    await importFiles(paths);
  });

  api.onOpenFiles(importFiles);
  api.onMenuOpen(chooseAndImport);
  api.onMenuExport(exportPlot);
  api.onBackendLog((message) => logMessage(message));
}

async function initialize() {
  registerEvents();
  setBusy(true, "Starting Python backend…");
  try {
    const result = await request("initialize");
    applyState(result.state);
    for (const message of result.messages || []) logMessage(message);
    setBackendStatus("ready", "Backend ready");
    logMessage("HyperPlot Electron interface ready.");
  } catch {
    setBackendStatus("error", "Backend unavailable");
  } finally {
    setBusy(false);
  }
}

initialize();
