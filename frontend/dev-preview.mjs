import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
process.chdir(__dirname);

const { createServer } = await import("vite");
const server = await createServer({ configFile: "./vite.config.js", server: { port: 5174, strictPort: true } });
await server.listen();
server.printUrls();
