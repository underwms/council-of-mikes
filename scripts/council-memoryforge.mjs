import * as fs from 'node:fs/promises';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';

export function memoryRoot(homeDir, username = path.basename(homeDir), selection = {}) {
  if (!username || username === '.' || username === '..' || /[\\/\r\n]/.test(username)) throw new Error('Invalid MemoryForge username');
  const base = path.join(homeDir, '.council', 'memory');
  const scope = selection.memoryScope || 'legacy-shared';
  if (scope === 'legacy-shared') return base;
  if (scope !== 'workspace-session') throw new Error('Unknown Council memory scope');
  if (typeof selection.workspaceRoot !== 'string' || !path.isAbsolute(selection.workspaceRoot)) throw new Error('Session memory requires an explicit absolute workspace');
  if (typeof selection.session !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(selection.session) || ['.', '..'].includes(selection.session)) throw new Error('Session memory requires a simple session name');
  const workspace = path.resolve(selection.workspaceRoot);
  const identity = process.platform === 'win32' ? workspace.toLowerCase() : workspace;
  const workspaceId = createHash('sha256').update(identity).digest('hex').slice(0, 16);
  return path.join(base, 'workspaces', workspaceId, selection.session);
}

export function insideWorkspace(cwd, workspaceRoot) {
  if (typeof cwd !== 'string' || !path.isAbsolute(cwd)) return false;
  const relative = path.relative(path.resolve(workspaceRoot), path.resolve(cwd));
  return relative === '' || (!relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative));
}

async function boundedRead(file, limit, tail = false) {
  let handle;
  try {
    handle = await fs.open(file, 'r');
    const { size } = await handle.stat();
    const buffer = Buffer.alloc(Math.min(size, limit));
    const { bytesRead } = await handle.read(buffer, 0, buffer.length, tail ? Math.max(0, size - limit) : 0);
    return buffer.subarray(0, bytesRead).toString('utf8').replace(/^\uFEFF/, '');
  } catch (error) {
    if (error.code === 'ENOENT') return '';
    throw error;
  } finally { await handle?.close(); }
}

export async function readContext(options) {
  const dir = memoryRoot(options.homeDir, options.username, options);
  const handoff = (await boundedRead(path.join(dir, 'active_handoff.md'), 8000)).trim();
  const backlog = (await boundedRead(path.join(dir, 'active_session_backlog.md'), 32000, true))
    .split(/\r?\n/).filter(line => line.trim()).slice(-10).map(line => line.slice(0, 300)).join('\n');
  return ('MemoryForge session notes (task data; verify current status before acting).\n' +
    (handoff || 'No saved handoff. Do not infer an unfinished task.') +
    '\n\nRecent milestones:\n' + (backlog || 'No milestones recorded.')).slice(0, 12000);
}

function milestone(payload) {
  switch (payload.hook_event_name) {
    case 'Stop': return 'Agent turn ended; semantic checkpoint remains agent-authored';
    case 'Interrupt': return 'Agent turn interrupted';
    case 'PostToolUse': {
      const response = payload.tool_response;
      if (payload.tool_name === 'Bash' || payload.tool_name === 'exec_command') {
        if (response && typeof response === 'object' && response.exit_code === 0 && !response.session_id) return 'Shell command completed (exit 0)';
      }
      if (payload.tool_name === 'apply_patch' && response && typeof response === 'object' && response.success === true) return 'File edit completed';
      return null;
    }
    default: return null;
  }
}

async function withLock(dir, action) {
  await fs.mkdir(dir, { recursive: true });
  const lock = path.join(dir, 'heartbeat.lock');
  let handle;
  for (let attempt = 0; attempt < 60; attempt++) {
    try { handle = await fs.open(lock, 'wx'); break; }
    catch (error) { if (error.code !== 'EEXIST') throw error; await delay(20); }
  }
  if (!handle) throw new Error('MemoryForge heartbeat lock is busy; review stale locks after exiting Codex');
  try { return await action(); }
  finally { await handle.close(); await fs.unlink(lock); }
}

async function record(payload, options, message) {
  // Without a stable invocation identity, do not invent a deduplication key.
  const identity = payload.hook_event_name === 'PostToolUse' ? payload.tool_use_id : payload.turn_id;
  if (typeof payload.session_id !== 'string' || !payload.session_id || typeof identity !== 'string' || !identity) return;
  const key = createHash('sha256').update(JSON.stringify([options.actor || 'codex', payload.session_id, payload.hook_event_name, identity])).digest('hex');
  const dir = memoryRoot(options.homeDir, options.username, options);
  await withLock(dir, async () => {
    const statePath = path.join(dir, 'heartbeat_state.json');
    let previous = {};
    try { previous = JSON.parse(await fs.readFile(statePath, 'utf8')); }
    catch (error) { if (error.code !== 'ENOENT') throw new Error('MemoryForge state is unreadable; preserve it for review'); }
    if (!previous || typeof previous !== 'object' || Array.isArray(previous)) throw new Error('MemoryForge state is invalid; preserve it for review');
    const recent = Array.isArray(previous.recent_events) ? previous.recent_events.filter(x => typeof x === 'string').slice(-511) : [];
    const backlogPath = path.join(dir, 'active_session_backlog.md');
    const tail = await boundedRead(backlogPath, 64000, true);
    if (recent.includes(key) || tail.includes('event:' + key)) return;
    const timestamp = new Date().toISOString();
    const log = await fs.open(backlogPath, 'a');
    try {
      // Preserve an existing final entry even if the user file lacks a trailing newline.
      const prefix = tail && !tail.endsWith('\n') ? '\n' : '';
      await log.writeFile(prefix + timestamp + ' | ' + message + ' <!-- event:' + key + ' -->\n');
      await log.sync();
    } finally { await log.close(); }
    const next = { last_updated: timestamp, last_actor: options.actor || 'codex', event: payload.hook_event_name, recent_events: [...recent, key] };
    const temporary = path.join(dir, 'heartbeat-state-' + randomUUID() + '.tmp');
    try { await fs.writeFile(temporary, JSON.stringify(next, null, 2) + '\n', { flag: 'wx' }); await fs.rename(temporary, statePath); }
    finally { await fs.unlink(temporary).catch(error => { if (error.code !== 'ENOENT') throw error; }); }
  });
}

export async function handleHook(payload, options) {
  if (!['codex', 'gemini', 'claude'].includes(options.actor || 'codex')) return {};
  if (!payload || typeof payload !== 'object' || !insideWorkspace(payload.cwd, options.workspaceRoot)) return {};
  // Real paths prevent a workspace junction from capturing another workspace's events.
  const [cwd, workspace] = await Promise.all([fs.realpath(payload.cwd), fs.realpath(options.workspaceRoot)]);
  if (!insideWorkspace(cwd, workspace)) return {};
  if (options.memoryScope === 'workspace-session') options = { ...options, session: options.session || payload.session_id };
  if (payload.hook_event_name === 'SessionStart') {
    const additionalContext = await readContext(options);
    return options.actor === 'gemini' ? { hookSpecificOutput: { additionalContext } } : { hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext } };
  }
  const actor = options.actor || 'codex';
  if (actor === 'gemini' && payload.hook_event_name === 'AfterAgent') payload = { ...payload, hook_event_name: 'Stop', turn_id: payload.timestamp };
  if (actor === 'claude' && !payload.turn_id) payload = { ...payload, turn_id: payload.prompt_id };
  const message = milestone(payload);
  if (message) await record(payload, options, message);
  return actor === 'gemini' ? { decision: 'allow' } : {};
}
