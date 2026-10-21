// Execute the installed workflow's mechanical preparation in one command.
// Story, script, design and frame authoring remain owned by the native agent.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';

const project = path.resolve(process.argv[2]);
const scripts = path.resolve(process.argv[3]);
const measurements = [];

function run(file, args) {
  const started = Date.now();
  const command = spawnSync(process.execPath, [path.join(scripts, file), ...args], {
    cwd: project, stdio: 'inherit', env: process.env,
  });
  measurements.push({step: file, args, seconds: (Date.now() - started) / 1000});
  const timingFile = path.join(project, '.hyperframes/host-preparation-timings.jsonl');
  fs.mkdirSync(path.dirname(timingFile), {recursive: true});
  fs.appendFileSync(timingFile, JSON.stringify({...measurements.at(-1), started_at: started / 1000, exit_code: command.status})+'\n');
  if (command.error || command.status !== 0) throw Error(command.error?.message || `${file} exited ${command.status}`);
}

try {
  fs.rmSync(path.join(project, '.hyperframes/host-scene-assets.json'), {force: true});
  // The upstream parser only treats indented text under '(Frame N)' as speech.
  // Fail here with an actionable format example, before paying for silent audio.
  const narrated = fs.existsSync(path.join(project, 'SCRIPT.md'));
  const script = narrated ? fs.readFileSync(path.join(project, 'SCRIPT.md'), 'utf8') : '';
  if (narrated && (!/^#{2,3}\s+.*?\(frame\s+\d+\)/im.test(script) || !/^(?: {4,}|\t)\S/m.test(script))) {
    throw Error('SCRIPT.md must use native headings like "## Opening (Frame 1)" and indent each spoken paragraph by four spaces. Keep the complete narration; correct its format and retry.');
  }
  run('audio.mjs', ['--script', 'SCRIPT.md', '--storyboard', 'STORYBOARD.md', '--hyperframes', '.', '--out', 'audio_meta.json']);
  const hasAudio = fs.existsSync(path.join(project, 'audio_meta.json'));
  const audio = hasAudio ? JSON.parse(fs.readFileSync(path.join(project, 'audio_meta.json'), 'utf8')) : {voices: []};
  if (narrated && !audio.voices?.length) throw Error('Native audio returned no voices; correct the SCRIPT.md frame headings and indented narration.');
  if (hasAudio) {
    run('audio.mjs', ['sync-durations', '--audio-meta', 'audio_meta.json', '--storyboard', 'STORYBOARD.md']);
    run('audio.mjs', ['fetch-sfx', '--storyboard', 'STORYBOARD.md', '--hyperframes', '.']);
    run('captions.mjs', ['build', '--storyboard', 'STORYBOARD.md', '--audio-meta', 'audio_meta.json', '--hyperframes', '.', '--out', 'caption_groups.json']);
  }
  const packetModule = await import(pathToFileURL(path.join(scripts, 'frame-packets.mjs')));
  // Full native blueprint + motion recipes can exceed the upstream 48 KB default.
  // Retain their contents instead of sending the agent back to trim native design.
  const packets = packetModule.buildFramePackets({projectDir: project, maxPacketBytes: 128_000});
  const role = packetModule.buildRolePayload({outDir: path.join(project, '.hyperframes/frame-packets')});
  const manifest = {
    project_directory: project, role_file: role.path, packets,
    audio_duration_seconds: audio.voices.reduce((total, voice) => total + voice.duration_s, 0),
    timings: measurements,
  };
  const manifestFile = path.join(project, '.hyperframes/host-scene-assets.json');
  fs.writeFileSync(manifestFile, JSON.stringify(manifest, null, 2));
  console.log(JSON.stringify({manifest_file: manifestFile, frames: packets.length,
    audio_duration_seconds: manifest.audio_duration_seconds, timings: measurements,
    next: 'Call dispatch_frames with this project_directory. It passes the complete native role, packets, design and assets at their exact paths. Do not manually retype packets or call audio again unless narration changed.'}));
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
