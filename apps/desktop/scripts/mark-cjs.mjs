// dist-electron is compiled to CommonJS, but this package is "type": "module".
import { writeFileSync } from "node:fs";
writeFileSync(new URL("../dist-electron/package.json", import.meta.url), '{ "type": "commonjs" }\n');
