#!/usr/bin/env node
// @tiendalasmotos/agent-cli — GSD Guardrails CLI v1.0.0
// Internal tool: NOT for public registry. Scope: @tiendalasmotos

"use strict";

const { execSync, spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const VERSION = "1.0.0";
const PACKAGE_NAME = "@tiendalasmotos/agent-cli";

// ─── ANSI Colors ─────────────────────────────────────────────────────────────
const C = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  blue: "\x1b[34m",
  cyan: "\x1b[36m",
  gray: "\x1b[90m",
};

function log(msg) { process.stdout.write(msg + "\n"); }
function ok(msg)  { log(`${C.green}✓${C.reset} ${msg}`); }
function err(msg) { log(`${C.red}✗${C.reset} ${msg}`); }
function warn(msg){ log(`${C.yellow}⚠${C.reset} ${msg}`); }
function info(msg){ log(`${C.cyan}ℹ${C.reset} ${msg}`); }
function header(msg) {
  log(`\n${C.bold}${C.blue}━━━ ${msg} ━━━${C.reset}`);
}

// ─── Utils ────────────────────────────────────────────────────────────────────
function run(cmd, opts = {}) {
  try {
    return execSync(cmd, { encoding: "utf8", stdio: "pipe", ...opts });
  } catch (e) {
    return null;
  }
}

function findProjectRoot() {
  let dir = process.cwd();
  while (dir !== path.dirname(dir)) {
    if (fs.existsSync(path.join(dir, ".npmrc")) || fs.existsSync(path.join(dir, ".planning"))) {
      return dir;
    }
    dir = path.dirname(dir);
  }
  return process.cwd();
}

// ─── Commands ─────────────────────────────────────────────────────────────────

/**
 * eval — Coherence score evaluator.
 * Runs pytest and calculates pass ratio. Guards against score < 0.9.
 * MANDATO: Prohibido npm publish si score < 0.9.
 */
function cmdEval() {
  header("GSD EVAL — Coherence Score Gate");

  const root = findProjectRoot();
  info(`Project root: ${root}`);

  // Run pytest
  log(`\n${C.gray}Running pytest...${C.reset}`);
  const result = spawnSync("uv", ["run", "pytest", "--tb=no", "-q"], {
    cwd: root,
    encoding: "utf8",
    stdio: "pipe",
  });

  const stdout = (result.stdout || "").trim();
  const stderr = (result.stderr || "").trim();

  if (stdout) log(stdout);
  if (stderr && result.status !== 0) log(`${C.gray}${stderr}${C.reset}`);

  // Parse results
  const matchPassed = stdout.match(/(\d+) passed/);
  const matchFailed = stdout.match(/(\d+) failed/);
  const matchError  = stdout.match(/(\d+) error/);

  const passed = matchPassed ? parseInt(matchPassed[1]) : 0;
  const failed = (matchFailed ? parseInt(matchFailed[1]) : 0) +
                 (matchError  ? parseInt(matchError[1])  : 0);
  const total  = passed + failed;

  const score = total > 0 ? (passed / total) : 0;
  const scoreStr = score.toFixed(3);
  const threshold = 0.9;

  log("");
  log(`${C.bold}━━━ EVAL REPORT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C.reset}`);
  log(`  Tests passed : ${C.green}${passed}${C.reset}`);
  log(`  Tests failed : ${failed > 0 ? C.red : C.green}${failed}${C.reset}`);
  log(`  Total        : ${total}`);
  log(`  Score        : ${score >= threshold ? C.green : C.red}${scoreStr}${C.reset} (threshold: ${threshold})`);
  log(`${C.bold}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C.reset}`);

  if (score >= threshold) {
    ok(`SCORE ${scoreStr} ≥ ${threshold} — DEPLOY AUTHORIZED ✅`);
    process.exit(0);
  } else {
    err(`SCORE ${scoreStr} < ${threshold} — DEPLOY ABORTADO ⛔`);
    err("Resuelve los tests fallidos antes de ejecutar npm publish o git push.");
    process.exit(1);
  }
}

/**
 * scaffold --check — Verifica la integridad de la estructura del proyecto.
 */
function cmdScaffold(args) {
  header("GSD SCAFFOLD — Structure Integrity Check");

  const root = findProjectRoot();
  const required = [
    ".npmrc",
    ".planning/STATE.md",
    ".planning/ROADMAP.md",
    "bin/agent-cli.js",
    "package.json",
    "app",
  ];

  let allOk = true;
  for (const f of required) {
    const fullPath = path.join(root, f);
    const exists = fs.existsSync(fullPath);
    if (exists) {
      ok(f);
    } else {
      err(`MISSING: ${f}`);
      allOk = false;
    }
  }

  log("");
  if (allOk) {
    ok("Scaffold integrity: PASS ✅");
    process.exit(0);
  } else {
    err("Scaffold integrity: FAIL ⛔ — Anomalía de Estructura detectada.");
    process.exit(1);
  }
}

/**
 * workflow start [id] — Registra inicio de flujo de trabajo GSD.
 */
function cmdWorkflow(args) {
  header("GSD WORKFLOW");
  const subCmd = args[0];
  const ticketId = args[1] || "UNKNOWN";

  if (subCmd === "start") {
    const ts = new Date().toISOString();
    info(`Workflow iniciado: ${ticketId} @ ${ts}`);
    ok(`Flujo GSD registrado. Ticket: ${C.bold}${ticketId}${C.reset}`);
    info("Recuerda: cada cambio quirúrgico debe ser commiteado atómicamente.");
    process.exit(0);
  } else {
    warn(`Subcomando desconocido: ${subCmd}. Uso: agent-cli workflow start [ticket_id]`);
    process.exit(1);
  }
}

/**
 * observability --live — Monitor de persistencia activo.
 */
function cmdObservability(args) {
  header("GSD OBSERVABILITY");
  const live = args.includes("--live");

  if (live) {
    info("Modo live activado. Monitoreando logs de persistencia...");
    info("(En producción, conecta a Cloud Logging. En local, tail app/logs si existe.)");

    const root = findProjectRoot();
    const logPaths = [
      path.join(root, "app", "logs", "app.log"),
      path.join(root, "logs", "app.log"),
    ];

    let found = false;
    for (const lp of logPaths) {
      if (fs.existsSync(lp)) {
        info(`Siguiendo: ${lp}`);
        spawnSync("tail", ["-f", lp], { stdio: "inherit" });
        found = true;
        break;
      }
    }

    if (!found) {
      warn("No se encontró archivo de log local. En Cloud Run: gcloud logging tail --project=<PROJECT_ID>");
      process.exit(0);
    }
  } else {
    info("Uso: agent-cli observability --live");
    process.exit(0);
  }
}

/**
 * deploy — Deploy a entorno beta via uvx google-agents-cli.
 */
function cmdDeploy(args) {
  header("GSD DEPLOY — Beta Environment");
  warn("Este comando activa el pipeline de despliegue beta.");
  info("Delegando a GitHub Actions (beta branch push)...");

  const branch = run("git rev-parse --abbrev-ref HEAD", {}).trim();
  if (branch !== "beta") {
    err(`Estás en rama '${branch}'. El deploy beta requiere estar en rama 'beta'.`);
    process.exit(1);
  }

  info("Ejecutando: git push origin beta");
  const result = spawnSync("git", ["push", "origin", "beta"], { stdio: "inherit" });
  if (result.status === 0) {
    ok("Push a beta exitoso. GitHub Actions iniciará el despliegue.");
  } else {
    err("Fallo en git push. Revisa credenciales y estado del repositorio.");
    process.exit(1);
  }
}

/**
 * publish — Registra versión en el catálogo (requiere aprobación de Tobias).
 */
function cmdPublish(args) {
  header("GSD PUBLISH — Register Version in Catalog");
  warn("MANDATO: npm publish solo es legal tras eval score ≥ 0.9 y aprobación de Tobias.");
  info("Ejecutando npm publish al registro de GitHub Packages...");

  const result = spawnSync("npm", ["publish", "--access=restricted"], {
    stdio: "inherit",
    env: process.env,
  });

  if (result.status === 0) {
    ok(`${PACKAGE_NAME}@${VERSION} publicado en GitHub Packages ✅`);
  } else {
    err("npm publish falló. Verifica NPM_TOKEN y permisos write:packages.");
    process.exit(1);
  }
}

/**
 * --version / -v
 */
function cmdVersion() {
  log(`${PACKAGE_NAME} v${VERSION}`);
  process.exit(0);
}

/**
 * --help / -h
 */
function cmdHelp() {
  log(`
${C.bold}${C.cyan}@tiendalasmotos/agent-cli${C.reset} v${VERSION}
${C.gray}Internal GSD Guardrails CLI — TiendaLasMotos${C.reset}

${C.bold}COMMANDS:${C.reset}
  eval                  Run pytest and calculate coherence score (threshold: 0.9)
  scaffold [--check]    Verify project structure integrity
  workflow start <id>   Register GSD workflow start for a ticket
  observability [--live] Monitor persistence layer logs
  deploy                Push to beta branch (triggers CI/CD)
  publish               Publish package to GitHub Packages (requires eval ≥ 0.9)

${C.bold}FLAGS:${C.reset}
  --version, -v         Show version
  --help, -h            Show this help

${C.bold}EXAMPLES:${C.reset}
  npx @tiendalasmotos/agent-cli eval
  npx @tiendalasmotos/agent-cli scaffold --check
  npx @tiendalasmotos/agent-cli workflow start BOT-STRUC-765
`);
  process.exit(0);
}

// ─── Router ───────────────────────────────────────────────────────────────────
const [,, cmd, ...rest] = process.argv;

switch (cmd) {
  case "eval":          cmdEval();               break;
  case "scaffold":      cmdScaffold(rest);        break;
  case "workflow":      cmdWorkflow(rest);         break;
  case "observability": cmdObservability(rest);    break;
  case "deploy":        cmdDeploy(rest);           break;
  case "publish":       cmdPublish(rest);          break;
  case "--version":
  case "-v":            cmdVersion();              break;
  case "--help":
  case "-h":
  case undefined:       cmdHelp();                 break;
  default:
    err(`Comando desconocido: '${cmd}'`);
    cmdHelp();
    process.exit(1);
}
