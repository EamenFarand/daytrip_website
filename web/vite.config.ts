import fs from "node:fs";
import path from "node:path";
import { defineConfig, type Plugin } from "vite";

const ROOT = path.resolve(import.meta.dirname, "..");

/** A setting from the environment or the repo's git-ignored .env file. */
function envValue(key: string): string | undefined {
  if (process.env[key]) return process.env[key];
  const envFile = path.join(ROOT, ".env");
  if (!fs.existsSync(envFile)) return undefined;
  for (const line of fs.readFileSync(envFile, "utf-8").split(/\r?\n/)) {
    const [k, ...rest] = line.split("=");
    if (k.trim() === key && rest.join("=").trim()) return rest.join("=").trim();
  }
  return undefined;
}

/** The pipeline's output folder: STEPFREE_BUILD, else ../data/build. */
export function buildDir(): string {
  return path.resolve(envValue("STEPFREE_BUILD") ?? path.join(ROOT, "data", "build"));
}

/** Where `vite build` writes the site: STEPFREE_SITE (locally outside Nextcloud), else web/dist. */
export function siteDir(): string {
  return path.resolve(envValue("STEPFREE_SITE") ?? path.join(import.meta.dirname, "dist"));
}

/** Serve /data/* from the pipeline's output during `vite dev` and `vite preview`. */
function serveBuildData(): Plugin {
  const dir = buildDir();
  const handler = (req: { url?: string }, res: import("node:http").ServerResponse, next: () => void) => {
    const rel = decodeURIComponent((req.url ?? "").split("?")[0]).replace(/^\/+/, "");
    const file = path.resolve(dir, rel);
    if (!file.startsWith(dir)) return next();
    if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.statusCode = 404; // a missing data file is a 404, not the app page
      return res.end();
    }
    res.setHeader("Content-Type", file.endsWith(".json") ? "application/json; charset=utf-8" : "application/octet-stream");
    fs.createReadStream(file).pipe(res);
  };
  // /api/lifts is a Cloudflare function in production; locally it serves STEPFREE_LIFTS (a file), or 404
  const lifts = (_req: unknown, res: import("node:http").ServerResponse) => {
    const file = envValue("STEPFREE_LIFTS");
    if (!file || !fs.existsSync(file)) {
      res.statusCode = 404;
      return res.end();
    }
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    fs.createReadStream(file).pipe(res);
  };
  return {
    name: "serve-build-data",
    configureServer(server) {
      server.middlewares.use("/data", handler);
      server.middlewares.use("/api/lifts", lifts);
    },
    configurePreviewServer(server) {
      server.middlewares.use("/data", handler);
      server.middlewares.use("/api/lifts", lifts);
    },
  };
}

export default defineConfig({
  plugins: [serveBuildData()],
  // The map chunk is MapLibre itself (about 1 MB, 280 KB compressed), loaded after the page; don't warn about it.
  build: { target: "es2022", outDir: siteDir(), emptyOutDir: true, chunkSizeWarningLimit: 1100 },
  worker: { format: "es" },
});
