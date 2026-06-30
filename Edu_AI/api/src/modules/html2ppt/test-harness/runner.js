function getExportFileName() {
  const configuredName = document.body.dataset.pptxFileName || 'dom-to-pptx-test.pptx';
  return configuredName.endsWith('.pptx') ? configuredName : `${configuredName}.pptx`;
}

function setStatus(message) {
  const statusEl = document.getElementById('status');
  if (statusEl) {
    statusEl.textContent = message;
  }
}

async function saveBlob(blob, fileName) {
  const response = await fetch(`/save-pptx?name=${encodeURIComponent(fileName)}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    },
    body: blob,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Save failed: ${response.status} ${text}`);
  }

  return response.json();
}

async function runExport() {
  const fileName = getExportFileName();

  try {
    setStatus('Running export...');
    const slides = Array.from(document.querySelectorAll('.slide'));
    const blob = await window.domToPptx.exportToPptx(slides, {
      fileName,
      skipDownload: true,
      svgAsVector: true,
      autoEmbedFonts: false,
    });

    setStatus(`Export finished. Blob size: ${blob.size} bytes. Saving to server...`);
    const result = await saveBlob(blob, fileName);
    setStatus(`Saved ${result.bytes} bytes to ${result.outputFile}`);
    window.__EXPORT_DONE__ = result;
  } catch (error) {
    setStatus(`Export failed: ${error.message}`);
    window.__EXPORT_ERROR__ = String(error && error.stack ? error.stack : error);
    console.error(error);
  }
}

window.addEventListener('load', () => {
  window.setTimeout(runExport, 300);
});
