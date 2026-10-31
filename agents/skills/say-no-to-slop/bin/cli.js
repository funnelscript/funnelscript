#!/usr/bin/env node

/**
 * Avoid AI Writing — Universal Agentic CLI
 * Fast, deterministic detector, preservation validator, and multi-agent router.
 */

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

const AIDetector = require(path.join(rootDir, 'detector', 'patterns.js'));
const AIDetectorValidate = require(path.join(rootDir, 'detector', 'validate.js'));
const pkg = JSON.parse(fs.readFileSync(path.join(rootDir, 'package.json'), 'utf8'));

// ANSI colors
const useColor = !process.env.NO_COLOR && process.stdout.isTTY;
const colors = {
  reset: useColor ? '\x1b[0m' : '',
  bold: useColor ? '\x1b[1m' : '',
  dim: useColor ? '\x1b[2m' : '',
  red: useColor ? '\x1b[31m' : '',
  green: useColor ? '\x1b[32m' : '',
  yellow: useColor ? '\x1b[33m' : '',
  blue: useColor ? '\x1b[34m' : '',
  magenta: useColor ? '\x1b[35m' : '',
  cyan: useColor ? '\x1b[36m' : '',
  bgRed: useColor ? '\x1b[41m\x1b[37m' : '',
  bgGreen: useColor ? '\x1b[42m\x1b[30m' : '',
  bgYellow: useColor ? '\x1b[43m\x1b[30m' : '',
};

function printBanner() {
  console.log(`${colors.bold}${colors.red}🛑 Say No to Slop!${colors.reset} ${colors.dim}v${pkg.version}${colors.reset} — Universal Multi-Agent AI Writing Sentinel\n`);
}

function printHelp() {
  printBanner();
  console.log(`${colors.bold}USAGE:${colors.reset}
  say-no-to-slop <command> [options] [arguments]
  bunx say-no-to-slop <command> [options]
  npx say-no-to-slop <command> [options]
  (aliases: prosewarden, avoid-ai-writing)

${colors.bold}COMMANDS:${colors.reset}
  ${colors.green}detect${colors.reset} <file|text> [--json]       Audit prose for AI patterns, buzzwords, and stylometrics
  ${colors.green}verify${colors.reset} <original> <rewritten>     Verify zero-regression preservation of code, tables, math, & links
  ${colors.green}route${colors.reset}  "<prompt>" [--json]          Route intent through the 7-node multi-agent orchestration DAG
  ${colors.green}scan${colors.reset}   <file>                      Run deep self-scan check
  ${colors.green}install${colors.reset}                            Install across Claude Code, Gemini CLI, Codex, Cursor, & Agent Kernel

${colors.bold}OPTIONS:${colors.reset}
  --json                             Output results in JSON format
  -h, --help                         Show this help message
  -v, --version                      Show version number

${colors.bold}EXAMPLES:${colors.reset}
  # Audit a string
  avoid-ai-writing detect "Acme is nestled in Boulder, offering a game-changing testament to innovation."

  # Audit a Markdown file
  avoid-ai-writing detect ./README.md

  # Verify preservation between draft and rewrite
  avoid-ai-writing verify original.md revised.md

  # Route a user prompt through the multi-agent graph
  avoid-ai-writing route "Audit this technical guide and fix AI buzzwords without touching code blocks"

  # Install into all detected agent harnesses
  avoid-ai-writing install
`);
}

const args = process.argv.slice(2);

if (args.length === 0 || args.includes('-h') || args.includes('--help')) {
  printHelp();
  process.exit(0);
}

if (args.includes('-v') || args.includes('--version')) {
  console.log(`avoid-ai-writing v${pkg.version}`);
  process.exit(0);
}

const command = args[0];
const subArgs = args.slice(1);
const isJson = subArgs.includes('--json');
const filteredArgs = subArgs.filter(a => a !== '--json');

switch (command) {
  case 'detect': {
    if (filteredArgs.length === 0) {
      console.error(`${colors.red}Error: Missing input text or file path to detect.${colors.reset}`);
      console.error('Usage: avoid-ai-writing detect <file|text> [--json]');
      process.exit(1);
    }

    const inputArg = filteredArgs.join(' ');
    let text = inputArg;
    let sourcePath = null;

    if (fs.existsSync(inputArg) && fs.statSync(inputArg).isFile()) {
      sourcePath = inputArg;
      text = fs.readFileSync(inputArg, 'utf8');
    }

    const result = AIDetector.analyzeText(text);

    if (isJson) {
      console.log(JSON.stringify({ source: sourcePath, ...result }, null, 2));
      process.exit(0);
    }

    printBanner();
    if (sourcePath) {
      console.log(`${colors.dim}Target File:${colors.reset} ${colors.bold}${sourcePath}${colors.reset}`);
    }

    const score = result.score;
    let badge = `${colors.bgGreen} CLEAN ${colors.reset}`;
    if (score > 40) {
      badge = `${colors.bgRed} HEAVY AI SIGNALS ${colors.reset}`;
    } else if (score > 15) {
      badge = `${colors.bgYellow} MODERATE AI SIGNALS ${colors.reset}`;
    } else if (score > 5) {
      badge = `${colors.yellow}[Minimal AI signals]${colors.reset}`;
    }

    console.log(`\n${colors.bold}Score:${colors.reset} ${colors.bold}${score}/100${colors.reset}  ${badge}`);
    console.log(`${colors.bold}Classification:${colors.reset} ${result.document_classification} (${result.label})`);
    console.log(`${colors.bold}Confidence:${colors.reset} ${result.confidence_category}`);
    console.log(`${colors.dim}Words: ${result.stats.wordCount} | Tier 1 Hits: ${result.stats.tier1Count} | Pattern Hits: ${result.stats.patternCount}${colors.reset}\n`);

    if (result.issues.length === 0) {
      console.log(`${colors.green}✓ No AI writing tells or boilerplate patterns detected.${colors.reset}\n`);
    } else {
      console.log(`${colors.bold}Detected Patterns (${result.issues.length}):${colors.reset}`);
      const grouped = {};
      for (const issue of result.issues) {
        const key = issue.type;
        if (!grouped[key]) grouped[key] = [];
        grouped[key].push(issue);
      }

      for (const [type, list] of Object.entries(grouped)) {
        console.log(`\n  ${colors.magenta}▸ ${type.toUpperCase()}${colors.reset} (${list.length} hits):`);
        for (const item of list.slice(0, 10)) {
          const sevColor = item.severity === 'critical' ? colors.red : item.severity === 'high' ? colors.yellow : colors.dim;
          console.log(`    • "${colors.bold}${item.text}${colors.reset}" [${sevColor}${item.severity}${colors.reset}]${item.suggestion ? ` → Suggestion: ${colors.green}${item.suggestion}${colors.reset}` : ''}`);
        }
        if (list.length > 10) {
          console.log(`    ${colors.dim}... and ${list.length - 10} more${colors.reset}`);
        }
      }
      console.log('');
    }
    process.exit(score > 30 ? 1 : 0);
  }

  case 'verify': {
    if (filteredArgs.length < 2) {
      console.error(`${colors.red}Error: Missing arguments for verify.${colors.reset}`);
      console.error('Usage: avoid-ai-writing verify <original-file> <rewritten-file> [--json]');
      process.exit(1);
    }

    const [origPath, newPath] = filteredArgs;
    if (!fs.existsSync(origPath)) {
      console.error(`${colors.red}Error: Original file not found at ${origPath}${colors.reset}`);
      process.exit(1);
    }
    if (!fs.existsSync(newPath)) {
      console.error(`${colors.red}Error: Rewritten file not found at ${newPath}${colors.reset}`);
      process.exit(1);
    }

    const origContent = fs.readFileSync(origPath, 'utf8');
    const newContent = fs.readFileSync(newPath, 'utf8');
    const result = AIDetectorValidate.validate(origContent, newContent);

    if (isJson) {
      console.log(JSON.stringify(result, null, 2));
      process.exit(result.ok ? 0 : 1);
    }

    printBanner();
    console.log(`${colors.bold}Preservation Verification Audit${colors.reset}`);
    console.log(`  Original:  ${origPath}`);
    console.log(`  Rewritten: ${newPath}\n`);

    if (result.ok) {
      console.log(`${colors.bgGreen} PASS ${colors.reset} ${colors.green}All structural elements preserved intact!${colors.reset}`);
      console.log(`  ✓ Code fences: preserved`);
      console.log(`  ✓ Tables: preserved`);
      console.log(`  ✓ LaTeX / math: preserved`);
      console.log(`  ✓ Markdown links: preserved`);
      console.log(`  ✓ Headings / structure: preserved\n`);
      process.exit(0);
    } else {
      console.log(`${colors.bgRed} FAIL ${colors.reset} ${colors.red}${result.errors.length} preservation violation(s) detected:${colors.reset}\n`);
      for (const err of result.errors) {
        console.log(`  ${colors.red}✖ [${err.code}]${colors.reset} ${err.message}`);
      }
      if (result.warnings && result.warnings.length > 0) {
        console.log(`\n${colors.yellow}Warnings (${result.warnings.length}):${colors.reset}`);
        for (const warn of result.warnings) {
          console.log(`  ${colors.yellow}⚠ [${warn.code}]${colors.reset} ${warn.message}`);
        }
      }
      console.log('');
      process.exit(1);
    }
  }

  case 'route': {
    const prompt = filteredArgs.join(' ');
    if (!prompt) {
      console.error(`${colors.red}Error: Missing prompt to route.${colors.reset}`);
      console.error('Usage: avoid-ai-writing route "<prompt>" [--json]');
      process.exit(1);
    }

    const pLower = prompt.toLowerCase();
    const hasAuditOnly = /\b(detect|audit|check|scan|find|highlight|measure|score)\b/.test(pLower) && !/\b(rewrite|fix|edit|replace|clean|humanize)\b/.test(pLower);
    const hasNamedFile = /\b(file|path|\.md|\.txt|\.doc|in-place|mutate)\b/.test(pLower);
    const hasConsequence = /\b(cheat|cheating|misconduct|plagiarism|fraud|consequence|grade|hire|fire|sanction)\b/.test(pLower);
    const hasRepresentation = /\b(character|person|face|ethnicity|appearance|photo|portrait|avatar)\b/.test(pLower);

    const steps = [];
    steps.push({
      step: 1,
      skill: 'ai-writing-detector',
      role: 'Deterministic Signal Extraction',
      description: 'Collect raw pattern counts, stylometric entropy, and tier 1-3 hits'
    });

    if (hasConsequence) {
      steps.push({
        step: 2,
        skill: 'false-positive-reviewer',
        role: 'Authorship Uncertainty Guardrail',
        description: 'Enforce ethical non-consequentiality and check for technical jargon false-positives'
      });
    }

    if (!hasAuditOnly) {
      if (hasNamedFile) {
        steps.push({
          step: steps.length + 1,
          skill: 'file-edit-in-place',
          role: 'Surgical Mutation',
          description: 'Apply targeted diffs to file preserving non-prose blocks'
        });
      } else {
        steps.push({
          step: steps.length + 1,
          skill: 'voice-preserving-rewriter',
          role: 'Voice-Preserving Rewrite',
          description: 'Reconstruct prose eliminating AI rhythm while preserving authorial voice'
        });
      }

      steps.push({
        step: steps.length + 1,
        skill: 'preservation-verifier',
        role: 'Zero-Regression Gate',
        description: 'Verify code fences, tables, LaTeX math, and links remain bitwise-intact'
      });
    }

    const routingPlan = {
      prompt,
      orchestrator: 'avoid-ai-writing-router',
      dag_version: '2',
      inferred_intent: hasAuditOnly ? 'detect_only' : hasNamedFile ? 'mutate_named_file' : 'rewrite_returned_text',
      active_guards: [
        ...(hasRepresentation ? ['human_representation_preservation'] : []),
        ...(hasConsequence ? ['authorship_uncertainty'] : []),
        'loop_bound_max_cycles:1'
      ],
      execution_flow: steps
    };

    if (isJson) {
      console.log(JSON.stringify(routingPlan, null, 2));
      process.exit(0);
    }

    printBanner();
    console.log(`${colors.bold}Agentic Intent Routing Analysis${colors.reset}`);
    console.log(`${colors.dim}Prompt:${colors.reset} "${prompt}"\n`);
    console.log(`${colors.bold}Inferred Intent:${colors.reset} ${colors.cyan}${routingPlan.inferred_intent}${colors.reset}`);
    console.log(`${colors.bold}Active Guards:${colors.reset}   ${routingPlan.active_guards.join(', ') || 'none'}\n`);
    console.log(`${colors.bold}Recommended Execution Flow:${colors.reset}`);
    for (const s of steps) {
      console.log(`  ${colors.green}[Step ${s.step}]${colors.reset} ${colors.bold}${s.skill}${colors.reset} (${s.role})`);
      console.log(`          ${colors.dim}${s.description}${colors.reset}`);
    }
    console.log('');
    process.exit(0);
  }

  case 'scan': {
    const scanTarget = filteredArgs[0];
    const scriptPath = path.join(rootDir, 'scripts', 'self-scan.js');
    const scanArgs = scanTarget ? [scriptPath, scanTarget] : [scriptPath];
    const res = spawnSync('node', scanArgs, { stdio: 'inherit' });
    process.exit(res.status ?? 0);
  }

  case 'install': {
    const installScript = path.join(rootDir, 'install.sh');
    const res = spawnSync('bash', [installScript], { stdio: 'inherit' });
    process.exit(res.status ?? 0);
  }

  default: {
    console.error(`${colors.red}Unknown command: ${command}${colors.reset}`);
    printHelp();
    process.exit(1);
  }
}
