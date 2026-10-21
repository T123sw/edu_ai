"""Opt-in real model/parser validation using isolated state and synthetic sources.
Run with Edu_AI's backend Python and PYTHONPATH=backend/src; credentials are read
through its normal resolver. No production job, document or exam is written.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--modes', nargs='+', choices=['custom', 'mimic'], default=['custom', 'mimic'])
    parser.add_argument('--retry-failed', action='store_true', help='Exercise one explicit task retry using the same private checkpoints')
    parser.add_argument('--paper-text', type=Path, help='Synthetic paper fixture, one rendered line per text line')
    parser.add_argument('--native-pdf-validation', action='store_true', help='Use pypdf for the synthetic text PDF only; does not validate MinerU/OCR')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    from app.exam_generation.schemas import CreateGeneration
    from app.exam_generation.snapshots import SnapshotCodec
    from app.exam_generation.sources import GenerationSources
    from app.exam_generation.repository import GenerationRepository
    from app.exam_generation.service import ExamGenerationHandler
    from app.integrations.deeptutor.client import DeepTutorClient, DeepTutorConfig
    from app.services.durable_task_handlers import DurableExecutionContext
    from app.database.models import AppStateRecord
    from sqlalchemy import create_engine
    import httpx
    root = Path(__file__).resolve().parents[1]
    token = secrets.token_urlsafe(40)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='edu-deeptutor-m2-') as temporary:
        work = Path(temporary)
        engine = create_engine('sqlite:///' + str(work / 'generations.db'), connect_args={'check_same_thread': False})
        AppStateRecord.__table__.create(engine)
        repo = GenerationRepository(engine)
        codec = SnapshotCodec()
        frozen = codec.capture('deeptutor-migration-validation')
        text = b'Quick sort chooses a pivot and partitions the sequence, then recursively sorts the partitions. Its average time complexity is O(n log n), while worst case is O(n squared). Merge sort divides the sequence and merges sorted halves. It is stable and uses O(n) auxiliary space.'
        # Produce a two-question PDF without a PDF-generation dependency.
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, NumberObject, DecodedStreamObject
        writer = PdfWriter()
        lines = ['Sorting practice paper', '1. Which statement about quick sort is correct?', 'A. It is always stable. B. It partitions around a pivot.', 'C. It always takes linear time. D. It needs a sorted input.', '2. Fill in the blank: Merge sort has worst-case time complexity ______.']
        if args.paper_text:
            lines = args.paper_text.read_text().splitlines()
        for start in range(0, len(lines), 30):
            page = writer.add_blank_page(width=595, height=842)
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
            content = DecodedStreamObject()
            escaped = [line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)') for line in lines[start:start+30]]
            content.set_data(('BT /F1 10 Tf 30 800 Td 24 TL ' + ' T* '.join('(' + line + ') Tj' for line in escaped) + ' ET').encode())
            page[NameObject('/Contents')] = writer._add_object(content)
        import io
        buffer = io.BytesIO()
        writer.write(buffer)
        paper = buffer.getvalue()
        (args.output / 'sample-paper.pdf').write_bytes(paper)
        (args.output / 'sample-context.txt').write_bytes(text)
        class Reader:
            def read_bytes(self, owner, document_id):
                if owner != 'deeptutor-migration-validation': raise PermissionError()
                return ({'filename': 'sorting.md'}, text) if document_id == 'context' else ({'filename': 'sample-paper.pdf'}, paper)
        native_factory = None
        if args.native_pdf_validation:
            from app.integrations.pdf.base import ParsedPdf
            from pypdf import PdfReader
            class NativeValidationParser:
                def parse(self, data, **kwargs):
                    pages = PdfReader(io.BytesIO(data)).pages
                    texts = [page.extract_text() for page in pages]
                    return ParsedPdf(text='\n'.join(texts), metadata={'parser': 'pypdf-validation-only',
                        'pageCount': len(pages), 'pageIndices': list(range(len(pages))),
                        'layout': [{'type': 'text', 'text': text, 'page_idx': i} for i, text in enumerate(texts)]})
            native_factory = lambda config: NativeValidationParser()
        sources = GenerationSources(reader=Reader(), parser_factory=native_factory)
        cfg = DeepTutorConfig(base_url=f'http://127.0.0.1:{port}', token=token, read_timeout=180)
        env = {**os.environ, 'DEEPTUTOR_HOME': str(work / 'runtime'), 'EDU_DEEPTUTOR_TOKEN': token}
        # Only the standalone service's environment selects its Python imports.
        env.pop('PYTHONPATH', None)
        log = (work / 'service.log').open('w')
        process = subprocess.Popen([str(root / '.venv/bin/python'), '-m', 'uvicorn', 'edu_deeptutor.api:create_app', '--factory', '--host', '127.0.0.1', '--port', str(port)], cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
        summary = {'model_boundary': 'live', 'pdf_parser': 'pypdf-validation-only' if args.native_pdf_validation else codec.read('deeptutor-migration-validation', frozen)['pdf_parser'].get('provider_id', 'mineru-cloud'), 'production_writes': False, 'cases': []}
        try:
            for _ in range(120):
                if process.poll() is not None: raise RuntimeError('Bridge exited during startup')
                try:
                    if httpx.get(cfg.base_url + '/health', timeout=1, trust_env=False).status_code == 200: break
                except httpx.HTTPError: pass
                time.sleep(0.25)
            else: raise RuntimeError('Bridge startup timed out')
            for mode, doc, role in [('custom', 'context', 'context'), ('mimic', 'paper', 'template')]:
                if mode not in args.modes:
                    continue
                payload = CreateGeneration(request_id=uuid4(), requirement='Generate a new sorting practice in English. Follow the supplied material. Use different values and wording from a template when supplied.', mode=mode, language='en',
                    num_questions=2, question_types=['choice', 'fill_in_blank'], per_type_counts={'choice': 1, 'fill_in_blank': 1}, sources=[{'document_id': doc, 'role': role}]).model_dump(mode='json')
                owner = 'deeptutor-migration-validation'
                row = repo.create(owner, payload, sources=sources.freeze(owner, payload['sources']), encrypted_snapshot=frozen)
                started = time.monotonic()
                ctx = DurableExecutionContext(task_id=row['id'], owner_user_id=owner, course_id=None, config_snapshot_id=None,
                    progress=lambda progress, stage, message: print(mode, stage, flush=True),
                    is_cancel_requested=lambda: time.monotonic() - started > 480, attempt_count=1, is_lease_valid=lambda: True)
                handler = ExamGenerationHandler(repo, sources, codec, lambda: DeepTutorClient(cfg))
                try:
                    result = handler({'generation_id': row['id']}, ctx)
                    stored = repo.get(owner, row['id'])
                    # These are synthetic task outputs; never include configuration or credentials.
                    (args.output / f'{mode}-result.json').write_text(json.dumps(stored['result'], ensure_ascii=False, indent=2) + '\n')
                    (args.output / f'{mode}-parsed.json').write_text(json.dumps(stored['parsed_sources'], ensure_ascii=False, indent=2) + '\n')
                    summary['cases'].append({'mode': mode, 'saved': result.get('saved'), 'seconds': round(time.monotonic()-started, 2),
                        'events': stored['last_seq'], 'result_ref': result.get('result_ref')})
                except Exception as exc:
                    stored = repo.get(owner, row['id'])
                    # Save diagnostic codes only; raw upstream errors may include request content.
                    summary['cases'].append({'mode': mode, 'saved': False, 'error_type': type(exc).__name__,
                        'error_code': getattr(exc, 'code', None), 'seconds': round(time.monotonic()-started, 2), 'events': stored['last_seq']})
                    (args.output / f'{mode}-diagnostic.json').write_text(json.dumps([
                        {'seq': e.get('seq'), 'type': e.get('type'), 'source': e.get('source'), 'stage': e.get('stage'),
                         'error_code': (e.get('metadata') or {}).get('error_code') or (e.get('metadata') or {}).get('code')}
                        for e in stored['events'] if e.get('type') in {'error', 'done'}], indent=2))
                    print(mode, 'failed:', type(exc).__name__, flush=True)
                    if stored.get('result'):
                        (args.output / f'{mode}-result.json').write_text(json.dumps(stored['result'], ensure_ascii=False, indent=2) + '\n')
                    # Local-only debug log, not an acceptance artifact.
                    (Path('/tmp') / f'deeptutor-m2-{mode}-debug.json').write_text(json.dumps(stored['events'], ensure_ascii=False))
                    if args.retry_failed and stored.get('result'):
                        from dataclasses import replace
                        retry_started = time.monotonic()
                        retry_context = replace(ctx, task_id='retry-' + row['id'])
                        try:
                            retried = handler({'generation_id': row['id']}, retry_context)
                            retry_id = retried['result_ref']['generation_id']
                            retry_row = repo.get(owner, retry_id)
                            (args.output / f'{mode}-retry-result.json').write_text(json.dumps(retry_row['result'], ensure_ascii=False, indent=2) + '\n')
                            summary['cases'].append({'mode': mode, 'attempt': 'explicit_retry', 'saved': True,
                                'seconds': round(time.monotonic()-retry_started, 2), 'events': retry_row['last_seq']})
                        except Exception as retry_exc:
                            from uuid import uuid5, NAMESPACE_URL
                            from app.exam_generation.repository import identifier
                            retry_id = identifier(owner, str(uuid5(NAMESPACE_URL, retry_context.task_id)))
                            retry_row = repo.get(owner, retry_id)
                            if retry_row.get('result'):
                                (args.output / f'{mode}-retry-result.json').write_text(json.dumps(retry_row['result'], ensure_ascii=False, indent=2) + '\n')
                            summary['cases'].append({'mode': mode, 'attempt': 'explicit_retry', 'saved': False,
                                'error_code': getattr(retry_exc, 'code', None), 'seconds': round(time.monotonic()-retry_started, 2)})
                (args.output / 'real-generation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
        finally:
            process.terminate()
            try: process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            log.close()
            # Keep local diagnostics outside tracked evidence, with restricted permissions.
            target = Path('/tmp/deeptutor-m2-service.log')
            target.write_bytes((work / 'service.log').read_bytes())
            target.chmod(0o600)
            engine.dispose()
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
