"use strict";

const { app, BrowserWindow, dialog, ipcMain, Menu } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const readline = require("node:readline");
const { fileURLToPath } = require("node:url");

const PROJECT_ROOT = path.resolve(__dirname, "..");
const ICON_PATH = path.join(PROJECT_ROOT, "assets", "hyperplot.svg");
const SUPPORTED_FILE = /\.(csv|svg|png|hpt\.json|hptemplate)$/i;

app.setName("HyperPlot");
if (process.platform === "linux") {
  app.setDesktopName("hyperplot.desktop");
  app.commandLine.appendSwitch("class", "HyperPlot");
}

let mainWindow = null;
let backend = null;
let queuedOpenFiles = [];

class BackendClient {
  constructor() {
    this.nextId = 1;
    this.pending = new Map();
    this.ready = this.start();
  }

  start() {
    return new Promise((resolve, reject) => {
      const python = process.env.HYPERPLOT_PYTHON || "python3";
      const cacheDir = path.join(app.getPath("userData"), "matplotlib");
      fs.mkdirSync(cacheDir, { recursive: true });
      this.process = spawn(
        python,
        [path.join(__dirname, "backend.py"), "--stdio"],
        {
          cwd: PROJECT_ROOT,
          env: {
            ...process.env,
            MPLBACKEND: "Agg",
            MPLCONFIGDIR: cacheDir,
            PYTHONUNBUFFERED: "1",
          },
          stdio: ["pipe", "pipe", "pipe"],
        },
      );

      let settled = false;
      const lines = readline.createInterface({ input: this.process.stdout });
      lines.on("line", (line) => this.onLine(line));
      this.process.stderr.on("data", (chunk) => {
        const message = chunk.toString().trim();
        if (message && mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send("backend:log", message);
        }
      });
      this.process.once("spawn", () => {
        settled = true;
        resolve();
      });
      this.process.once("error", (error) => {
        if (!settled) reject(error);
        this.rejectAll(error);
      });
      this.process.once("exit", (code, signal) => {
        const detail = signal ? `signal ${signal}` : `code ${code}`;
        this.rejectAll(new Error(`HyperPlot backend stopped (${detail}).`));
      });
    });
  }

  onLine(line) {
    let response;
    try {
      response = JSON.parse(line);
    } catch {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send("backend:log", line);
      }
      return;
    }

    const pending = this.pending.get(response.id);
    if (!pending) return;
    this.pending.delete(response.id);
    if (response.ok) {
      pending.resolve(response);
    } else {
      const error = new Error(response.error || "Backend request failed.");
      error.traceback = response.traceback;
      pending.reject(error);
    }
  }

  rejectAll(error) {
    for (const pending of this.pending.values()) pending.reject(error);
    this.pending.clear();
  }

  async request(action, payload = {}) {
    await this.ready;
    if (!this.process || this.process.killed || !this.process.stdin.writable) {
      throw new Error("HyperPlot backend is not available.");
    }
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.process.stdin.write(`${JSON.stringify({ id, action, payload })}\n`);
    });
  }

  close() {
    if (!this.process || this.process.killed) return;
    this.process.stdin.end();
    setTimeout(() => {
      if (this.process && !this.process.killed) this.process.kill();
    }, 1200).unref();
  }
}

function filesFromArgv(argv) {
  return argv
    .map((arg) => {
      try {
        return arg.startsWith("file://") ? fileURLToPath(arg) : arg;
      } catch {
        return arg;
      }
    })
    .filter((arg) => SUPPORTED_FILE.test(arg))
    .map((arg) => path.resolve(arg))
    .filter((arg) => fs.existsSync(arg));
}

function deliverOpenFiles(files) {
  const unique = [...new Set(files)];
  if (!unique.length) return;
  if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.webContents.isLoading()) {
    mainWindow.webContents.send("files:open", unique);
  } else {
    queuedOpenFiles.push(...unique);
  }
}

function createApplicationMenu() {
  const template = [
    {
      label: "File",
      submenu: [
        {
          label: "Open Data…",
          accelerator: "CmdOrCtrl+O",
          click: () => mainWindow?.webContents.send("menu:open"),
        },
        {
          label: "Export Plot…",
          accelerator: "CmdOrCtrl+Shift+S",
          click: () => mainWindow?.webContents.send("menu:export"),
        },
        { type: "separator" },
        { role: "quit" },
      ],
    },
    {
      label: "Edit",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { role: "selectAll" },
      ],
    },
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { role: "toggleDevTools" },
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { role: "togglefullscreen" },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1040,
    minHeight: 660,
    title: "HyperPlot",
    icon: ICON_PATH,
    backgroundColor: "#f4f1eb",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));
  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.webContents.once("did-finish-load", () => {
    if (queuedOpenFiles.length) {
      const files = [...new Set(queuedOpenFiles)];
      queuedOpenFiles = [];
      mainWindow.webContents.send("files:open", files);
    }
  });
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function registerIpc() {
  ipcMain.handle("backend:request", async (_event, action, payload) => {
    return backend.request(action, payload);
  });

  ipcMain.handle("dialog:open-files", async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: "Import data or HyperPlot state",
      properties: ["openFile", "multiSelections"],
      filters: [
        {
          name: "HyperPlot files",
          extensions: ["csv", "svg", "png", "json", "hptemplate"],
        },
        { name: "All files", extensions: ["*"] },
      ],
    });
    return result.canceled ? [] : result.filePaths;
  });

  ipcMain.handle("dialog:save-plot", async (_event, suggestedName) => {
    const defaultName = suggestedName || "hyperplot.svg";
    const result = await dialog.showSaveDialog(mainWindow, {
      title: "Export plot",
      defaultPath: path.join(PROJECT_ROOT, "plots", defaultName),
      filters: [
        { name: "SVG image", extensions: ["svg"] },
        { name: "PNG image", extensions: ["png"] },
        { name: "PDF document", extensions: ["pdf"] },
        { name: "All files", extensions: ["*"] },
      ],
    });
    return result.canceled ? null : result.filePath;
  });

  ipcMain.handle("dialog:save-csv", async (_event, suggestedName) => {
    const result = await dialog.showSaveDialog(mainWindow, {
      title: "Export selected curves",
      defaultPath: path.join(
        PROJECT_ROOT,
        "plots",
        suggestedName || "selected_curves.csv",
      ),
      filters: [
        { name: "CSV data", extensions: ["csv"] },
        { name: "All files", extensions: ["*"] },
      ],
    });
    return result.canceled ? null : result.filePath;
  });
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", (_event, argv) => {
    deliverOpenFiles(filesFromArgv(argv));
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    backend = new BackendClient();
    registerIpc();
    createApplicationMenu();
    createWindow();
    deliverOpenFiles(filesFromArgv(process.argv.slice(1)));
    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
  });
  app.on("before-quit", () => backend?.close());
}
