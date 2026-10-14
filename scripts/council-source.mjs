/** Canonical source audit and explicit SHA-256 release locks, independent of placement. */
import * as fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const defaultRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const hash = data => createHash('sha256').update(data).digest('hex');
const namePattern = /^[a-z0-9][a-z0-9-]*$/;

async function child(root, relative) {
  if (typeof relative !== 'string' || !relative || path.isAbsolute(relative) || relative.split(/[\\/]/).includes('..')) throw new Error('Source path escapes root: ' + relative);
  const target = path.resolve(root, relative);
  const inside = path.relative(root, target);
  if (!inside || inside.startsWith('..') || path.isAbsolute(inside)) throw new Error('Source path escapes root: ' + relative);
  let ancestor = target;
  while (true) {
    try {
      const stat = await fs.lstat(ancestor);
      const resolved = await fs.realpath(ancestor);
      const same = process.platform === 'win32' ? resolved.toLowerCase() === ancestor.toLowerCase() : resolved === ancestor;
      if (stat.isSymbolicLink() || !same) throw new Error('Source links are not canonical files: ' + relative);
      break;
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
      ancestor = path.dirname(ancestor);
      if (ancestor === root) break;
    }
  }
  return target;
}

async function manifestAt(root) {
  const manifest = JSON.parse(await fs.readFile(path.join(root, 'manifest.json'), 'utf8'));
  if (manifest.schema_version !== 1) throw new Error('Versioned source manifest schema 1 is required');
  return manifest;
}

export async function sourceSnapshot(root = defaultRoot) {
  root = path.resolve(root);
  const manifest = await manifestAt(root);
  const snapshot = {};
  async function add(relative) {
    const target = await child(root, relative);
    const stat = await fs.lstat(target);
    if (stat.isDirectory()) {
      for (const entry of (await fs.readdir(target)).sort()) {
        if (['__pycache__', '.pytest_cache', '.git', 'work', 'backups', 'memory', 'node_modules'].includes(entry)) continue;
        await add(path.join(relative, entry));
      }
    } else if (stat.isFile()) snapshot[relative.replaceAll('\\', '/')] = hash(await fs.readFile(target));
  }
  for (const relative of [...manifest.source_roots, ...manifest.source_files]) await add(relative);
  return Object.fromEntries(Object.entries(snapshot).sort(([a], [b]) => a.localeCompare(b)));
}

export async function verifySourceLock(root = defaultRoot) {
  let loaded = false;
  try {
    const lock = JSON.parse(await fs.readFile(await child(path.resolve(root), 'source-lock.json'), 'utf8'));
    loaded = true;
    if (lock.schema_version !== 1 || !lock.files || typeof lock.files !== 'object') throw new Error('Invalid source lock');
    const current = await sourceSnapshot(root);
    const errors = [];
    for (const relative of new Set([...Object.keys(lock.files), ...Object.keys(current)])) {
      if (lock.files[relative] !== current[relative]) errors.push('Source drift: ' + relative);
    }
    return { status: errors.length ? 'fail' : 'pass', files: Object.keys(current).length, errors };
  } catch (error) {
    const absent = !loaded && error.code === 'ENOENT';
    return { status: absent ? 'absent' : 'fail', errors: [absent ? 'Source lock is absent' : 'Source lock audit: ' + error.message] };
  }
}

export async function auditSource(root = defaultRoot, { checkLock = false } = {}) {
  root = path.resolve(root);
  const report = { status: 'fail', scope: 'canonical-source', errors: [], specialists: 0, workflows: 0, links: 0 };
  try {
    const manifest = await manifestAt(root);
    if (!manifest.version || manifest.execution?.scope !== 'user' || manifest.execution?.routine_development !== 'allow_without_prompt') report.errors.push('Missing version or user-scoped execution contract');
    const lists = [manifest.skills, manifest.specialists, manifest.workflows];
    for (const list of lists) if (!Array.isArray(list) || !list.length || new Set(list).size !== list.length || list.some(name => !namePattern.test(name))) throw new Error('Skill inventory must be nonempty, unique, and use simple names');
    if (new Set([...manifest.specialists, ...manifest.workflows]).size !== manifest.skills.length || manifest.skills.some(name => ![...manifest.specialists, ...manifest.workflows].includes(name))) report.errors.push('Combined specialist/workflow inventory differs from skills');
    for (const relative of Object.values(manifest.paths)) await fs.stat(await child(root, relative));
    const skillsRoot = await child(root, manifest.paths.skills);
    const actual = (await fs.readdir(skillsRoot, { withFileTypes: true })).filter(entry => entry.isDirectory()).map(entry => entry.name).sort();
    if (JSON.stringify(actual) !== JSON.stringify([...manifest.skills].sort())) report.errors.push('Actual skill inventory differs from manifest');
    for (const name of manifest.skills) {
      const skill = await child(root, `${manifest.paths.skills}/${name}/SKILL.md`);
      let text;
      try { text = await fs.readFile(skill, 'utf8'); } catch { report.errors.push('Missing package: ' + name); continue; }
      const front = text.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/)?.[1];
      if (!front || front.match(/^name:\s*([^\r\n]+)/m)?.[1].trim() !== name || !/^description:\s*\S+/m.test(front)) report.errors.push('Invalid skill metadata: ' + name);
      if (manifest.specialists.includes(name)) {
        report.specialists++;
        try { await fs.stat(await child(root, `${manifest.paths.skills}/${name}/references/${name}.md`)); } catch { report.errors.push('Missing specialist reference: ' + name); }
      } else report.workflows++;
    }
    if (!manifest.profiles?.[manifest.default_profile]) report.errors.push('Default profile is not registered');
    for (const [id, relative] of Object.entries(manifest.profiles || {})) {
      const file = await child(root, relative);
      const profile = JSON.parse(await fs.readFile(file, 'utf8'));
      if (profile.id !== id) report.errors.push('Profile ID mismatch: ' + id);
      for (const key of ['rules', 'corporate_rules']) await fs.stat(await child(root, path.relative(root, path.join(path.dirname(file), profile[key]))));
      if (id === 'fulfillment' && (!/PostgreSQL/.test(profile.stack?.persistence || '') || !profile.stack?.forbidden?.includes('Redis') || !profile.stack?.forbidden?.includes('Dapper') || !/MSTest.*NSubstitute/.test(profile.stack?.unit_tests || ''))) report.errors.push('Fulfillment profile violates current contracts');
    }
    for (const [id, relative] of Object.entries(manifest.adapters || {})) {
      const file = await child(root, relative);
      try {
        const adapter = JSON.parse(await fs.readFile(file, 'utf8'));
        if (adapter.id !== id || adapter.execution_scope !== 'user' || adapter.indexing_scope !== 'user') report.errors.push('Invalid user-scoped adapter: ' + id);
        for (const key of ['instructions', 'policy_fragment']) if (adapter[key]) await fs.stat(await child(root, path.relative(root, path.join(path.dirname(file), adapter[key]))));
      } catch (error) { report.errors.push('Invalid adapter resource: ' + id + ': ' + error.message); }
    }
    const snapshot = await sourceSnapshot(root);
    const markdown = Object.keys(snapshot).filter(relative => relative.endsWith('.md'));
    const wikilinks = new Set([...manifest.skills, ...markdown.map(relative => path.basename(relative, '.md'))]);
    for (const relative of markdown) {
      const text = await fs.readFile(await child(root, relative), 'utf8');
      const stripped = text.replace(/```[\s\S]*?```|`[^`\n]*`/g, '');
      for (const match of stripped.matchAll(/\[[^\]\n]+\]\(([^)\n]+)\)/g)) {
        const target = match[1].split('#')[0].trim().replace(/^<|>$/g, '');
        if (!target || /^([a-z]+:|\/)/i.test(target) || /[{}]/.test(target)) continue;
        report.links++;
        const destination = path.resolve(path.dirname(path.join(root, relative)), target);
        try { await fs.stat(await child(root, path.relative(root, destination))); } catch { report.errors.push('Broken source link: ' + relative + ' -> ' + target); }
      }
      for (const match of stripped.matchAll(/\[\[([^\]|#]+)(?:[^\]]*)\]\]/g)) if (!wikilinks.has(match[1]) && !match[1].includes('<')) report.errors.push('Broken wikilink: ' + relative + ' -> ' + match[1]);
      if (/dapper persistence isolation|Redis caching topologies|Redis sliding expiration/i.test(text)) report.errors.push('Stale persistence doctrine: ' + relative);
      if (relative === manifest.paths.host_rules && /\.gemini[\\/]tmp|\.gemini[\\/]skills|Sourcing & Fulfillment Pod Architecture Rules/.test(text)) report.errors.push('Workspace/Gemini rules leaked into global host rules');
    }
    if (checkLock) {
      report.lock = await verifySourceLock(root);
      if (report.lock.status !== 'pass') report.errors.push(...report.lock.errors);
    }
  } catch (error) { report.errors.push('Source structure: ' + error.message); }
  report.status = report.errors.length ? 'fail' : 'pass';
  return report;
}

export async function writeSourceLock(root = defaultRoot) {
  const report = await auditSource(root);
  if (report.status !== 'pass') throw new Error('Refusing source lock refresh: ' + report.errors.join('; '));
  const lock = { schema_version: 1, version: (await manifestAt(root)).version, files: await sourceSnapshot(root) };
  await fs.writeFile(await child(path.resolve(root), 'source-lock.json'), JSON.stringify(lock, null, 2) + '\n');
  return { status: 'pass', files: Object.keys(lock.files).length };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [command = 'audit', explicitRoot] = process.argv.slice(2);
  const root = explicitRoot ? path.resolve(explicitRoot) : defaultRoot;
  try {
    if (!['audit', 'check', 'lock'].includes(command)) throw new Error('Usage: council-source.mjs audit|check|lock [root]');
    const report = command === 'lock' ? await writeSourceLock(root) : await auditSource(root, { checkLock: command === 'check' });
    console.log(JSON.stringify(report, null, 2));
    process.exitCode = report.status === 'pass' ? 0 : 1;
  } catch (error) { console.error(error.message); process.exitCode = 1; }
}
