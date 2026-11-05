// The electron npm package no longer downloads its binary on install, so do it here.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";

const require = createRequire(import.meta.url);
const pkgDir = dirname(require.resolve("electron/package.json"));
const pathFile = join(pkgDir, "path.txt");
if (existsSync(pathFile) && existsSync(join(pkgDir, "dist"))) {
  console.log("electron binary present");
} else {
  execFileSync(process.execPath, [join(pkgDir, "install.js")], { stdio: "inherit" });
}
