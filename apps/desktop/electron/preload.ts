// Narrow, read-only bridge (SECURITY.md §3). No IPC, no Node APIs for the renderer.
import { contextBridge } from "electron";

contextBridge.exposeInMainWorld("orchestra", Object.freeze({ shell: "electron" as const }));
