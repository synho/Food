#!/usr/bin/env node
/**
 * monitor.js — live colorful terminal dashboard for KG expansion
 *
 * Usage:
 *   node monitor.js           # refresh every 10s
 *   node monitor.js --once    # print once and exit
 *   node monitor.js --interval 5
 */
import { execSync, spawnSync } from "child_process";
import { existsSync, readdirSync, readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import chalk from "chalk";

const __dir = dirname(fileURLToPath(import.meta.url));

// ── Args ─────────────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const once = args.includes("--once");
const intervalIdx = args.indexOf("--interval");
const INTERVAL_S = intervalIdx >= 0 ? parseInt(args[intervalIdx + 1], 10) : 10;

// ── Paths ─────────────────────────────────────────────────────────────────────
const DATA       = resolve(__dir, "data");
const RAW_DIR    = resolve(DATA, "raw_papers");
const EXT_DIR    = resolve(DATA, "extracted_triples");
const LOGS_DIR   = resolve(__dir, "logs");
const DB_PATH    = resolve(__dir, "..", "data", "health_map.db");
const VENV_PY    = resolve(__dir, "venv", "bin", "python");

// ── Helpers ──────────────────────────────────────────────────────────────────
const run = (cmd) => {
  try { return execSync(cmd, { encoding: "utf8", stdio: ["pipe","pipe","pipe"] }).trim(); }
  catch { return ""; }
};

const countDir = (dir) => {
  try { return readdirSync(dir).length; } catch { return 0; }
};

const countDirGlob = (dir, suffix) => {
  try { return readdirSync(dir).filter(f => f.endsWith(suffix)).length; } catch { return 0; }
};

const fmtNum = (n) => typeof n === "number" ? n.toLocaleString() : n;
const fmtElapsed = (secs) => {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = Math.round(secs % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
};

// ── Data fetchers ─────────────────────────────────────────────────────────────
function getProcesses() {
  const WATCHED = ["run_expansion", "run_overnight", "watch_kg", "run_pipeline",
                   "fetch_papers", "extract_triples", "smart_fetch", "ingest_to_neo4j",
                   "consolidate_graph", "entity_resolver"];
  const out = run("ps -eo pid,ppid,etime,%cpu,%mem,command");
  const procs = [];
  for (const line of out.split("\n")) {
    for (const name of WATCHED) {
      if (line.includes(name) && !line.includes("grep") && !line.includes("monitor.js")) {
        const parts = line.trim().split(/\s+/);
        procs.push({
          pid: parts[0], ppid: parts[1],
          elapsed: parts[2], cpu: parts[3], mem: parts[4],
          name,
        });
        break;
      }
    }
  }
  return procs;
}

function getCycles() {
  try {
    const logs = readdirSync(LOGS_DIR)
      .filter(f => f.startsWith("expansion_cycles_") && f.endsWith(".log"))
      .sort().reverse();
    if (!logs.length) return { startedAt: null, cycles: [] };

    const text = readFileSync(resolve(LOGS_DIR, logs[0]), "utf8");
    const startMatch = text.match(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\[START\]/);
    const cycles = [];
    for (const line of text.split("\n")) {
      const m = line.match(/\[CYCLE\s+(\d+)\]\s+papers \+(\d+)\s+nodes \+(\d+)\s+rels \+(\d+)\s+total=(\d+) nodes \/ (\d+) rels/);
      if (m) {
        const ts = line.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/);
        cycles.push({
          cycle: +m[1], papers: +m[2], nodesDelta: +m[3], relsDelta: +m[4],
          totalNodes: +m[5], totalRels: +m[6],
          time: ts ? ts[1].split(" ")[1] : "",
        });
      }
    }
    return { startedAt: startMatch ? startMatch[1] : null, cycles };
  } catch { return { startedAt: null, cycles: [] }; }
}

function getNeo4j() {
  const out = run(`${VENV_PY} -c "
from neo4j import GraphDatabase
d = GraphDatabase.driver('bolt://localhost:7687', auth=('foodnot4self','foodnot4self'))
with d.session() as s:
    n = s.run('MATCH (n) RETURN count(n) AS c').single()['c']
    r = s.run('MATCH ()-[r]->() RETURN count(r) AS c').single()['c']
    src = s.run('MATCH ()-[r]->() RETURN count(DISTINCT r.source_id) AS c').single()['c']
    rows = s.run('MATCH (n) WITH labels(n)[0] AS l RETURN l, count(*) AS c ORDER BY c DESC LIMIT 6').data()
    print(f'{n}|{r}|{src}')
    for row in rows: print(f'  {row[\\"l\\"]}:{row[\\"c\\"]}')
d.close()
" 2>/dev/null`);
  if (!out) return null;
  const lines = out.split("\n");
  const [nodes, rels, sources] = lines[0].split("|").map(Number);
  const byLabel = {};
  for (const l of lines.slice(1)) {
    const [k, v] = l.trim().split(":");
    if (k && v) byLabel[k] = +v;
  }
  return { nodes, rels, sources, byLabel };
}

function getSnapshots() {
  try {
    const out = run(`${VENV_PY} -c "
import sqlite3, json
c = sqlite3.connect('${DB_PATH}')
rows = c.execute('SELECT recorded_at, total_nodes, total_relationships FROM kg_stats ORDER BY id DESC LIMIT 8').fetchall()
for r in rows: print(f'{r[0][:19]}|{r[1]}|{r[2]}')
c.close()
" 2>/dev/null`);
    return out.split("\n").filter(Boolean).map(l => {
      const [date, nodes, rels] = l.split("|");
      return { date, nodes: +nodes, rels: +rels };
    }).reverse();
  } catch { return []; }
}

// ── Rendering ─────────────────────────────────────────────────────────────────
function bar(filled, total, width = 30) {
  const pct = Math.min(1, total > 0 ? filled / total : 0);
  const n = Math.round(pct * width);
  const filled_str = "█".repeat(n);
  const empty_str  = "░".repeat(width - n);
  const pctLabel   = `${Math.round(pct * 100)}%`;
  return chalk.green(filled_str) + chalk.gray(empty_str) + " " + chalk.bold(pctLabel);
}

function miniSparkline(vals, width = 20) {
  if (vals.length < 2) return chalk.gray("—");
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const chars = " ▁▂▃▄▅▆▇█";
  const pts = vals.slice(-width).map(v => chars[Math.round(((v - min) / range) * 8)]);
  return chalk.cyan(pts.join(""));
}

function renderDashboard() {
  const procs    = getProcesses();
  const raw      = countDir(RAW_DIR);
  const ext      = countDirGlob(EXT_DIR, "_triples.json");
  const backlog  = Math.max(0, raw - ext);
  const neo4j    = getNeo4j();
  const { startedAt, cycles } = getCycles();
  const snaps    = getSnapshots();

  const isActive = procs.some(p => ["run_expansion","run_overnight","watch_kg"].includes(p.name));
  const now      = new Date();

  let elapsedStr = "—";
  if (startedAt) {
    const started = new Date(startedAt);
    elapsedStr = fmtElapsed((now - started) / 1000);
  }

  const W = 72;
  const line  = chalk.gray("─".repeat(W));
  const dline = chalk.gray("═".repeat(W));

  const lines = [];

  // ── Header ────────────────────────────────────────────────────────────────
  lines.push("");
  lines.push(dline);
  lines.push(
    chalk.bold.cyan("  KG EXPANSION MONITOR") +
    "  " + chalk.gray(now.toLocaleTimeString()) +
    (isActive
      ? "  " + chalk.bgGreen.black(" ACTIVE ") + chalk.green(` ${elapsedStr} elapsed`)
      : "  " + chalk.bgGray.white(" IDLE "))
  );
  lines.push(dline);

  // ── Processes ─────────────────────────────────────────────────────────────
  lines.push("");
  lines.push(chalk.bold("  PROCESSES"));
  lines.push(line);
  if (!procs.length) {
    lines.push(chalk.gray("  No expansion processes running."));
  } else {
    const ICONS = {
      run_expansion: "▶", run_overnight: "▶", watch_kg: "↻",
      run_pipeline: "⟳", fetch_papers: "↓", extract_triples: "⚗",
      smart_fetch: "⎯", ingest_to_neo4j: "⬆", consolidate_graph: "⊞",
      entity_resolver: "⊛",
    };
    const COLORS = {
      run_expansion: chalk.yellow, run_overnight: chalk.yellow,
      watch_kg: chalk.cyan, run_pipeline: chalk.white,
      fetch_papers: chalk.magenta, extract_triples: chalk.blue,
      smart_fetch: chalk.magenta, ingest_to_neo4j: chalk.green,
      consolidate_graph: chalk.yellow, entity_resolver: chalk.green,
    };
    // Sort by PID so parent → child order
    procs.sort((a, b) => +a.pid - +b.pid);
    for (const p of procs) {
      const col    = COLORS[p.name] ?? chalk.white;
      const icon   = ICONS[p.name] ?? "●";
      const isFetch  = p.name === "fetch_papers" || p.name === "smart_fetch";
      const isExt    = p.name === "extract_triples";
      const pulse    = (isFetch || isExt) ? chalk.bold(" ← active") : "";
      lines.push(
        "  " + col(`${icon} ${p.name.padEnd(20)}`) +
        chalk.gray(`pid=${p.pid.padEnd(6)} cpu=${p.cpu.padStart(4)}%  ${p.elapsed.padStart(8)}`) +
        pulse
      );
    }
  }

  // ── Corpus ────────────────────────────────────────────────────────────────
  lines.push("");
  lines.push(chalk.bold("  CORPUS"));
  lines.push(line);
  lines.push(
    "  " + chalk.cyan("Raw papers") + "   " + chalk.bold.white(fmtNum(raw)) +
    "   " + chalk.cyan("Extracted") + " " + chalk.bold.white(fmtNum(ext)) +
    "   " + (backlog > 0 ? chalk.yellow(`${fmtNum(backlog)} queued`) : chalk.green("fully extracted"))
  );
  lines.push("  " + bar(ext, raw, 40));

  // ── Cycles ────────────────────────────────────────────────────────────────
  lines.push("");
  lines.push(chalk.bold("  EXPANSION CYCLES  ") + chalk.gray(`(${cycles.length} completed)`));
  lines.push(line);
  if (!cycles.length) {
    lines.push(chalk.gray("  Cycle 1 in progress — no completed cycles yet."));
  } else {
    const totPapers = cycles.reduce((s, c) => s + c.papers, 0);
    const totNodes  = cycles.reduce((s, c) => s + c.nodesDelta, 0);
    const totRels   = cycles.reduce((s, c) => s + c.relsDelta, 0);
    lines.push(
      "  Total: " +
      chalk.yellow(`+${fmtNum(totPapers)} papers`) + "  " +
      chalk.blue(`+${fmtNum(totNodes)} nodes`) + "  " +
      chalk.green(`+${fmtNum(totRels)} rels`)
    );
    lines.push("");
    // Show last 6 cycles
    for (const c of cycles.slice(-6).reverse()) {
      const hasPapers = c.papers > 0;
      const hasNodes  = c.nodesDelta > 0;
      const dot = (hasPapers || hasNodes)
        ? chalk.green("●") : chalk.gray("○");
      lines.push(
        "  " + dot + " " +
        chalk.gray(`#${String(c.cycle).padStart(2)}`) + "  " +
        chalk.gray(c.time) + "  " +
        (hasPapers ? chalk.yellow(`+${c.papers} papers`) : chalk.gray("+0 papers")) + "  " +
        (hasNodes  ? chalk.blue(`+${c.nodesDelta} nodes`) : chalk.gray("+0 nodes")) + "  " +
        (c.relsDelta > 0 ? chalk.green(`+${c.relsDelta} rels`) : chalk.gray("+0 rels"))
      );
    }
  }

  // ── Neo4j ─────────────────────────────────────────────────────────────────
  lines.push("");
  lines.push(chalk.bold("  NEO4J KNOWLEDGE GRAPH"));
  lines.push(line);
  if (!neo4j) {
    lines.push(chalk.red("  ✗ Neo4j unreachable"));
  } else {
    lines.push(
      "  " + chalk.cyan("Nodes") + "         " + chalk.bold.blue(fmtNum(neo4j.nodes)) +
      "   " + chalk.cyan("Rels") + "    " + chalk.bold.green(fmtNum(neo4j.rels)) +
      "   " + chalk.cyan("Sources") + " " + chalk.bold.white(fmtNum(neo4j.sources))
    );
    lines.push("");
    for (const [label, count] of Object.entries(neo4j.byLabel)) {
      const b = bar(count, neo4j.nodes, 18);
      lines.push(`  ${chalk.bold(label.padEnd(20))} ${chalk.white(fmtNum(count).padStart(6))}  ${b}`);
    }
  }

  // ── KG Trend ──────────────────────────────────────────────────────────────
  if (snaps.length >= 2) {
    lines.push("");
    lines.push(chalk.bold("  KG GROWTH TREND  ") + miniSparkline(snaps.map(s => s.nodes)));
    lines.push(line);
    for (const s of snaps.slice(-6)) {
      const dateStr = s.date.replace("T", " ").slice(5, 16);
      lines.push(
        "  " + chalk.gray(dateStr) + "  " +
        chalk.blue(`nodes ${fmtNum(s.nodes).padStart(7)}`) + "  " +
        chalk.green(`rels ${fmtNum(s.rels).padStart(7)}`)
      );
    }
  }

  // ── Footer ────────────────────────────────────────────────────────────────
  lines.push("");
  lines.push(dline);
  lines.push(
    chalk.gray(`  Refresh every ${INTERVAL_S}s  ·  Ctrl+C to exit  ·  `) +
    chalk.cyan("http://localhost:3000/kg")
  );
  lines.push("");

  return lines.join("\n");
}

// ── Main loop ─────────────────────────────────────────────────────────────────
function render() {
  process.stdout.write("\x1B[2J\x1B[0f"); // clear screen
  process.stdout.write(renderDashboard());
}

render();
if (!once) {
  setInterval(render, INTERVAL_S * 1000);
}
