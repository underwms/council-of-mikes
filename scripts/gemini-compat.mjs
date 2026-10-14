/** Version-scoped repair; native policies and genuine flag checks remain intact. */
import * as fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const oldGuard = 'if (existingSkill && existingSkill.location !== newSkill.location) {';
const newGuard = 'if (existingSkill && existingSkill.location !== newSkill.location && !councilSameSkillFile(existingSkill.location, newSkill.location)) {';
const helper = `import * as councilSkillFs from "node:fs";
function councilSameSkillFile(left, right) {
  try {
    const a = councilSkillFs.realpathSync(left);
    const b = councilSkillFs.realpathSync(right);
    return process.platform === 'win32' ? a.toLowerCase() === b.toLowerCase() : a === b;
  } catch { return false; }
}
`;
const hash = value => createHash('sha256').update(value).digest('hex');

export function transformGeminiChunk(source) {
  let content = source.replace(/(function findUntrustedFlags\(command, untrustedContext\) \{)\r?\n  return \[\];(?=\r?\n)/g, '$1');
  if (!content.includes('Skill conflict detected')) throw new Error('Unrecognized Gemini skill warning structure');
  if (content.includes(newGuard)) {
    if (!content.startsWith(helper)) throw new Error('Changed Council compatibility helper');
  } else if (content.includes('fsSkills.realpathSync')) {
    if (!content.includes('import * as fsSkills from "node:fs";') || !content.includes('fsSkills.realpathSync(existingSkill.location).toLowerCase() === fsSkills.realpathSync(newSkill.location).toLowerCase()') || !content.includes('if (!isSameFile) {')) throw new Error('Unrecognized prior Gemini skill repair');
  } else {
    if (content.split(oldGuard).length !== 2) throw new Error('Unrecognized Gemini skill guard count');
    content = helper + content.replace(oldGuard, newGuard);
  }
  return {content, changed: content !== source};
}

async function regularFile(file) {
  const stat = await fs.lstat(file);
  if (!stat.isFile() || stat.isSymbolicLink()) throw new Error('Compatibility file must not be a link');
  return fs.readFile(file, 'utf8');
}

export async function repairGemini(root, {rollback = false, validateOnly = false, nodePath = process.execPath} = {}) {
  root = await fs.realpath(path.resolve(root));
  const pkg = JSON.parse(await regularFile(path.join(root, 'package.json')));
  if (pkg.name !== '@google/gemini-cli' || pkg.version !== '0.64.0') return {status: 'unsupported', version: pkg.version};
  const bundle = path.join(root, 'bundle');
  if ((await fs.lstat(bundle)).isSymbolicLink()) throw new Error('Gemini bundle must not be a link');
  const plans = [];
  let recognized = 0;
  for (const entry of (await fs.readdir(bundle, {withFileTypes: true})).sort((a,b) => a.name.localeCompare(b.name))) {
    if (!/^chunk-.*\.js$/.test(entry.name)) continue;
    const file = path.join(bundle, entry.name);
    const before = await regularFile(file);
    const backup = file + '.council-compat.bak', metadata = file + '.council-compat.json';
    if (rollback) {
      let record;
      try {record = JSON.parse(await regularFile(metadata));} catch (error) {if (error.code === 'ENOENT') continue; throw error;}
      const restored = await regularFile(backup);
      if (record.version !== pkg.version || hash(restored) !== record.before || hash(before) !== record.after) throw new Error('Compatibility rollback refused: bundle or backup changed');
      plans.push({file, before, after: restored, backup, metadata});
    } else if (before.includes(oldGuard) || before.includes(newGuard) || before.includes('fsSkills.realpathSync')) {
      const result = transformGeminiChunk(before); recognized++;
      plans.push({file, before, after: result.content, backup, metadata, changed: result.changed});
    }
  }
  if (!rollback && !recognized) throw new Error('No recognized Gemini skill implementation found');
  // Check all candidates, including existing repairs, before writing any package file.
  for (const plan of plans) {
    try {execFileSync(nodePath, ['--input-type=module', '--check'], {input: plan.after, stdio: ['pipe', 'pipe', 'pipe'], timeout: 30000});}
    catch {throw new Error('Gemini replacement failed JavaScript syntax check');}
    if (!rollback && plan.changed) for (const file of [plan.backup, plan.metadata]) {
      try {await fs.lstat(file); throw new Error('Existing compatibility backup requires reconciliation');}
      catch (error) {if (error.code !== 'ENOENT') throw error;}
    }
  }
  const changed = plans.filter(plan => rollback || plan.changed);
  if (validateOnly) {
    if (changed.length) throw new Error('Gemini compatibility repair is needed');
    return {status: 'verified', recognized};
  }
  const committed = [], created = [];
  try {
    for (const plan of changed) {
      if (await regularFile(plan.file) !== plan.before) throw new Error('Gemini bundle changed during staging');
      if (!rollback) {
        await fs.writeFile(plan.backup, plan.before, {flag: 'wx'}); created.push(plan.backup);
        await fs.writeFile(plan.metadata, JSON.stringify({version: pkg.version, before: hash(plan.before), after: hash(plan.after)}), {flag: 'wx'}); created.push(plan.metadata);
      }
    }
    for (const plan of changed) {committed.push(plan); await fs.writeFile(plan.file, plan.after);}
  } catch (error) {
    const recoveryErrors = [];
    for (const plan of committed.reverse()) {
      try {
        if (await regularFile(plan.file) !== plan.before) await fs.writeFile(plan.file, plan.before);
      } catch (recoveryError) { recoveryErrors.push(recoveryError); }
    }
    // External I/O failures can also block restoration. Retain recovery records in that case.
    if (recoveryErrors.length) throw new AggregateError([error, ...recoveryErrors], 'Gemini repair failed; recovery is incomplete and backups were retained');
    for (const file of created) await fs.unlink(file);
    throw error;
  }
  if (rollback) for (const plan of changed) {await fs.unlink(plan.backup); await fs.unlink(plan.metadata);}
  return {status: rollback ? 'restored' : changed.length ? 'repaired' : 'verified', recognized, changed: changed.length};
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [root, ...flags] = process.argv.slice(2);
  if (!root || flags.some(flag => !['--rollback', '--validate-only'].includes(flag))) {
    console.error('Usage: gemini-compat.mjs package-root [--rollback|--validate-only]'); process.exitCode = 1;
  } else repairGemini(root, {rollback: flags.includes('--rollback'), validateOnly: flags.includes('--validate-only')})
    .then(result => console.log(JSON.stringify(result)))
    .catch(error => {console.error(error.message); process.exitCode = 1;});
}
