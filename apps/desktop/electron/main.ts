/**
 * Electron main process (P0 G1, ADR-0001, ADR-0009).
 *
 * - Starts the Python backend on 127.0.0.1 with a fresh per-launch token.
 * - Injects the token only into requests to that backend; the renderer never sees it.
 * - Renderer: contextIsolation + sandbox, no Node, no new windows, no navigation away.
 * - No IPC channels are exposed in P0 (nothing to validate, nothing to abuse).
 */
import { type ChildProcess, spawn, spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { join, resolve } from "node:path";
import { BrowserWindow, app, dialog, session, shell } from "electron";

const REPO_ROOT = resolve(__dirname, "../../..");
const BACKEND_DIR = join(REPO_ROOT, "apps", "backend");
const RENDERER_DIR = resolve(__dirname, "../dist/renderer");
const PORT = Number(process.env.ORCHESTRA_PORT ?? 8765);
const BACKEND_ORIGIN = `http://127.0.0.1:${PORT}`;
const TOKEN = randomBytes(32).toString("base64url");
const devUrlArg = process.argv.find((a) => a.startsWith("--dev-url="));
const DEV_URL = devUrlArg ? devUrlArg.slice("--dev-url=".length) : null;

let backend: ChildProcess | null = null;

function startBackend(): ChildProcess {
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    ORCHESTRA_TOKEN: TOKEN,
    ORCHESTRA_PORT: String(PORT),
    ORCHESTRA_DATA_DIR: join(REPO_ROOT, "data"),
  };
  if (!DEV_URL) env.ORCHESTRA_STATIC_DIR = RENDERER_DIR;
  // P0: run from source via uv. Packaging Python for installers is deferred (P0_PLAN).
  const child = spawn("uv", ["run", "--project", BACKEND_DIR, "orchestra-backend"], {
    env,
    cwd: REPO_ROOT,
    windowsHide: true,
    stdio: ["ignore", "inherit", "inherit"],
  });
  child.on("exit", (code) => {
    if (backend === child && !app.isReady()) return;
    if (backend === child && code !== 0 && code !== null) {
      dialog.showErrorBox("Orchestra Studio", `Backend dừng bất thường (mã ${code}).`);
    }
  });
  return child;
}

function stopBackend(): void {
  const child = backend;
  backend = null;
  if (!child?.pid || child.exitCode !== null) return;
  if (process.platform === "win32") {
    // uv starts python as a child; kill the whole tree.
    spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { windowsHide: true });
  } else {
    child.kill("SIGTERM");
  }
}

async function waitForBackend(timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (backend?.exitCode !== null && backend?.exitCode !== undefined) {
      throw new Error(`backend exited with code ${backend.exitCode}`);
    }
    try {
      const res = await fetch(`${BACKEND_ORIGIN}/api/v1/health`);
      if (res.ok) return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("backend did not become healthy in time");
}

function hardenSession(): void {
  const ses = session.defaultSession;
  ses.webRequest.onBeforeSendHeaders({ urls: [`${BACKEND_ORIGIN}/*`] }, (details, callback) => {
    callback({ requestHeaders: { ...details.requestHeaders, "x-orchestra-token": TOKEN } });
  });
  ses.setPermissionRequestHandler((_wc, _permission, callback) => callback(false));
}

function createWindow(): void {
  const appUrl = DEV_URL ?? `${BACKEND_ORIGIN}/`;
  const allowedOrigin = new URL(appUrl).origin;
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    title: "Orchestra Studio",
    backgroundColor: "#020617",
    webPreferences: {
      preload: join(__dirname, "preload.js"),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      webSecurity: true,
    },
  });
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("https://")) void shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, url) => {
    if (new URL(url).origin !== allowedOrigin) event.preventDefault();
  });
  void win.loadURL(appUrl);
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.whenReady().then(async () => {
    hardenSession();
    backend = startBackend();
    try {
      await waitForBackend(120_000); // first run may install Python deps via uv
    } catch (err) {
      dialog.showErrorBox(
        "Orchestra Studio",
        `Không khởi động được backend: ${(err as Error).message}\nKiểm tra đã cài uv và chạy được "pnpm backend".`,
      );
      stopBackend();
      app.quit();
      return;
    }
    createWindow();
  });

  app.on("window-all-closed", () => app.quit());
  app.on("before-quit", stopBackend);
  process.on("exit", stopBackend);
}
