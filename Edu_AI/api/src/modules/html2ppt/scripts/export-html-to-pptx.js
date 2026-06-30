#!/usr/bin/env node

const path = require('path');
const { exportHtmlToPptx } = require('../src/lib/export-html-to-pptx');

function printUsage() {
  console.log(`Usage:
  node scripts/export-html-to-pptx.js <html-file> [output-pptx]

Example:
  node scripts/export-html-to-pptx.js test-harness/gpt5.4.html
  node scripts/export-html-to-pptx.js test-harness/gpt5.4.html /tmp/gpt5.4.pptx`);
}

async function main() {
  const input = process.argv[2];
  if (!input || input === '--help' || input === '-h') {
    printUsage();
    process.exit(input ? 0 : 1);
  }

  const htmlPath = path.resolve(input);
  const outputPath = process.argv[3]
    ? path.resolve(process.argv[3])
    : path.join(path.dirname(htmlPath), `${path.basename(htmlPath, path.extname(htmlPath))}.pptx`);

  const result = await exportHtmlToPptx({
    htmlPath,
    outputPath,
    jobWorkspace: path.dirname(htmlPath),
  });

  console.log(`Prepared: ${result.preparation.htmlFilePath}`);
  if (result.preparation.changed) {
    console.log('Patched HTML: yes');
    console.log(`Changes: ${result.preparation.changes.join('; ')}`);
  } else {
    console.log('Patched HTML: no changes needed');
  }
  console.log(`Export URL: ${result.pageUrl}`);
  console.log(`Output PPTX: ${result.outputFile}`);
  console.log(`Output size: ${result.outputSize} bytes`);
}

main().catch((error) => {
  console.error(`Export failed: ${error.message}`);
  process.exit(1);
});
