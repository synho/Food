/**
 * render_html.mjs — generates /tmp/monitor_rich.html with full chalk colors as inline CSS spans
 */
import { execSync } from "child_process";
import { readdirSync, readFileSync, writeFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dir = dirname(fileURLToPath(import.meta.url));
const DATA     = resolve(__dir, "data");
const RAW_DIR  = resolve(DATA, "raw_papers");
const EXT_DIR  = resolve(DATA, "extracted_triples");
const LOGS_DIR = resolve(__dir, "logs");
const DB_PATH  = resolve(__dir, "..", "data", "health_map.db");
const VENV_PY  = resolve(__dir, "venv", "bin", "python");

// ── Color helpers (inline HTML spans) ────────────────────────────────────────
const c = {
  cyan:    (s) => `<span style="color:#58d7f7">${s}</span>`,
  green:   (s) => `<span style="color:#3fb950">${s}</span>`,
  yellow:  (s) => `<span style="color:#e3b341">${s}</span>`,
  blue:    (s) => `<span style="color:#79c0ff">${s}</span>`,
  magenta: (s) => `<span style="color:#d2a8ff">${s}</span>`,
  red:     (s) => `<span style="color:#f85149">${s}</span>`,
  gray:    (s) => `<span style="color:#484f58">${s}</span>`,
  white:   (s) => `<span style="color:#e6edf3">${s}</span>`,
  bold:    (s) => `<b>${s}</b>`,
  badge_green: (s) => `<span style="background:#2ea043;color:#0d1117;padding:2px 7px;border-radius:4px;font-weight:700">${s}</span>`,
  badge_gray:  (s) => `<span style="background:#21262d;color:#8b949e;padding:2px 7px;border-radius:4px">${s}</span>`,
};

// ── Helpers ───────────────────────────────────────────────────────────────────
const run = (cmd) => {
  try { return execSync(cmd, { encoding: "utf8", stdio: ["pipe","pipe","pipe"] }).trim(); }
  catch { return ""; }
};
const fmt     = (n) => typeof n === "number" ? n.toLocaleString() : String(n ?? "—");
const countDir  = (d) => { try { return readdirSync(d).length; } catch { return 0; } };
const countGlob = (d, s) => { try { return readdirSync(d).filter(f => f.endsWith(s)).length; } catch { return 0; } };

// ── Data ──────────────────────────────────────────────────────────────────────
// Processes
const WATCHED = ["run_expansion","run_overnight","watch_kg","run_pipeline",
                 "fetch_papers","extract_triples","smart_fetch","ingest_to_neo4j",
                 "consolidate_graph","entity_resolver"];
const ICONS = {
  run_expansion:"▶", run_overnight:"▶", watch_kg:"↻", run_pipeline:"⟳",
  fetch_papers:"↓", extract_triples:"⚗", smart_fetch:"⎯", ingest_to_neo4j:"⬆",
  consolidate_graph:"⊞", entity_resolver:"⊛",
};
const PROC_COLORS = {
  run_expansion:c.yellow, run_overnight:c.yellow, watch_kg:c.cyan, run_pipeline:c.white,
  fetch_papers:c.magenta, extract_triples:c.blue, smart_fetch:c.magenta,
  ingest_to_neo4j:c.green, consolidate_graph:c.yellow, entity_resolver:c.green,
};

const psOut = run("ps -eo pid,ppid,etime,%cpu,command");
const procs = [];
for (const line of psOut.split("\n")) {
  for (const name of WATCHED) {
    if (line.includes(name) && !line.includes("grep") && !line.includes("monitor") && !line.includes("render_html")) {
      const p = line.trim().split(/\s+/);
      procs.push({ pid: p[0], ppid: p[1], elapsed: p[2], cpu: p[3], name });
      break;
    }
  }
}
procs.sort((a, b) => +a.pid - +b.pid);
const isActive = procs.some(p => ["run_expansion","run_overnight","watch_kg"].includes(p.name));

// Corpus
const raw     = countDir(RAW_DIR);
const ext     = countGlob(EXT_DIR, "_triples.json");
const backlog = Math.max(0, raw - ext);

// Cycles
const cycleLogs = readdirSync(LOGS_DIR)
  .filter(f => f.startsWith("expansion_cycles_") && f.endsWith(".log"))
  .sort().reverse();
let startedAt = null, cycles = [];
if (cycleLogs.length) {
  const text = readFileSync(resolve(LOGS_DIR, cycleLogs[0]), "utf8");
  const sm = text.match(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\[START\]/);
  if (sm) startedAt = new Date(sm[1]);
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
}
let elapsedStr = "—";
if (startedAt) {
  const s = (Date.now() - startedAt) / 1000;
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.round(s % 60);
  elapsedStr = h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

// Neo4j — write query to temp file to avoid shell escaping issues
import { writeFileSync as _wf } from "fs";
const NEO_SCRIPT = "/tmp/_kg_neo_query.py";
_wf(NEO_SCRIPT, `from neo4j import GraphDatabase
d = GraphDatabase.driver('bolt://localhost:7687', auth=('foodnot4self','foodnot4self'))
with d.session() as s:
    n  = s.run('MATCH (n) RETURN count(n) AS c').single()['c']
    r  = s.run('MATCH ()-[r]->() RETURN count(r) AS c').single()['c']
    sr = s.run('MATCH ()-[r]->() RETURN count(DISTINCT r.source_id) AS c').single()['c']
    rows = s.run('MATCH (n) WITH labels(n)[0] AS l RETURN l, count(*) AS c ORDER BY c DESC LIMIT 8').data()
    print(f'{n}|{r}|{sr}')
    for row in rows: print(f"{row['l']}:{row['c']}")
d.close()
`);
const neoOut = run(`${VENV_PY} ${NEO_SCRIPT} 2>/dev/null`);
const neoLines = neoOut.split("\n");
const [nNodes, nRels, nSrcs] = neoLines[0].split("|").map(Number);
const byLabel = {};
for (const l of neoLines.slice(1)) {
  const idx = l.lastIndexOf(":");
  if (idx > 0) byLabel[l.slice(0, idx).trim()] = +l.slice(idx + 1).trim();
}

// Snapshots
const SNAP_SCRIPT = "/tmp/_kg_snap_query.py";
_wf(SNAP_SCRIPT, `import sqlite3
c = sqlite3.connect('${DB_PATH}')
rows = c.execute('SELECT recorded_at, total_nodes, total_relationships FROM kg_stats ORDER BY id DESC LIMIT 6').fetchall()
for r in rows: print(f'{r[0][:19]}|{r[1]}|{r[2]}')
c.close()
`);
const snaps = run(`${VENV_PY} ${SNAP_SCRIPT} 2>/dev/null`)
  .split("\n").filter(Boolean)
  .map(l => { const [d, n, r] = l.split("|"); return { date: d, nodes: +n, rels: +r }; })
  .reverse();

// ── Render ────────────────────────────────────────────────────────────────────
const W = 70;
const hr  = c.gray("─".repeat(W));
const dhr = `<span style="color:#30363d">${"═".repeat(W)}</span>`;

const bar = (filled, total, width = 34) => {
  const pct = Math.min(1, total > 0 ? filled / total : 0);
  const n = Math.round(pct * width);
  return c.green("█".repeat(n)) + c.gray("░".repeat(width - n)) +
    " " + c.bold(c.white(Math.round(pct * 100) + "%"));
};

const rows = [""];

// Header
rows.push(dhr);
rows.push(
  c.bold(c.cyan("  KG EXPANSION MONITOR")) + "  " +
  c.gray(new Date().toLocaleTimeString()) + "  " +
  (isActive
    ? c.badge_green(" ACTIVE ") + " " + c.green(c.bold(elapsedStr) + " elapsed")
    : c.badge_gray(" IDLE "))
);
rows.push(dhr);

// Processes
rows.push("");
rows.push(c.bold("  PROCESSES"));
rows.push(hr);
if (!procs.length) {
  rows.push(c.gray("  No expansion processes running."));
} else {
  for (const p of procs) {
    const col   = PROC_COLORS[p.name] ?? c.white;
    const icon  = ICONS[p.name] ?? "●";
    const pulse = (p.name === "extract_triples" || p.name === "fetch_papers" || p.name === "smart_fetch")
      ? "  " + c.bold(c.green("← active")) : "";
    rows.push(
      "  " + col(`${icon} ${p.name.padEnd(22)}`) +
      c.gray(`pid=${p.pid.padEnd(6)} cpu=${p.cpu.padStart(5)}%  ${p.elapsed.padStart(9)}`) +
      pulse
    );
  }
}

// Corpus
rows.push("");
rows.push(c.bold("  CORPUS"));
rows.push(hr);
rows.push(
  "  " + c.cyan("Raw papers") + "  " + c.bold(c.white(fmt(raw))) +
  "     " + c.cyan("Extracted") + " " + c.bold(c.white(fmt(ext))) +
  "     " + (backlog > 0 ? c.yellow(`${fmt(backlog)} queued`) : c.green("✓ fully extracted"))
);
rows.push("  " + bar(ext, raw, 42));

// Cycles
rows.push("");
rows.push(c.bold("  EXPANSION CYCLES") + "  " + c.gray(`(${cycles.length} completed)`));
rows.push(hr);
if (!cycles.length) {
  rows.push(c.gray("  Cycle 1 in progress — no completed cycles yet."));
} else {
  const tP = cycles.reduce((s, x) => s + x.papers, 0);
  const tN = cycles.reduce((s, x) => s + x.nodesDelta, 0);
  const tR = cycles.reduce((s, x) => s + x.relsDelta, 0);
  rows.push("  Total this run: " +
    c.yellow(`+${fmt(tP)} papers`) + "  " +
    c.blue(`+${fmt(tN)} nodes`) + "  " +
    c.green(`+${fmt(tR)} rels`));
  rows.push("");
  for (const x of cycles.slice(-6).reverse()) {
    const dot = (x.papers > 0 || x.nodesDelta > 0) ? c.green("●") : c.gray("○");
    rows.push(
      "  " + dot + " " + c.gray(`#${String(x.cycle).padStart(2)}`) + "  " +
      c.gray(x.time) + "  " +
      (x.papers > 0    ? c.yellow(`+${x.papers} papers`)      : c.gray("+0 papers")) + "  " +
      (x.nodesDelta > 0 ? c.blue(`+${x.nodesDelta} nodes`)    : c.gray("+0 nodes")) + "  " +
      (x.relsDelta > 0  ? c.green(`+${x.relsDelta} rels`)     : c.gray("+0 rels"))
    );
  }
}

// Neo4j
rows.push("");
rows.push(c.bold("  NEO4J KNOWLEDGE GRAPH"));
rows.push(hr);
rows.push(
  "  " + c.cyan("Nodes") + "         " + c.bold(c.blue(fmt(nNodes))) +
  "   " + c.cyan("Relationships") + " " + c.bold(c.green(fmt(nRels))) +
  "   " + c.cyan("Sources") + " " + c.bold(c.white(fmt(nSrcs)))
);
rows.push("");
for (const [label, count] of Object.entries(byLabel)) {
  rows.push(
    "  " + c.bold(label.padEnd(24)) +
    c.white(fmt(count).padStart(6)) + "  " +
    bar(count, nNodes, 20)
  );
}

// Trend
if (snaps.length >= 2) {
  rows.push("");
  rows.push(c.bold("  KG GROWTH TREND"));
  rows.push(hr);
  for (const s of snaps) {
    const d = s.date.replace("T", " ").slice(0, 16);
    rows.push(
      "  " + c.gray(d) + "   " +
      c.blue("nodes " + fmt(s.nodes).padStart(7)) + "   " +
      c.green("rels  " + fmt(s.rels).padStart(7))
    );
  }
}

rows.push("");
rows.push(dhr);
rows.push(
  c.gray("  Refresh every 10s  ·  Ctrl+C to stop  ·  ") +
  c.cyan("http://localhost:3000/kg")
);
rows.push("");

const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>KG Monitor</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #0d1117;
    padding: 28px 36px;
    font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
    font-size: 13.5px;
    line-height: 1.65;
    color: #c9d1d9;
  }
  pre { white-space: pre-wrap; }
</style></head>
<body><pre>${rows.join("\n")}</pre></body></html>`;

writeFileSync("/tmp/monitor_rich.html", html);
console.log("Written to /tmp/monitor_rich.html");
