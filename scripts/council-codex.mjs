import path from 'node:path';
import * as fs from 'node:fs/promises';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { installCouncil, validateCouncil, cleanupCouncilProjects } from './council-codex-lib.mjs';
import { handleHook, readContext } from './council-memoryforge.mjs';

export async function executeCommand(args, { input = '' } = {}) {
  const [command, ...flags] = args;
  if (!['install', 'validate', 'onboard', 'hook', 'cleanup'].includes(command)) throw new Error('Usage: council-codex.mjs install|validate|onboard|hook [--workspace path] [--home path] [--username name] [--payload path] [--node path]');
  const names = { '--workspace': 'workspaceRoot', '--home': 'homeDir', '--username': 'username', '--payload': 'payloadRoot', '--node': 'nodePath', '--model': 'actor', '--memory-scope': 'memoryScope', '--session': 'session' };
  const o = {};
  for (let i = 0; i < flags.length; i += 2) {
    const name = names[flags[i]];
    if (!name) throw new Error('Unknown option: ' + flags[i]);
    if (o[name] !== undefined) throw new Error('Duplicate option: ' + flags[i]);
    if (!flags[i + 1] || flags[i + 1].startsWith('--')) throw new Error('Missing option value: ' + flags[i]);
    o[name] = flags[i + 1];
  }
  let hookPayload;
  if (command === 'hook') {
    try { if (Buffer.byteLength(input) > 1048576) throw new Error(); hookPayload = JSON.parse(input); }
    catch { throw new Error('Invalid hook JSON (one object, at most 1 MiB)'); }
  }
  const scriptParent = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  if (!o.workspaceRoot && path.basename(scriptParent) === '.council') {
    const metadata = JSON.parse(await fs.readFile(path.join(scriptParent, 'installation.json'), 'utf8'));
    o.workspaceRoot = metadata.workspaceRoot;
    o.homeDir ||= metadata.homeDir;
    o.username ||= metadata.username;
    o.nodePath ||= metadata.nodePath;
  }
  o.workspaceRoot = path.resolve(o.workspaceRoot || scriptParent);
  o.homeDir = path.resolve(o.homeDir || os.homedir());
  o.username ||= path.basename(o.homeDir);
  o.nodePath ||= globalThis.process?.execPath;
  if (command === 'cleanup') return { exitCode: 0, output: JSON.stringify(await cleanupCouncilProjects(o), null, 2) };
  if (command === 'onboard') return { exitCode: 0, output: await readContext(o) };
  if (command === 'hook') {
    return { exitCode: 0, output: JSON.stringify(await handleHook(hookPayload, o)) };
  }
  const report = command === 'install' ? await installCouncil(o) : await validateCouncil(o);
  const validation = command === 'install' ? report.report : report;
  const exitCode = validation.placement.status === 'pass' && validation.lifecycle.status === 'configured' ? 0 : 1;
  return { exitCode, output: JSON.stringify(report, null, 2) };
}

if (globalThis.process?.argv[1] && path.resolve(globalThis.process.argv[1]) === fileURLToPath(import.meta.url)) {
  (async () => {
    let input = '';
    if (process.argv[2] === 'hook') {
      for await (const chunk of process.stdin) {
        input += chunk;
        if (Buffer.byteLength(input) > 1048576) throw new Error('Hook input exceeds 1 MiB');
      }
    }
    const result = await executeCommand(process.argv.slice(2), { input });
    console.log(result.output);
    process.exitCode = result.exitCode;
  })().catch(error => {
    // Avoid logging tool arguments, transcripts, or hook payloads on failure.
    console.error(process.argv[2] === 'hook' ? 'MemoryForge hook failed; check cache permissions and lock/state health.' : error.message);
    if (process.argv[2] === 'hook') console.log('{}');
    process.exitCode = 1;
  });
}
