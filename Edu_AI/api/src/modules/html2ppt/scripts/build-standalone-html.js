#!/usr/bin/env node

const path = require('path');
const { buildStandaloneHtmlFromFragment } = require('../src/lib/build-standalone-html');
const { defaultThemeId } = require('../src/config');

function printUsage() {
  console.log(`Usage:
  node scripts/build-standalone-html.js <input-fragment> [output-html] [--title "Document Title"] [--theme-id heu_academic_elegant]

Examples:
  node scripts/build-standalone-html.js test-harness/402-1-fragment.html
  node scripts/build-standalone-html.js test-harness/402-1-fragment.html test-harness/402-1.html
  node scripts/build-standalone-html.js test-harness/402-1-fragment.html --title "全模态大模型汇报"
  node scripts/build-standalone-html.js test-harness/402-1-fragment.html --theme-id heu_academic_basic`);
}

function parseArgs(argv) {
  const positional = [];
  const options = {
    title: '',
    themeId: defaultThemeId,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') {
      options.help = true;
      continue;
    }
    if (arg === '--title') {
      options.title = argv[i + 1] || '';
      i += 1;
      continue;
    }
    if (arg.startsWith('--title=')) {
      options.title = arg.slice('--title='.length);
      continue;
    }
    if (arg === '--theme-id') {
      options.themeId = argv[i + 1] || options.themeId;
      i += 1;
      continue;
    }
    if (arg.startsWith('--theme-id=')) {
      options.themeId = arg.slice('--theme-id='.length) || options.themeId;
      continue;
    }
    positional.push(arg);
  }

  return { positional, options };
}

function main() {
  const { positional, options } = parseArgs(process.argv.slice(2));

  if (options.help || positional.length < 1) {
    printUsage();
    process.exit(options.help ? 0 : 1);
  }

  const inputPath = path.resolve(positional[0]);
  const outputPath = positional[1] ? path.resolve(positional[1]) : undefined;

  const result = buildStandaloneHtmlFromFragment({
    fragmentPath: inputPath,
    outputPath,
    title: options.title,
    themeId: options.themeId,
  });

  console.log(`Input fragment: ${result.fragmentPath}`);
  console.log(`Output HTML: ${result.outputPath}`);
  console.log(`Theme CSS: ${result.themeCssPath}`);
  console.log(`Document title: ${result.title}`);
}

try {
  main();
} catch (error) {
  console.error(`Build failed: ${error.message}`);
  process.exit(1);
}
