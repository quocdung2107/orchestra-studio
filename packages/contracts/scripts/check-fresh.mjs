// ADR-0003: fail when committed openapi.json is stale versus the backend code.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const tmp = join(mkdtempSync(join(tmpdir(), "orch-openapi-")), "openapi.json");
execFileSync("uv", ["run", "--project", "../../apps/backend", "python", "-m",
  "orchestra_backend.export_openapi", tmp], { stdio: "inherit", shell: process.platform === "win32" });
const fresh = readFileSync(tmp, "utf8");
const committed = readFileSync("openapi.json", "utf8").replace(/\r\n/g, "\n");
if (fresh !== committed) {
  console.error("openapi.json is stale. Run: pnpm contracts");
  process.exit(1);
}
console.log("openapi.json is up to date");
