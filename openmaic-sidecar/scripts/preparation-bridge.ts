/** JSONL subprocess protocol. stdout is reserved; upstream diagnostics use stderr. */
import { createInterface } from 'node:readline';
import { existsSync } from 'node:fs';
import { loadEnvFile } from 'node:process';

const output = process.stdout.write.bind(process.stdout);
console.log = console.info = console.debug = (...args) => console.error(...args);
const lines = createInterface({ input: process.stdin, crlfDelay: Infinity })[
  Symbol.asyncIterator
]();
const emit = (value: unknown) => output(JSON.stringify(value) + '\n');
async function receive() {
  const next = await lines.next();
  if (next.done) throw new Error('Bridge input closed');
  return JSON.parse(next.value);
}
async function main() {
  for (const filename of ['.env.local', '.env']) if (existsSync(filename)) loadEnvFile(filename);
  const { generatePreparationClassroom } = await import('../lib/server/preparation-generation');
  const input = await receive();
  const { getServerImageProviders, getServerVideoProviders } =
    await import('../lib/server/provider-config');
  const imagePrice = Number(input.mediaPrices?.image ?? 0);
  const videoPrice = Number(input.mediaPrices?.video ?? 0);
  const { resolveImageApiKey, resolveVideoApiKey } = await import('../lib/server/provider-config');
  const { IMAGE_PROVIDERS } = await import('../lib/media/image-providers');
  const imageId = Object.keys(getServerImageProviders())[0];
  const videoId = Object.keys(getServerVideoProviders())[0];
  input.enableImages = Boolean(
    imageId &&
    imagePrice > 0 &&
    (!IMAGE_PROVIDERS[imageId as keyof typeof IMAGE_PROVIDERS]?.requiresApiKey ||
      resolveImageApiKey(imageId)),
  );
  input.enableVideos = Boolean(videoId && videoPrice > 0 && resolveVideoApiKey(videoId));
  emit({ type: 'capabilities', images: input.enableImages, videos: input.enableVideos });
  const result = await generatePreparationClassroom(input, {
    aiCall: async (system, user) => {
      emit({ type: 'model', system, user });
      const reply = await receive();
      if (reply.type !== 'model_result' || typeof reply.text !== 'string')
        throw new Error('Invalid model reply');
      return reply.text;
    },
    checkpoint: async (state) => {
      emit({ type: 'checkpoint', state });
      if ((await receive()).type !== 'ack') throw new Error('Checkpoint was not persisted');
    },
    progress: (message) => emit({ type: 'progress', message }),
  });
  // Persisted generated assets are embedded, so private drafts never depend on
  // an unauthenticated sidecar URL or a browser's localhost. Bound artifact size.
  if (input.enableImages || input.enableVideos) {
    const { generateMediaForClassroom, replaceMediaPlaceholders } =
      await import('../lib/server/classroom-media-generation');
    const { CLASSROOMS_DIR } = await import('../lib/server/classroom-storage');
    const { readFile, stat } = await import('node:fs/promises');
    const path = await import('node:path');
    const requests = result.outlines.flatMap((o) => o.mediaGenerations ?? []);
    if (
      requests.some(
        (r) => !/^[a-zA-Z0-9_-]+$/.test(r.elementId) || !['image', 'video'].includes(r.type),
      )
    )
      throw new Error('Invalid media generation request');
    if (requests.length) {
      emit({
        type: 'media_reserve',
        requests: requests.map((r) => ({ type: r.type, elementId: r.elementId })),
      });
      if ((await receive()).type !== 'ack') throw new Error('Media budget was not reserved');
    }
    const base = 'http://openmaic-generated.invalid';
    const map = await generateMediaForClassroom(result.outlines, input.resourceId, base);
    let total = 0;
    for (const [key, url] of Object.entries(map)) {
      const filename = path.basename(new URL(url).pathname);
      const file = path.join(CLASSROOMS_DIR, input.resourceId, 'media', filename);
      total += (await stat(file)).size;
      if (total > 40 * 1024 * 1024) throw new Error('Generated media exceeds 40MB artifact budget');
      const ext = path.extname(filename).slice(1);
      const mime = ext === 'mp4' ? 'video/mp4' : `image/${ext === 'jpg' ? 'jpeg' : ext}`;
      map[key] = `data:${mime};base64,${(await readFile(file)).toString('base64')}`;
    }
    if (requests.some((r) => !map[r.elementId]))
      throw new Error('Required generated media unavailable');
    replaceMediaPlaceholders(result.scenes, map);
  }
  emit({
    type: 'result',
    content: { stage: result.stage, scenes: result.scenes },
    outlines: result.outlines,
  });
}
main()
  .catch((error) => {
    emit({ type: 'error', message: String(error?.message ?? error) });
    process.exitCode = 1;
  })
  .finally(() => {
    process.stdin.destroy();
  });
