// Copy the pipeline's output into <site>/data so the built site is complete (used by `npm run build:site`).
import fs from "node:fs";
import path from "node:path";
import { buildDir, siteDir } from "../vite.config.ts";

const from = buildDir();
const to = path.join(siteDir(), "data");
if (!fs.existsSync(path.join(from, "meta.json"))) {
  console.error(`No pipeline build found in ${from}. Run: cd pipeline && uv run python -m stepfree.build`);
  process.exit(1);
}
fs.rmSync(to, { recursive: true, force: true });
fs.cpSync(from, to, { recursive: true });
console.log(`copied ${from} -> ${to}`);
