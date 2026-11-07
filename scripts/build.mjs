import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";

const candidates = process.platform === "win32"
  ? [
      { command: ".venv\\Scripts\\python.exe", prefix: [] },
      { command: "python", prefix: [] },
      { command: "py", prefix: ["-3"] },
    ]
  : [
      { command: ".venv/bin/python", prefix: [] },
      { command: "python3", prefix: [] },
      { command: "python", prefix: [] },
    ];

function available(candidate) {
  if (candidate.command.startsWith(".venv") && !existsSync(candidate.command)) {
    return false;
  }
  const result = spawnSync(
    candidate.command,
    [...candidate.prefix, "--version"],
    { stdio: "ignore" },
  );
  return result.status === 0;
}

const python = candidates.find(available);
if (!python) {
  throw new Error("Python 3 is required to build the Flask application.");
}

function runPython(args) {
  const result = spawnSync(
    python.command,
    [...python.prefix, ...args],
    { stdio: "inherit" },
  );
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

runPython(["-m", "compileall", "-q", "app", "run.py"]);
runPython([
  "-c",
  [
    "from dotenv import load_dotenv",
    "load_dotenv()",
    "from run import app",
    "assert app.config['SQLALCHEMY_DATABASE_URI']",
    "print('Flask entrypoint import: ok')",
  ].join("; "),
]);
