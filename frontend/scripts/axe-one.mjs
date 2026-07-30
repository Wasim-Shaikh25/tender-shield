#!/usr/bin/env node
/*
Run a single axe-core WCAG 2.1 AA audit against one server-rendered HTML file.
Intended to be spawned by axe-ci.mjs so that each route loads a fresh axe-core
instance bound to its own JSDOM window.
*/

import fs from "node:fs";
import { JSDOM } from "jsdom";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const file = process.argv[2];
if (!file) {
  console.error("Usage: node scripts/axe-one.mjs <path-to-html>");
  process.exit(1);
}

const html = fs.readFileSync(file, "utf8");
const dom = new JSDOM(html, { url: "http://localhost:3000" });
global.window = dom.window;
global.document = dom.window.document;

const axe = require("axe-core");
axe.configure({
  locale: "en",
  allowedOrigins: ["<unsafe_all>"],
});

const results = await axe.run(document.documentElement, {
  runOnly: {
    type: "tag",
    values: ["wcag21aa"],
  },
});

console.log(JSON.stringify({
  file,
  violations: results.violations.map(v => ({
    id: v.id,
    impact: v.impact,
    help: v.help,
    helpUrl: v.helpUrl,
  })),
}));
