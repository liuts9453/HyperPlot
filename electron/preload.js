"use strict";

const { contextBridge, ipcRenderer, webUtils } = require("electron");

contextBridge.exposeInMainWorld("hyperplot", {
  request: (action, payload = {}) =>
    ipcRenderer.invoke("backend:request", action, payload),
  chooseFiles: () => ipcRenderer.invoke("dialog:open-files"),
  choosePlotOutput: (suggestedName) =>
    ipcRenderer.invoke("dialog:save-plot", suggestedName),
  chooseCsvOutput: (suggestedName) =>
    ipcRenderer.invoke("dialog:save-csv", suggestedName),
  droppedFilePath: (file) => webUtils.getPathForFile(file),
  onOpenFiles: (callback) =>
    ipcRenderer.on("files:open", (_event, files) => callback(files)),
  onMenuOpen: (callback) =>
    ipcRenderer.on("menu:open", () => callback()),
  onMenuExport: (callback) =>
    ipcRenderer.on("menu:export", () => callback()),
  onBackendLog: (callback) =>
    ipcRenderer.on("backend:log", (_event, message) => callback(message)),
});
