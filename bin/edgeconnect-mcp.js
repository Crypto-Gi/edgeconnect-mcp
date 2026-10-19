#!/usr/bin/env node
// Runs the bundled Python server (stdlib only, Python 3.9+) so `npx github:Crypto-Gi/edgeconnect-mcp` works.
"use strict";
const { spawnSync } = require("child_process");
const path = require("path");

const src = path.join(__dirname, "..", "src");
const env = { ...process.env, PYTHONPATH: [src, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) };
const check = "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)";

for (const python of process.env.EDGECONNECT_PYTHON ? [process.env.EDGECONNECT_PYTHON] : ["python3", "python"]) {
  if (spawnSync(python, ["-c", check], { stdio: "ignore" }).status !== 0) continue;
  const run = spawnSync(python, ["-m", "edgeconnect_mcp", ...process.argv.slice(2)], { stdio: "inherit", env });
  process.exit(run.status === null ? 1 : run.status);
}
console.error("edgeconnect-mcp: needs Python 3.9 or later on PATH (or set EDGECONNECT_PYTHON)");
process.exit(1);
