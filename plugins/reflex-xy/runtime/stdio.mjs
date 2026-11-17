import { fileURLToPath } from "node:url";

const asset = (path) => fileURLToPath(new URL(path, import.meta.url));
process.env.XY_RENDER_SCRIPT = asset("./render.py");
process.env.XY_SKILL_DIR = asset("../skills/reflex-xy/");
process.env.PYTHONIOENCODING = "utf-8";
process.env.PYTHONDONTWRITEBYTECODE = "1";

const server = new URL("../chatgpt/dist/server-bundled.js", import.meta.url);
process.argv = [process.execPath, fileURLToPath(server), "--stdio", "--desktop"];
await import(server.href);
