import * as fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { createHash, randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { memoryRoot } from './council-memoryforge.mjs';
import { mergeCodexDefaults, mergeCodexWorkspaceRoots } from './council-codex-config.mjs';
import { auditSource, writeSourceLock } from './council-source.mjs';

const BEGIN = '<!-- COUNCIL CODEX BEGIN -->';
const END = '<!-- COUNCIL CODEX END -->';
const defaultScripts = path.dirname(fileURLToPath(import.meta.url));
const normalizeText = text => text.replace(/\r\n/g, '\n').trim();

export function mergeManagedBlock(existing, body) {
  const starts = existing.split(BEGIN).length - 1;
  const ends = existing.split(END).length - 1;
  if (starts !== ends || starts > 1 || (starts === 1 && existing.indexOf(BEGIN) > existing.indexOf(END))) throw new Error('Malformed or duplicate Council instruction block');
  const block = BEGIN + '\n' + body.trim() + '\n' + END;
  if (!starts) return (existing.trimEnd() ? existing.trimEnd() + '\n\n' : '') + block + '\n';
  return existing.slice(0, existing.indexOf(BEGIN)) + block + existing.slice(existing.indexOf(END) + END.length);
}

function managedBody(text) {
  mergeManagedBlock(text, 'validation');
  if (!text.includes(BEGIN)) throw new Error('Missing Council instruction block');
  return normalizeText(text.slice(text.indexOf(BEGIN) + BEGIN.length, text.indexOf(END)));
}

function parseConfiguration(text, label) {
  try { return JSON.parse(text); } catch { throw new Error('Invalid JSON configuration: ' + label); }
}

function options(input = {}) {
  const workspaceRoot = path.resolve(input.workspaceRoot || path.join(defaultScripts, '..'));
  const homeDir = path.resolve(input.homeDir || os.homedir());
  return { ...input, workspaceRoot, homeDir,
    councilRoot: path.resolve(input.councilRoot || path.join(homeDir, '.council')),
    username: input.username || path.basename(homeDir),
    scriptRoot: path.resolve(input.scriptRoot || defaultScripts),
    payloadRoot: path.resolve(input.payloadRoot || (path.basename(path.dirname(defaultScripts)) === '.council' ? path.dirname(defaultScripts) : path.join(workspaceRoot, 'temp/the-council/central'))) };
}

async function exists(file) {
  try { await fs.lstat(file); return true; } catch (error) { if (error.code === 'ENOENT') return false; throw error; }
}

async function readOptional(file) {
  try { return await fs.readFile(file, 'utf8'); } catch (error) { if (error.code === 'ENOENT') return ''; throw error; }
}

async function files(root) {
  const result = [];
  for (const entry of await fs.readdir(root, { withFileTypes: true })) {
    if (['__pycache__', '.pytest_cache', 'node_modules', '.venv', 'runtime', 'build', 'dist'].includes(entry.name) || entry.name.endsWith('.egg-info') || entry.name.endsWith('.pyc')) continue;
    const full = path.join(root, entry.name);
    if (entry.isSymbolicLink()) throw new Error('Payload links are not supported: ' + full);
    if (entry.isDirectory()) result.push(...await files(full));
    else if (entry.isFile()) result.push(full);
  }
  return result;
}

async function model(input) {
  const o = options(input);
  const manifest = JSON.parse(await fs.readFile(path.join(o.payloadRoot, 'manifest.json'), 'utf8'));
  if (!Array.isArray(manifest.skills) || !manifest.skills.length || new Set(manifest.skills).size !== manifest.skills.length || manifest.skills.some(name => typeof name !== 'string' || !/^[a-z0-9][a-z0-9-]*$/.test(name))) throw new Error('Invalid Council skill manifest');
  const repos = [];
  for (const entry of await fs.readdir(o.workspaceRoot, { withFileTypes: true })) {
    if (entry.isDirectory() && await exists(path.join(o.workspaceRoot, entry.name, '.git'))) repos.push(path.join(o.workspaceRoot, entry.name));
  }
  const render = text => text.replaceAll('__WORKSPACE_ROOT__', o.workspaceRoot).replaceAll('__COUNCIL_ROOT__', o.councilRoot);
  const renderJSON = value => typeof value === 'string' ? render(value) : Array.isArray(value) ? value.map(renderJSON) : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).map(([key, item]) => [key, renderJSON(item)])) : value;
  const renderContent = (file, content) => file.endsWith('.md') ? Buffer.from(render(content.toString('utf8'))) : file.endsWith('.json') ? Buffer.from(JSON.stringify(renderJSON(JSON.parse(content.toString('utf8'))), null, 2) + '\n') : content;
  const writes = [];
  for (const name of manifest.skills) {
    const sourceRoot = path.join(o.payloadRoot, 'skills', name);
    const skill = await fs.readFile(path.join(sourceRoot, 'SKILL.md'), 'utf8');
    if (!/^---\r?\n[\s\S]*?\r?\n---/.test(skill) || !/^name:\s*\S+/m.test(skill) || !/^description:\s*\S+/m.test(skill)) throw new Error('Invalid skill frontmatter: ' + name);
    const declaredName = skill.match(/^name:\s*["']?([^\r\n"']+)/m)?.[1].trim();
    if (declaredName !== name) throw new Error('Skill name differs from directory: ' + name);
    for (const file of await files(sourceRoot)) {
      const content = await fs.readFile(file);
      writes.push({ target: path.join(o.councilRoot, 'skills', name, path.relative(sourceRoot, file)), content: renderContent(file, content) });
    }
  }
  writes.push({ target: path.join(o.councilRoot, 'rules/workspace.md'), content: Buffer.from(render(await fs.readFile(path.join(o.payloadRoot, 'rules/workspace.md'), 'utf8'))) });
  if (await exists(path.join(o.payloadRoot, 'README.md'))) writes.push({ target: path.join(o.councilRoot, 'README.md'), content: Buffer.from(render(await fs.readFile(path.join(o.payloadRoot, 'README.md'), 'utf8'))) });
  if (await exists(path.join(o.payloadRoot, 'rules/global.md'))) writes.push({ target: path.join(o.councilRoot, 'rules/global.md'), content: Buffer.from(render(await fs.readFile(path.join(o.payloadRoot, 'rules/global.md'), 'utf8'))) });
  const sharedFile = await exists(path.join(o.payloadRoot, 'AGENTS.md')) ? path.join(o.payloadRoot, 'AGENTS.md') : path.join(o.payloadRoot, 'instructions/shared.md');
  const shared = render(await fs.readFile(sharedFile, 'utf8'));
  writes.push({ target: path.join(o.councilRoot, 'instructions/shared.md'), content: Buffer.from(shared) });
  writes.push({ target: path.join(o.councilRoot, 'manifest.json'), content: Buffer.from(JSON.stringify(manifest, null, 2) + '\n') });
  const sourceLock = path.join(o.payloadRoot, 'source-lock.json');
  if (!manifest.schema_version && await exists(sourceLock)) {
    if ((await fs.lstat(sourceLock)).isSymbolicLink()) throw new Error('Source lock must be a canonical file');
    writes.push({ target: path.join(o.councilRoot, 'source-lock.json'), content: await fs.readFile(sourceLock) });
  }
  for (const name of ['council-codex.mjs', 'council-codex-lib.mjs', 'council-codex-config.mjs', 'council-memoryforge.mjs', 'council-source.mjs']) {
    const source = path.join(o.scriptRoot, name);
    if (!(await exists(source))) throw new Error('Missing lifecycle script: ' + name);
    writes.push({ target: path.join(o.councilRoot, 'scripts', name), content: await fs.readFile(source) });
  }
  for (const name of ['setup-council.ps1', 'council.ps1', '.gitignore']) {
    const source = path.join(o.payloadRoot, name);
    if (await exists(source)) writes.push({ target: path.join(o.councilRoot, name), content: await fs.readFile(source) });
  }
  const runtimeInstaller = path.join(o.scriptRoot, 'install-engine-runtime.ps1');
  if (await exists(runtimeInstaller)) writes.push({ target: path.join(o.councilRoot, 'scripts/install-engine-runtime.ps1'), content: await fs.readFile(runtimeInstaller) });
  const workspaceValidator = path.join(o.scriptRoot, 'validate-workspace.ps1');
  if (await exists(workspaceValidator)) writes.push({ target: path.join(o.councilRoot, 'scripts/validate-workspace.ps1'), content: await fs.readFile(workspaceValidator) });
  const geminiOptimizer = path.join(o.scriptRoot, 'optimize-gemini-cli.ps1');
  if (await exists(geminiOptimizer)) writes.push({ target: path.join(o.councilRoot, 'scripts/optimize-gemini-cli.ps1'), content: await fs.readFile(geminiOptimizer) });
  const geminiCompatibility = path.join(o.scriptRoot, 'gemini-compat.mjs');
  if (await exists(geminiCompatibility)) writes.push({ target: path.join(o.councilRoot, 'scripts/gemini-compat.mjs'), content: await fs.readFile(geminiCompatibility) });

  for (const directory of ['docs', 'adapters', 'profiles', 'exclusions', 'project-instructions', 'project-skills', 'legacy', 'scripts/tests', 'council']) {
    const source = path.join(o.payloadRoot, directory);
    if (await exists(source)) for (const file of await files(source)) {
      const content = await fs.readFile(file);
      writes.push({ target: path.join(o.councilRoot, directory, path.relative(source, file)), content: renderContent(file, content) });
    }
  }
  const sharedPath = path.join(o.councilRoot, 'instructions/shared.md');
  const scope = 'Council root: ' + o.councilRoot + '\nFor work in ' + o.workspaceRoot + ' or its projects, use the shared Council instructions. Council definitions are central; never install agents or skills inside service repositories.\n';
  const instructions = [
    { target: path.join(o.homeDir, '.codex/AGENTS.md'), body: scope + 'Read ' + sharedPath + ' and the Codex adapter at ' + path.join(o.councilRoot, 'adapters/codex.md') + ' explicitly; Codex does not expand @file imports.' },
    { target: path.join(o.homeDir, '.gemini/GEMINI.md'), body: scope + 'Read ' + sharedPath + ' and the Gemini adapter at ' + path.join(o.councilRoot, 'adapters/gemini.md') + ' explicitly.' },
    { target: path.join(o.homeDir, '.claude/CLAUDE.md'), body: scope + '@' + sharedPath.replaceAll('\\', '/').replaceAll(' ', '\\ ') + '\nRead the Claude Code adapter at ' + path.join(o.councilRoot, 'adapters/claude.md') + '.' }
  ];
  const profileLinks = ['.agents', '.gemini', '.claude'].flatMap(folder => manifest.skills.map(name => ({ folder, name, link: path.join(o.homeDir, folder, 'skills', name), canonical: path.join(o.councilRoot, 'skills', name) })));
  const legacyText = await readOptional(path.join(o.payloadRoot, 'legacy-fingerprints.json'));
  const legacy = legacyText ? JSON.parse(legacyText) : {};
  if (legacyText) writes.push({ target: path.join(o.councilRoot, 'legacy-fingerprints.json'), content: Buffer.from(legacyText) });
  let codexDefaults;
  let codexWorkspaceRoots = [];
  if (manifest.adapters?.codex) {
    const payloadFile = relative => {
      const file = path.resolve(o.payloadRoot, relative);
      const within = path.relative(o.payloadRoot, file);
      if (within === '..' || within.startsWith('..' + path.sep) || path.isAbsolute(within)) throw new Error('Codex adapter resource escapes the payload');
      return file;
    };
    const descriptorFile = payloadFile(manifest.adapters.codex);
    const descriptor = parseConfiguration(await fs.readFile(descriptorFile, 'utf8'), 'Codex adapter');
    if (descriptor.workspace_write_roots) {
      if (!Array.isArray(descriptor.workspace_write_roots) || descriptor.workspace_write_roots.some(binding => binding !== 'council-root')) throw new Error('Unsupported Codex writable-root binding');
      codexWorkspaceRoots = descriptor.workspace_write_roots.map(() => o.councilRoot);
    }
    if (descriptor.policy_fragment) {
      if (descriptor.policy_destination !== '~/.codex/config.toml') throw new Error('Unsupported Codex policy destination');
      const fragmentFile = payloadFile(path.relative(o.payloadRoot, path.resolve(path.dirname(descriptorFile), descriptor.policy_fragment)));
      codexDefaults = await fs.readFile(fragmentFile, 'utf8');
      mergeCodexDefaults('', codexDefaults);
    }
  }
  const geminiFragmentFile = path.join(o.payloadRoot, 'adapters/gemini/settings-fragment.json');
  const geminiSettingsFragment = await exists(geminiFragmentFile) ? renderJSON(parseConfiguration(await fs.readFile(geminiFragmentFile, 'utf8'), 'Gemini settings fragment')) : undefined;
  return { o, manifest, repos, writes, instructions, profileLinks, legacy, codexDefaults, codexWorkspaceRoots, geminiSettingsFragment };
}

function quote(argument) {
  if (typeof argument !== 'string' || /["\r\n\x00$\x60%&|<>^]/.test(argument)) throw new Error('Unsupported shell metacharacter in hook argument');
  return '"' + argument + '"';
}

function owner(o) { return 'Council MemoryForge ' + createHash('sha256').update(o.workspaceRoot.toLowerCase()).digest('hex').slice(0, 12); }

export function buildHooks(input) {
  const o = options(input);
  const actor = input.actor || 'codex';
  if (!['codex', 'gemini', 'claude'].includes(actor)) throw new Error('Unknown Council model adapter');
  if (!o.nodePath) throw new Error('Node executable path is required for hook installation');
  const argumentsList = [o.nodePath, path.join(o.councilRoot, 'scripts/council-codex.mjs'), 'hook', '--workspace', o.workspaceRoot, '--home', o.homeDir, '--username', o.username, '--model', actor];
  const command = argumentsList.map(quote).join(' ');
  const psArgument = value => "'" + value.replaceAll("'", "''") + "'";
  const commandWindows = 'powershell.exe -NoProfile -NonInteractive -Command "& ' + argumentsList.map(psArgument).join(' ') + '"';
  if (actor === 'gemini') {
    const handler = { type: 'command', command: os.platform() === 'win32' ? commandWindows : command, timeout: 3000, name: owner(o) };
    return { hooks: { SessionStart: [{ hooks: [{ ...handler }] }], AfterAgent: [{ hooks: [{ ...handler }] }] } };
  }
  if (actor === 'claude') {
    const handler = { type: 'command', command: os.platform() === 'win32' ? commandWindows : command, timeout: 3, statusMessage: owner(o) };
    return { hooks: { SessionStart: [{ hooks: [{ ...handler }] }], Stop: [{ hooks: [{ ...handler }] }] } };
  }
  const handler = { type: 'command', command, commandWindows, timeout: 3, statusMessage: owner(o) };
  return { hooks: {
    SessionStart: [{ matcher: 'startup|resume|clear|compact', hooks: [{ ...handler, additionalContextLimit: 12000 }] }],
    Stop: [{ hooks: [{ ...handler }] }],
    Interrupt: [{ hooks: [{ ...handler }] }],
    PostToolUse: [{ matcher: '^(Bash|exec_command|apply_patch)$', hooks: [{ ...handler }] }]
  } };
}

function mergeHooks(existing, expected, o) {
  if (!existing || typeof existing !== 'object' || Array.isArray(existing)) throw new Error('Invalid existing hooks configuration');
  const merged = structuredClone(existing);
  if (merged.hooks !== undefined && (!merged.hooks || typeof merged.hooks !== 'object' || Array.isArray(merged.hooks))) throw new Error('Invalid existing hooks configuration');
  merged.hooks ||= {};
  for (const [event, groups] of Object.entries(merged.hooks)) {
    if (!Array.isArray(groups) || groups.some(group => !group || !Array.isArray(group.hooks))) throw new Error('Invalid existing hook groups: ' + event);
    merged.hooks[event] = groups.map(group => ({ ...group, hooks: group.hooks.filter(h => h.statusMessage !== owner(o) && h.name !== owner(o) && !(o.actor === 'gemini' && h.name === 'memoryforge-heartbeat')) })).filter(group => group.hooks.length);
  }
  for (const [event, groups] of Object.entries(expected.hooks)) merged.hooks[event] = [...(merged.hooks[event] || []), ...groups];
  return merged;
}

export function mergeGeminiSettings(currentSettings, o, fragment) {
  const desired = fragment?.context?.fileFiltering || {};
  if ((desired.respectGeminiIgnore !== undefined && typeof desired.respectGeminiIgnore !== 'boolean') ||
      (desired.customIgnoreFilePaths !== undefined && (!Array.isArray(desired.customIgnoreFilePaths) || desired.customIgnoreFilePaths.some(value => typeof value !== 'string')))) throw new Error('Invalid Gemini settings fragment');
  const settings = (currentSettings && typeof currentSettings === 'object' && !Array.isArray(currentSettings))
    ? { ...currentSettings }
    : {};

  const context = (settings.context && typeof settings.context === 'object' && !Array.isArray(settings.context))
    ? { ...settings.context }
    : {};

  const fileFiltering = (context.fileFiltering && typeof context.fileFiltering === 'object' && !Array.isArray(context.fileFiltering))
    ? { ...context.fileFiltering }
    : {};

  if (typeof fileFiltering.respectGeminiIgnore !== 'boolean') {
    fileFiltering.respectGeminiIgnore = desired.respectGeminiIgnore ?? true;
  }

  const councilIgnore = path.join(o.councilRoot, 'exclusions/global.ignore');
  const existingPaths = Array.isArray(fileFiltering.customIgnoreFilePaths)
    ? fileFiltering.customIgnoreFilePaths.filter(p => typeof p === 'string').slice()
    : [];

  const identity = value => process.platform === 'win32' ? path.resolve(value).toLowerCase() : path.resolve(value);
  for (const candidate of [councilIgnore, ...(desired.customIgnoreFilePaths || [])]) {
    if (!existingPaths.some(value => identity(value) === identity(candidate))) existingPaths.push(candidate);
  }
  fileFiltering.customIgnoreFilePaths = existingPaths;

  context.fileFiltering = fileFiltering;
  settings.context = context;

  return settings;
}


async function assertWritableTarget(target, roots) {
  let ancestor = target;
  while (!(await exists(ancestor))) {
    const parent = path.dirname(ancestor);
    if (parent === ancestor) throw new Error('Cannot resolve installation target');
    ancestor = parent;
  }
  if ((await fs.lstat(ancestor)).isSymbolicLink()) throw new Error('Installation target has a conflicting link: ' + target);
  const resolved = await fs.realpath(ancestor);
  let permitted = false;
  for (const root of roots) {
    let rootAncestor = root;
    while (!(await exists(rootAncestor))) rootAncestor = path.dirname(rootAncestor);
    const realRoot = path.resolve(await fs.realpath(rootAncestor), path.relative(rootAncestor, root));
    const realTarget = path.resolve(resolved, path.relative(ancestor, target));
    const relative = path.relative(realRoot, realTarget);
    if (relative === '' || (!relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative))) { permitted = true; break; }
  }
  if (!permitted) throw new Error('Installation target escapes workspace/Codex home: ' + target);
}

async function matchesFingerprint(directory, expected) {
  const actualFiles = await files(directory);
  if (actualFiles.length !== Object.keys(expected).length) return false;
  for (const file of actualFiles) {
    const relative = path.relative(directory, file).replaceAll('\\', '/');
    if (createHash('sha256').update(await fs.readFile(file)).digest('hex') !== expected[relative]) return false;
  }
  return true;
}

function stripLegacyGeminiContext(text, legacy, relative) {
  if (!legacy.globalInstructions?.[relative]) return text;
  if (createHash('sha256').update(text).digest('hex') !== legacy.globalInstructions[relative]) {
    if (text.includes('## 4. Automatic Session Onboarding') && text.includes('## 6. The Council V2')) throw new Error('Legacy Gemini context changed; preserve and reconcile it before migration');
    return text;
  }
  const start = text.indexOf('## 4. Automatic Session Onboarding');
  if (start < 0 || !text.includes('## 6. The Council V2')) throw new Error('Unrecognized legacy Gemini Council instructions');
  return text.slice(0, start).trimEnd() + '\n';
}

async function planLegacyRetirement(m) {
  const { o, legacy } = m;
  const actions = [];
  for (const [folder, packages] of Object.entries(legacy.workspace || {})) {
    if (!['.agents/skills', '.gemini/skills'].includes(folder)) throw new Error('Unexpected legacy workspace skill root');
    for (const [name, fingerprint] of Object.entries(packages)) {
      if (!m.manifest.skills.includes(name)) throw new Error('Unexpected legacy skill name');
      const source = path.join(o.workspaceRoot, folder, name);
      if (!(await exists(source))) continue;
      if (!(await matchesFingerprint(source, fingerprint))) throw new Error('Legacy workspace package changed: ' + name);
      const resolved = await fs.realpath(source);
      if (resolved.toLowerCase() !== path.resolve(source).toLowerCase()) throw new Error('Legacy workspace package is a redirected path');
      actions.push({ source, relative: path.join('workspace', folder, name) });
    }
  }
  for (const [relative, fingerprint] of Object.entries(legacy.workspaceFolders || {})) {
    if (relative !== 'tools/council') throw new Error('Unexpected legacy workspace tooling root');
    const source = path.join(o.workspaceRoot, relative);
    if (!(await exists(source))) continue;
    if (await exists(path.join(source, '.git'))) throw new Error('Do not move an independent Git repository as a tooling directory');
    if (!(await matchesFingerprint(source, fingerprint))) throw new Error('Legacy workspace engine changed; reconcile before migration');
    if ((await fs.realpath(source)).toLowerCase() !== path.resolve(source).toLowerCase()) throw new Error('Legacy engine path is redirected');
    actions.push({ source, relative: path.join('workspace', relative) });
  }
  for (const [scope, entries] of [['workspace', legacy.workspaceFiles || {}], ['profile', legacy.profileFiles || {}]]) {
    const allowed = scope === 'workspace' ? ['GEMINI.md', '.gemini/GEMINI.md', '.gemini/.rules/rules.md', '.agents/rules/workspace.md', 'scripts/onboard.py', 'scripts/heartbeat_hook.py', 'scripts/convene.py'] : ['.gemini/scripts/onboard.py', '.gemini/scripts/heartbeat_hook.py', '.gemini/.rules/rules.md'];
    for (const [relative, fingerprint] of Object.entries(entries)) {
      if (!allowed.includes(relative)) throw new Error('Unexpected legacy file retirement path');
      const source = path.join(scope === 'workspace' ? o.workspaceRoot : o.homeDir, relative);
      if (!(await exists(source))) continue;
      if (createHash('sha256').update(await fs.readFile(source)).digest('hex') !== fingerprint) throw new Error('Legacy Council file changed; reconcile before migration: ' + relative);
      await assertWritableTarget(source, [scope === 'workspace' ? o.workspaceRoot : o.homeDir]);
      actions.push({ source, relative: path.join(scope, relative) });
    }
  }
  for (const action of actions) {
    const destination = path.join(o.councilRoot, 'legacy', action.relative);
    await assertWritableTarget(destination, [o.homeDir]);
    if (await exists(destination)) throw new Error('Legacy archive destination already exists: ' + destination);
  }
  return actions;
}

async function preflight(m) {
  const { o, instructions, profileLinks, legacy } = m;
  m.adoptions = [];
  m.retirements = await planLegacyRetirement(m);
  const oldPolicy = path.join(o.homeDir, '.gemini/policies');
  const canonicalPolicy = path.join(o.councilRoot, 'adapters/gemini/policies');
  if (legacy.profilePolicies && await exists(oldPolicy)) {
    const stat = await fs.lstat(oldPolicy);
    if (stat.isSymbolicLink()) {
      if ((await fs.realpath(oldPolicy)).toLowerCase() !== path.resolve(canonicalPolicy).toLowerCase()) throw new Error('Gemini policy link conflicts');
    } else {
      if (!(await matchesFingerprint(oldPolicy, legacy.profilePolicies))) throw new Error('Gemini policies changed; reconcile before migration');
      if (await exists(canonicalPolicy)) throw new Error('Canonical Gemini policy directory already exists');
      await assertWritableTarget(canonicalPolicy, [o.homeDir]);
      m.policyAdoption = { source: oldPolicy, destination: canonicalPolicy };
    }
  }

  if (await exists(path.join(o.homeDir, '.codex/AGENTS.override.md'))) throw new Error('Global AGENTS.override.md takes precedence');
  for (const instruction of instructions) {
    const current = await readOptional(instruction.target);
    const prepared = instruction.target === path.join(o.homeDir, '.gemini/GEMINI.md') ? stripLegacyGeminiContext(current, legacy, '.gemini/GEMINI.md') : current;
    mergeManagedBlock(prepared, instruction.body);
  }
  for (const { link, canonical, folder, name } of profileLinks) {
    if (await exists(link)) {
      const stat = await fs.lstat(link);
      if (stat.isSymbolicLink() && path.resolve(await fs.realpath(link)).toLowerCase() === path.resolve(canonical).toLowerCase()) continue;
      const fingerprint = legacy.profiles?.[folder]?.[name];
      if (!stat.isDirectory() || stat.isSymbolicLink() || !fingerprint || !(await matchesFingerprint(link, fingerprint))) throw new Error('Profile skill path conflicts: ' + link);
      await assertWritableTarget(link, [o.homeDir]);
      m.adoptions.push({ link, folder, name });
    } else await assertWritableTarget(link, [o.homeDir]);
  }
}

export async function validateCouncil(input = {}) {
  const placement = { status: 'fail', errors: [] };
  const lifecycle = { status: 'absent', errors: [], trust: 'unverified' };
  const runtime = { status: 'unverified', checks: ['native command startup', 'fresh workspace and repository discovery', 'trusted hooks actually executed', 'workspace integrity validator'] };
  const report = { placement, lifecycle, runtime, ready: false };
  let m;
  try { m = await model(input); } catch (error) { placement.errors.push(error.message); return report; }
  const { o, manifest, repos, writes, instructions, profileLinks } = m;
  report.skills = manifest.skills.length; report.repositories = repos.length;
  if (m.codexDefaults) {
    try {
      const current = await readOptional(path.join(o.homeDir, '.codex/config.toml'));
      if (mergeCodexWorkspaceRoots(mergeCodexDefaults(current, m.codexDefaults), m.codexWorkspaceRoots) !== current) placement.errors.push('Codex Council defaults or writable roots are missing/stale');
    } catch (error) { placement.errors.push('Codex configuration audit: ' + error.message); }
  }
  if (m.geminiSettingsFragment) {
    try {
      const current = parseConfiguration(await readOptional(path.join(o.homeDir, '.gemini/settings.json')) || '{}', 'Gemini settings');
      if (JSON.stringify(mergeGeminiSettings(current, o, m.geminiSettingsFragment)) !== JSON.stringify(current)) placement.errors.push('Gemini Council settings fragment is missing/stale');
    } catch (error) { placement.errors.push('Gemini settings audit: ' + error.message); }
  }
  if (await exists(path.join(o.homeDir, '.codex/AGENTS.override.md'))) placement.errors.push('Global instruction override takes precedence');
  for (const { target, body } of instructions) {
    try { if (managedBody(await fs.readFile(target, 'utf8')) !== normalizeText(body)) throw new Error('stale managed content'); }
    catch (error) { placement.errors.push('Council instruction mismatch: ' + target + ' (' + error.message + ')'); }
  }
  for (const { target, content } of writes) {
    try { if (!(await fs.readFile(target)).equals(content)) placement.errors.push('Payload mismatch: ' + target); }
    catch (error) { placement.errors.push('Missing/unreadable payload: ' + target); }
  }
  for (const { link, canonical } of profileLinks) {
    try {
      if (!(await fs.lstat(link)).isSymbolicLink() || (await fs.realpath(link)).toLowerCase() !== (await fs.realpath(canonical)).toLowerCase()) placement.errors.push('Profile skill junction/link mismatch: ' + link);
    } catch { placement.errors.push('Missing/broken profile skill link: ' + link); }
  }
  for (const repo of repos) {
    if ((await readOptional(path.join(repo, 'AGENTS.md'))).includes(BEGIN)) placement.errors.push('Legacy Council project instruction remains: ' + repo);
    for (const name of manifest.skills) if (await exists(path.join(repo, '.agents/skills', name))) placement.errors.push('Project skill artifact remains: ' + repo + '/' + name);
  }
  if (m.legacy.profilePolicies && (await exists(path.join(o.homeDir, '.gemini/policies')) || await exists(path.join(o.councilRoot, 'adapters/gemini/policies')))) {
    const policy = path.join(o.homeDir, '.gemini/policies');
    try {
      if (!(await fs.lstat(policy)).isSymbolicLink() || (await fs.realpath(policy)).toLowerCase() !== path.resolve(o.councilRoot, 'adapters/gemini/policies').toLowerCase()) placement.errors.push('Gemini policy route does not reference the canonical Council');
    } catch { placement.errors.push('Canonical Gemini policy route is missing'); }
  }
  placement.status = placement.errors.length ? 'fail' : 'pass';
  try {
    const installed = JSON.parse(await fs.readFile(path.join(o.councilRoot, 'installation.json'), 'utf8'));
    if (installed.workspaceRoot !== o.workspaceRoot || installed.homeDir !== o.homeDir || installed.username !== o.username || installed.councilRoot !== o.councilRoot) throw new Error('Installation metadata belongs to another location');
    if (!(await exists(installed.nodePath)) || !(await fs.stat(installed.nodePath)).isFile()) lifecycle.errors.push('Configured Node executable is missing');
    for (const actor of ['codex', 'gemini', 'claude']) {
      const expected = buildHooks({ ...o, nodePath: installed.nodePath, actor });
      const settings = actor === 'codex' ? '.codex/hooks.json' : '.' + actor + '/settings.json';
      const actual = parseConfiguration(await fs.readFile(path.join(o.homeDir, settings), 'utf8'), actor + ' hooks');
      for (const [event, groups] of Object.entries(expected.hooks)) {
        const handlers = (actual.hooks?.[event] || []).flatMap(group => group.hooks || []).filter(h => h.statusMessage === owner(o) || h.name === owner(o));
        if (handlers.length !== 1 || JSON.stringify(handlers[0]) !== JSON.stringify(groups[0].hooks[0])) lifecycle.errors.push('Missing/stale ' + actor + ' Council hook: ' + event);
        const ownedGroups = (actual.hooks?.[event] || []).filter(group => group.hooks?.some(h => h.statusMessage === owner(o) || h.name === owner(o)));
        if (ownedGroups.length === 1 && ownedGroups[0].matcher !== groups[0].matcher) lifecycle.errors.push('Stale ' + actor + ' hook matcher: ' + event);
      }
    }
    for (const name of ['council-codex.mjs', 'council-codex-lib.mjs', 'council-codex-config.mjs', 'council-memoryforge.mjs', 'council-source.mjs']) if (!(await exists(path.join(o.councilRoot, 'scripts', name)))) lifecycle.errors.push('Missing lifecycle script: ' + name);
    if (!(await exists(memoryRoot(o.homeDir, o.username)))) lifecycle.errors.push('MemoryForge directory absent');
    lifecycle.status = lifecycle.errors.length ? 'fail' : 'configured';
  } catch (error) { lifecycle.status = error.code === 'ENOENT' ? 'absent' : 'fail'; lifecycle.errors.push(error.code === 'ENOENT' ? 'Codex lifecycle configuration is absent' : error.message); }
  return report;
}

async function migrateMemory(o) {
  const destination = memoryRoot(o.homeDir, o.username);
  await fs.mkdir(destination, { recursive: true });
  const sources = [];
  for (const actor of ['codex', 'gemini']) {
    const source = path.join(o.homeDir, '.' + actor, 'tmp', o.username, 'memory');
    if (!(await exists(source))) continue;
    const real = await fs.realpath(source);
    if (real.toLowerCase() !== path.resolve(source).toLowerCase()) throw new Error('Legacy memory directory is redirected; reconcile before migration');
    for (const entry of await fs.readdir(source, { withFileTypes: true })) {
      if (!entry.isFile()) continue;
      const file = path.join(source, entry.name);
      sources.push({ actor, file, name: entry.name, modified: (await fs.stat(file)).mtimeMs });
    }
  }
  if (!(await exists(path.join(destination, 'active_handoff.md')))) {
    const handoff = sources.filter(item => item.name === 'active_handoff.md').sort((a, b) => b.modified - a.modified)[0];
    if (handoff) await fs.copyFile(handoff.file, path.join(destination, 'active_handoff.md'));
  }
  if (!(await exists(path.join(destination, 'active_session_backlog.md')))) {
    const lines = [];
    for (const item of sources.filter(item => item.name === 'active_session_backlog.md').sort((a, b) => a.modified - b.modified)) lines.push(...(await fs.readFile(item.file, 'utf8')).replace(/^\uFEFF/, '').split(/\r?\n/).filter(Boolean));
    if (lines.length) await fs.writeFile(path.join(destination, 'active_session_backlog.md'), [...new Set(lines)].join('\n') + '\n');
  }
  const archive = path.join(destination, 'archive', 'migration-' + randomUUID());
  for (const item of sources) {
    const target = path.join(archive, item.actor, item.name);
    await assertWritableTarget(target, [o.homeDir]);
    await fs.mkdir(path.dirname(target), { recursive: true });
    await fs.rename(item.file, target);
  }
}

export async function installCouncil(input = {}) {
  const m = await model(input);
  const { o, writes, instructions, repos, manifest, profileLinks } = m;
  if (manifest.schema_version === 1) {
    const sourceReport = await auditSource(o.payloadRoot, {checkLock: true});
    if (sourceReport.status !== 'pass') throw new Error('Release integrity failed: ' + sourceReport.errors.join('; '));
  }
  if (manifest.distribution?.project_cleanup === false) {
    for (const repo of repos) {
      if ((await readOptional(path.join(repo, 'AGENTS.md'))).includes(BEGIN)) throw new Error('Existing repository Council instructions require separate reconciliation: ' + repo);
      for (const name of manifest.skills) if (await exists(path.join(repo, '.agents/skills', name))) throw new Error('Existing repository Council skill requires separate reconciliation: ' + repo);
    }
    const policy = path.join(o.homeDir, '.gemini/policies');
    if (await exists(policy) && (!(await fs.lstat(policy)).isSymbolicLink() || (await fs.realpath(policy)).toLowerCase() !== path.resolve(o.councilRoot, 'adapters/gemini/policies').toLowerCase())) throw new Error('Existing Gemini policy directory requires separate reconciliation');
  }
  await preflight(m);
  for (const name of ['council-codex.mjs', 'council-codex-lib.mjs', 'council-codex-config.mjs', 'council-memoryforge.mjs', 'council-source.mjs']) {
    if (!(await exists(path.join(o.scriptRoot, name)))) throw new Error('Missing lifecycle script: ' + name);
  }
  if (!o.nodePath || !(await exists(o.nodePath)) || !(await fs.stat(o.nodePath)).isFile()) throw new Error('Node executable is missing');
  const expected = buildHooks(o);
  const hookPath = path.join(o.homeDir, '.codex/hooks.json');
  const existing = await readOptional(hookPath);
  const hookText = JSON.stringify(mergeHooks(existing ? parseConfiguration(existing, 'Codex hooks') : {}, expected, o), null, 2) + '\n';
  const metadata = { workspaceRoot: o.workspaceRoot, homeDir: o.homeDir, councilRoot: o.councilRoot, username: o.username, scriptRoot: path.join(o.councilRoot, 'scripts'), nodePath: o.nodePath };
  const pending = [...writes];
  if (m.codexDefaults) {
    const target = path.join(o.homeDir, '.codex/config.toml');
    const merged = mergeCodexWorkspaceRoots(mergeCodexDefaults(await readOptional(target), m.codexDefaults), m.codexWorkspaceRoots);
    pending.push({ target, content: Buffer.from(merged) });
  }
  for (const actor of ['gemini', 'claude']) {
    const settingsPath = path.join(o.homeDir, '.' + actor, 'settings.json');
    const current = await readOptional(settingsPath);
    const actorOptions = { ...o, actor };
    let parsedSettings = current ? parseConfiguration(current, actor + ' settings') : {};
    if (actor === 'gemini') {
      parsedSettings = mergeGeminiSettings(parsedSettings, o, m.geminiSettingsFragment);
    }
    const merged = mergeHooks(parsedSettings, buildHooks(actorOptions), actorOptions);
    pending.push({ target: settingsPath, content: Buffer.from(JSON.stringify(merged, null, 2) + '\n') });
  }

  for (const { target, body } of instructions) {
    let current = await readOptional(target);
    if (target === path.join(o.homeDir, '.gemini/GEMINI.md')) {
      current = stripLegacyGeminiContext(current, m.legacy, '.gemini/GEMINI.md').replace('@./.rules/rules.md', 'Read ' + path.join(o.councilRoot, 'rules/global.md').replaceAll('\\', '/') + ' explicitly.');
    }
    pending.push({ target, content: Buffer.from(mergeManagedBlock(current, body)) });
  }
  pending.push({ target: hookPath, content: Buffer.from(hookText) }, { target: path.join(o.councilRoot, 'installation.json'), content: Buffer.from(JSON.stringify(metadata, null, 2) + '\n') });
  const privateRoot = memoryRoot(o.homeDir, o.username);
  const oldGlobalRules = path.join(o.homeDir, '.gemini/.rules/rules.md');
  if (!m.manifest.schema_version && m.retirements.some(item => item.source === oldGlobalRules)) pending.push({ target: path.join(o.councilRoot, 'rules/global.md'), content: await fs.readFile(oldGlobalRules) });

  for (const item of pending) await assertWritableTarget(item.target, [o.homeDir]);
  await assertWritableTarget(privateRoot, [o.homeDir]);
  const changed = [];
  const backupRoot = path.join(o.councilRoot, 'backups', randomUUID());
  await assertWritableTarget(backupRoot, [o.homeDir]);
  for (const { target, content } of pending) {
    let old;
    try { old = await fs.readFile(target); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (old?.equals(content)) continue;
    if (old) {
      await fs.mkdir(backupRoot, { recursive: true });
      const backup = path.join(backupRoot, createHash('sha256').update(target).digest('hex') + '.bak');
      await fs.writeFile(backup, old);
      await fs.appendFile(path.join(backupRoot, 'files.jsonl'), JSON.stringify({ target, backup }) + '\n');
    }
    await fs.mkdir(path.dirname(target), { recursive: true });
    await fs.writeFile(target, content);
    changed.push(target);
  }
  for (const adoption of m.adoptions) {
    const destination = path.join(backupRoot, 'legacy-skills', adoption.folder, adoption.name);
    await assertWritableTarget(destination, [o.homeDir]);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    const resolved = await fs.realpath(adoption.link);
    if (resolved.toLowerCase() !== path.resolve(adoption.link).toLowerCase()) throw new Error('Legacy skill move target changed');
    await fs.rename(adoption.link, destination);
    changed.push(adoption.link);
  }
  for (const { link, canonical } of profileLinks) if (!(await exists(link))) {
    await fs.mkdir(path.dirname(link), { recursive: true });
    await fs.symlink(canonical, link, 'junction');
    changed.push(link);
  }
  if (m.policyAdoption) {
    const { source, destination } = m.policyAdoption;
    const resolved = await fs.realpath(source);
    if (resolved.toLowerCase() !== path.resolve(source).toLowerCase()) throw new Error('Gemini policy source changed');
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.rename(source, destination);
    await fs.symlink(destination, source, 'junction');
    changed.push(source);
  }
  const policySource = path.join(o.homeDir, '.gemini/policies');
  const policyTarget = path.join(o.councilRoot, 'adapters/gemini/policies');
  if (!(await exists(policySource)) && await exists(policyTarget)) {
    await assertWritableTarget(policySource, [o.homeDir]);
    await fs.mkdir(path.dirname(policySource), { recursive: true });
    await fs.symlink(policyTarget, policySource, 'junction');
    changed.push(policySource);
  }
  for (const retirement of m.retirements) {
    const destination = path.join(o.councilRoot, 'legacy', retirement.relative);
    if (await exists(destination)) throw new Error('Legacy archive destination already exists: ' + destination);
    await assertWritableTarget(destination, [o.homeDir]);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.rename(retirement.source, destination);
    changed.push(retirement.source);
  }
  if (manifest.distribution?.project_cleanup !== false) {
    const workspaceInstructions = path.join(o.workspaceRoot, 'AGENTS.md');
    const oldInstructions = await readOptional(workspaceInstructions);
    if (oldInstructions.includes(BEGIN)) {
      mergeManagedBlock(oldInstructions, 'validation');
      await fs.mkdir(backupRoot, { recursive: true });
      await fs.writeFile(path.join(backupRoot, 'workspace-AGENTS.md'), oldInstructions);
      const remaining = (oldInstructions.slice(0, oldInstructions.indexOf(BEGIN)) + oldInstructions.slice(oldInstructions.indexOf(END) + END.length)).trim();
      if (remaining) await fs.writeFile(workspaceInstructions, remaining + '\n'); else await fs.unlink(workspaceInstructions);
      changed.push(workspaceInstructions);
    }
    await cleanupCouncilProjects({ ...o, relocateExistingInstructions: true });
  }
  if (manifest.distribution?.import_private_memory === false) await fs.mkdir(privateRoot, {recursive: true});
  else await migrateMemory(o);
  if (manifest.schema_version === 1) await writeSourceLock(o.councilRoot);
  const report = await validateCouncil(o);
  if (report.placement.status !== 'pass' || report.lifecycle.status !== 'configured') throw new Error('Installation validation failed: ' + JSON.stringify(report));
  return { changed, backupRoot: changed.length ? backupRoot : null, report, message: 'Static installation verified. Review/trust hooks and verify native runtime before claiming readiness.' };
}


export async function cleanupCouncilProjects(input = {}) {
  const o = options(input);
  const manifest = JSON.parse(await fs.readFile(path.join(o.payloadRoot, 'manifest.json'), 'utf8'));
  const retainedRoot = path.resolve(input.retainedRoot || path.join(o.councilRoot, 'project-instructions'));
  const backupRoot = path.resolve(input.backupRoot || path.join(o.councilRoot, 'backups/project-cleanup-' + randomUUID()));
  const retainedSkillRoot = path.resolve(input.retainedSkillRoot || path.join(o.councilRoot, 'project-skills'));
  const actions = [];
  const repoRoots = [];
  for (const entry of await fs.readdir(o.workspaceRoot, { withFileTypes: true })) {
    const repo = path.join(o.workspaceRoot, entry.name);
    if (!entry.isDirectory() || !(await exists(path.join(repo, '.git')))) continue;
    repoRoots.push(repo);
    const localSkills = path.join(repo, '.agents/skills');
    if (input.relocateExistingInstructions !== false && await exists(localSkills)) {
      for (const entry of await fs.readdir(localSkills, { withFileTypes: true })) {
        if (!entry.isDirectory() || entry.isSymbolicLink()) continue;
        const source = path.join(localSkills, entry.name);
        const target = path.join(retainedSkillRoot, path.basename(repo), entry.name);
        if (await exists(target)) throw new Error('Retained project skill conflicts: ' + target);
        const realSource = await fs.realpath(source);
        const realRepo = await fs.realpath(repo);
        if (path.relative(realRepo, realSource) !== path.join('.agents', 'skills', entry.name)) throw new Error('Project skill move escapes repository');
        await assertWritableTarget(target, [o.workspaceRoot, o.homeDir]);
        actions.push({ kind: 'skill', target: source, retainedTarget: target });
      }
    }

    const instruction = path.join(repo, 'AGENTS.md');
    const text = await readOptional(instruction);
    if (text.includes(BEGIN)) mergeManagedBlock(text, 'validation');
    const start = text.indexOf(BEGIN);
    const remaining = start < 0 ? text : (text.slice(0, start) + text.slice(text.indexOf(END) + END.length)).trimEnd().replace(/\s+$/g, '') + '\n';
    if (start >= 0 || (input.relocateExistingInstructions !== false && text.trim())) {
      const retained = remaining.trim() ? remaining : '';
      const target = path.join(retainedRoot, entry.name + '.md');
      if (retained && input.relocateExistingInstructions !== false && await exists(target) && await fs.readFile(target, 'utf8') !== retained) throw new Error('Central project instructions conflict: ' + entry.name);
      await assertWritableTarget(instruction, [o.workspaceRoot]);
      if (retained && input.relocateExistingInstructions !== false) await assertWritableTarget(target, [o.workspaceRoot, o.homeDir]);
      actions.push({ kind: 'instruction', target: instruction, text, retained, retainedTarget: target });
    }
    for (const name of manifest.skills) {
      const link = path.join(repo, '.agents/skills', name);
      if (!(await exists(link)) || !(await fs.lstat(link)).isSymbolicLink()) continue;
      const actual = path.resolve(await fs.readlink(link)).replace(/^\\\\\?\\/, '').toLowerCase();
      const canonical = path.resolve(o.workspaceRoot, '.agents/skills', name).toLowerCase();
      if (actual !== canonical) continue;
      // Only unlink the junction itself, never recursively remove or follow its target.
      const parent = await fs.realpath(path.dirname(link));
      const repoPath = await fs.realpath(repo);
      const relative = path.relative(repoPath, parent);
      if (relative !== path.join('.agents', 'skills')) throw new Error('Project cleanup parent escapes repository');
      actions.push({ kind: 'link', target: link, linkTarget: await fs.readlink(link) });
    }
  }
  if (!actions.length) return { removedLinks: 0, removedInstructions: 0, retainedInstructions: 0, retainedSkills: 0, changed: [], backupRoot: null };
  await assertWritableTarget(backupRoot, [o.workspaceRoot, o.homeDir]);
  await fs.mkdir(backupRoot, { recursive: true });
  const result = { removedLinks: 0, removedInstructions: 0, retainedInstructions: 0, retainedSkills: 0, changed: [], backupRoot };
  for (const action of actions) {
    const id = createHash('sha256').update(action.target).digest('hex');
    if (action.kind === 'instruction') {
      await fs.writeFile(path.join(backupRoot, id + '.md'), action.text);
      if (action.retained && input.relocateExistingInstructions === false) await fs.writeFile(action.target, action.retained);
      else {
        if (action.retained) { await fs.mkdir(retainedRoot, { recursive: true }); await fs.writeFile(action.retainedTarget, action.retained); result.retainedInstructions++; }
        await fs.unlink(action.target); result.removedInstructions++;
      }
    } else if (action.kind === 'skill') {
      await fs.mkdir(path.dirname(action.retainedTarget), { recursive: true });
      await fs.rename(action.target, action.retainedTarget); result.retainedSkills++;
    } else { await fs.unlink(action.target); result.removedLinks++; }
    await fs.appendFile(path.join(backupRoot, 'files.jsonl'), JSON.stringify({ target: action.target, kind: action.kind, linkTarget: action.linkTarget, retainedTarget: action.retained || action.kind === 'skill' ? action.retainedTarget : undefined }) + '\n');
    result.changed.push(action.target);
  }
  for (const repo of repoRoots) for (const suffix of ['.agents/skills', '.agents']) {
    const dir = path.join(repo, suffix);
    if (await exists(dir) && !(await fs.lstat(dir)).isSymbolicLink() && (await fs.readdir(dir)).length === 0) await fs.rmdir(dir);
  }
  return result;
}
