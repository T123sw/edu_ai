import {
  exportClassroomVideo,
  parseVideoExportArguments,
} from './videoPipeline.ts';

async function main(): Promise<void> {
  const options = parseVideoExportArguments(process.argv.slice(2));
  const result = await exportClassroomVideo({
    ...options,
    onProgress: (event) => {
      process.stdout.write(
        `${JSON.stringify({ type: 'progress', ...event })}\n`,
      );
    },
  });
  process.stdout.write(`${JSON.stringify({ type: 'result', ...result })}\n`);
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`${JSON.stringify({ type: 'error', message })}\n`);
  process.exitCode = 1;
});
