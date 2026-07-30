#!/usr/bin/env node
/*
Static WCAG 2.1 AA assessment for the Next.js app-router build output.
Spawns scripts/axe-one.mjs for each server-rendered .html file so that every
route is audited by a fresh axe-core instance bound to its own JSDOM window.
Exits with a non-zero code if any critical or serious violations remain.
*/

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const appDir = path.join(root, ".next", "server", "app");

if (!fs.existsSync(appDir)) {
  console.error("Build output not found. Run `npm run build` first.");
  process.exit(1);
}

const htmlFiles = [];
function walk(dir) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) {
      walk(p);
    } else if (ent.name.endsWith(".html")) {
      htmlFiles.push(p);
    }
  }
}
walk(appDir);

if (htmlFiles.length === 0) {
  console.error("No server-rendered HTML files found in .next/server/app.");
  process.exit(1);
}

function audit(file) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(__dirname, "axe-one.mjs"), file], {
      cwd: root,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => (stdout += d.toString()));
    child.stderr.on("data", (d) => (stderr += d.toString()));
    child.on("close", (code) => {
      if (code !== 0) {
        return reject(new Error(`axe-one.mjs exited ${code}: ${stderr || stdout}`));
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (e) {
        reject(new Error(`Failed to parse axe output: ${stdout}\n${stderr}`));
      }
    });
  });
}

let totalViolations = 0;
for (const file of htmlFiles) {
  const result = await audit(file);
  const route = path.relative(appDir, result.file).replace(/\\/g, "/");
  const serious = result.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious",
  );
  totalViolations += serious.length;

  for (const v of result.violations) {
    const prefix = v.impact === "critical" || v.impact === "serious" ? "FAIL" : "WARN";
    console.log(`${prefix} [${route}] ${v.id} (${v.impact}): ${v.help}`);
  }
}

if (totalViolations > 0) {
  console.error(`
Accessibility check failed: ${totalViolations} critical/serious WCAG 2.1 AA violation(s).
`);
  process.exit(1);
}

console.log(`
Accessibility check passed: ${htmlFiles.length} route(s) audited against WCAG 2.1 AA.`);
