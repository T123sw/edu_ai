const test = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');

const {
  buildGeometryWarnings,
  inspectHtmlLayout,
} = require('../src/lib/layout-geometry-inspector');

test('geometry warning builder reports key container overflow', () => {
  const report = buildGeometryWarnings({
    slide_count: 1,
    results: [
      {
        slide_index: 1,
        title: 'Overflow',
        issues: [
          {
            code: 'KEY_CONTAINER_OVERFLOW',
            selector: '.content-area',
            scrollHeight: 720,
            clientHeight: 620,
          },
        ],
      },
    ],
  });

  assert.equal(report.warning_count, 1);
  assert.equal(report.warnings[0].code, 'KEY_CONTAINER_OVERFLOW');
  assert.match(report.warnings[0].message, /content-area/);
});

test('html layout inspector parses dumped JSON report from chrome stdout', async () => {
  const chrome = new EventEmitter();
  chrome.stdout = new EventEmitter();
  chrome.stderr = new EventEmitter();
  chrome.kill = () => true;

  const resultPromise = inspectHtmlLayout('/tmp/demo.html', {
    chromePathOverride: process.execPath,
    timeoutMs: 50,
    spawnChrome: () => {
      setImmediate(() => {
        chrome.stdout.emit(
          'data',
          '<html><body><script type="application/json" id="layout-quality-json">{"slide_count":1,"results":[]}</script></body></html>'
        );
        chrome.emit('close', 0, null);
      });
      return chrome;
    },
  });

  const report = await resultPromise;
  assert.equal(report.slide_count, 1);
  assert.equal(report.warning_count, 0);
});
