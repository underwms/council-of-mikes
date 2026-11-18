/** Local advisory reply checks. Never stores prompt/reply text or blocks a turn. */
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const rulesPath = path.join(root, 'instructions/references/reply-standard.json');
const maxInput = 1048576;
const ttl = 86400000;
const findingIds = new Set(['sentence-length', 'procedure-length', 'word-choice']);
const escapeRegex = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function proseLines(text) {
  let fence;
  const lines = [];
  for (const line of text.split(/\r?\n/)) {
    const marker = line.match(/^\s*(`{3,}|~{3,})/);
    if (marker) {
      if (!fence) fence = marker[1];
      else if (marker[1][0] === fence[0] && marker[1].length >= fence.length) fence = undefined;
      continue;
    }
    if (!fence && !/^\s*>/.test(line)) lines.push(line);
  }
  return lines.join('\n')
    .replace(/(`+)[\s\S]*?\1/g, ' LITERAL ')
    .replace(/"[^"\n]*"|\u201c[^\u201d\n]*\u201d/g, ' LITERAL ')
    .replace(/!?\[([^\]]*)\]\([^\n)]*\)/g, '$1')
    .replace(/https?:\/\/\S+|\b[A-Za-z]:[\\/]\S+/g, ' LITERAL ')
    .split('\n');
}

export function scoreReply(text, rules) {
  const counts = new Map();
  const add = id => counts.set(id, (counts.get(id) || 0) + 1);
  let paragraph = '';
  const inspect = (text, procedural) => {
    for (const sentence of text.split(/[.!?]+(?:\s|$)/)) {
      const words = sentence.match(/[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*/gu) || [];
      if (words.length > (procedural ? rules.checks.procedure_words : rules.checks.sentence_words)) add(procedural ? 'procedure-length' : 'sentence-length');
      for (const { phrase } of rules.checks.word_choices) {
        const hits = sentence.match(new RegExp('\\b' + escapeRegex(phrase) + '\\b', 'gi'));
        if (hits) counts.set('word-choice', (counts.get('word-choice') || 0) + hits.length);
      }
    }
  };
  for (const line of proseLines(text)) {
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)/);
    if (!line.trim() || numbered || /^\s*[-*+]\s/.test(line)) {
      inspect(paragraph, false);
      paragraph = '';
      if (numbered) inspect(numbered[1], true);
      else if (line.trim()) inspect(line.replace(/^\s*[-*+]\s+/, ''), false);
    } else paragraph += ' ' + line;
  }
  inspect(paragraph, false);
  const findings = [...counts].map(([rule, count]) => ({ rule, count }));
  return { score: Math.max(0, 100 - findings.reduce((sum, f) => sum + f.count, 0) * rules.checks.penalty_per_finding), findings };
}

function validAssessment(value, now) {
  return value?.schema_version === 1 && Number.isFinite(value.checked_at) && value.checked_at <= now && now - value.checked_at <= ttl &&
    Number.isInteger(value.score) && value.score >= 0 && value.score <= 100 && Array.isArray(value.findings) && value.findings.length <= 3 &&
    value.findings.every(f => findingIds.has(f.rule) && Number.isInteger(f.count) && f.count > 0 && f.count <= maxInput);
}

async function readState(file) {
  try {
    const stat = await fs.lstat(file);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 8192) return null;
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(await fs.readFile(file)));
  } catch { return null; }
}

async function writeState(folder, file, record) {
  let temporary;
  try {
    await fs.mkdir(folder, { recursive: true });
    const stat = await fs.lstat(folder);
    if (!stat.isDirectory() || stat.isSymbolicLink()) return;
    temporary = path.join(folder, randomUUID() + '.tmp');
    await fs.writeFile(temporary, JSON.stringify(record) + '\n', { encoding: 'utf8', flag: 'wx' });
    await fs.rename(temporary, file);
  } catch { /* Storage cannot stop the user turn. Do not log payloads. */ }
  finally { if (temporary) await fs.rm(temporary, { force: true }).catch(() => {}); }
}

export async function handleReplyHook(payload, { client, stateRoot = path.join(root, 'memory/runtime/reply-standard'), now = Date.now() } = {}) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload) || !['codex', 'gemini'].includes(client)) return {};
  const before = client === 'codex' ? 'UserPromptSubmit' : 'BeforeAgent';
  const after = client === 'codex' ? 'Stop' : 'AfterAgent';
  const event = payload.hook_event_name;
  if (![before, after].includes(event)) return {};
  const rules = JSON.parse(await fs.readFile(rulesPath, 'utf8'));
  const session = typeof payload.session_id === 'string' && payload.session_id.length > 0 && payload.session_id.length <= 1024 ? payload.session_id : null;
  const identity = session ? createHash('sha256').update(client + '\0' + session).digest('hex') : null;
  const file = identity ? path.join(stateRoot, identity + '.json') : null;
  const previous = file ? await readState(file) : null;
  if (event === before) {
    const valid = validAssessment(previous, now);
    let context = rules.guidance.join('\n');
    if (valid) {
      const findings = previous.findings.map(f => f.rule + ': ' + f.count).join('; ') || 'no issues in the checked subset';
      context += '\nPrevious reply advisory score: ' + previous.score + '/100. ' + findings + '. Correct these issues in this reply. This score is not full STE certification.';
    }
    if (file) await writeState(stateRoot, file, { ...(valid ? { checked_at: previous.checked_at, score: previous.score, findings: previous.findings } : {}), schema_version: 1, client, before_at: now });
    return { hookSpecificOutput: { hookEventName: before, additionalContext: context } };
  }
  const text = client === 'codex' ? payload.last_assistant_message : payload.prompt_response;
  if (file && typeof text === 'string' && Buffer.byteLength(text, 'utf8') <= maxInput) {
    await writeState(stateRoot, file, { schema_version: 1, client, ...(Number.isFinite(previous?.before_at) ? { before_at: previous.before_at } : {}), checked_at: now, ...scoreReply(text, rules) });
  }
  return {};
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  (async () => {
    let bytes = 0;
    const chunks = [];
    for await (const chunk of process.stdin) {
      bytes += chunk.length;
      if (bytes > maxInput) throw new Error('oversize');
      chunks.push(chunk);
    }
    if (process.argv.length !== 4 || process.argv[2] !== '--client') throw new Error('arguments');
    const payload = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(chunks)));
    console.log(JSON.stringify(await handleReplyHook(payload, { client: process.argv[3] })));
  })().catch(() => { console.log('{}'); });
}
