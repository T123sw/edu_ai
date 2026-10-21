import { createSession, reduceSession } from './model';
let input = '';
for await (const chunk of process.stdin) input += chunk;
const { manifest, state, commands = [] } = JSON.parse(input);
let result = state || createSession(manifest);
for (const command of commands) result = reduceSession(manifest, result, command);
process.stdout.write(JSON.stringify(result));
