import path from 'node:path';
import * as fs from 'node:fs/promises';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { installCouncil, validateCouncil, cleanupCouncilProjects } from './council-codex-lib.mjs';
import { handleHook, readStartupContext, validateStartupMode } from './council-memoryforge.mjs';
import { saveTask, selectTask, startFresh, setTaskStatus, suggestTasks, receiptPath } from './council-task-context.mjs';
import { executeIcm } from './council-icm.mjs';
import { finishDailyItem, dailyReviewPacket, recordDailyScreening, continueDailyScan, claimDaily } from './council-daily.mjs';
import { scanMainline, mainlinePacket, mainlineSource, finishMainline, mainlineStatus } from './council-mainline.mjs';
import { listProposals, reviewProposal, decideProposal, proposalStatus } from './council-proposals.mjs';
import {listPropagation,propagationStatus} from './council-propagation.mjs';

export async function executeCommand(args, { input = '' } = {}) {
  const [command, ...flags] = args;
  if (!['install', 'validate', 'onboard', 'hook', 'cleanup', 'tasks', 'icm','daily'].includes(command)) throw new Error('Usage: council-codex.mjs install|validate|onboard|hook|tasks|icm|daily [options]');
  const action = ['tasks','icm','daily'].includes(command) ? flags.shift() : null;
  const names = { '--startup-mode': 'startupMode', '--workspace': 'workspaceRoot', '--home': 'homeDir', '--username': 'username', '--payload': 'payloadRoot', '--node': 'nodePath', '--model': 'actor', '--memory-scope': 'memoryScope', '--session': 'session', '--chat': 'chat', '--cwd': 'cwd', '--project': 'project', '--record': 'recordPath', '--task': 'task', '--status': 'status', '--reason': 'reason', '--resume': 'resume', '--limit': 'limit' };
  const o = {};
  for (let i = 0; i < flags.length; i += 2) {
    const name = names[flags[i]];
    if (!name) throw new Error('Unknown option: ' + flags[i]);
    if (o[name] !== undefined) throw new Error('Duplicate option: ' + flags[i]);
    if (!flags[i + 1] || flags[i + 1].startsWith('--')) throw new Error('Missing option value: ' + flags[i]);
    o[name] = flags[i + 1];
  }
  if (o.startupMode !== undefined && !['onboard', 'hook'].includes(command)) throw new Error('Startup mode is only valid for onboard or hook');
  validateStartupMode(o);
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
  o.actor ||= 'codex';
  if (command === 'icm') return {exitCode:0,output:JSON.stringify(await executeIcm(action,o),null,2)};
  if (command === 'onboard' || command === 'tasks' || command === 'daily') {
    o.cwd ||= process.cwd();
    if (!o.chat && o.actor === 'codex') o.chat = process.env.CODEX_THREAD_ID || process.env.CODEX_SESSION_ID;
  }
  if(command==='daily'){
    const actions={claim:claimDaily,finish:finishDailyItem,packet:dailyReviewPacket,screen:recordDailyScreening,'mainline-scan':scanMainline,'mainline-packet':mainlinePacket,'mainline-source':mainlineSource,'mainline-finish':finishMainline,'mainline-status':mainlineStatus,'scan-documents':continueDailyScan,'proposal-list':listProposals,'proposal-review':reviewProposal,'proposal-decide':decideProposal,'proposal-status':proposalStatus,'propagation-list':listPropagation,'propagation-status':propagationStatus};
    if(!Object.hasOwn(actions,action)||!o.recordPath)throw Error('Use daily claim|finish|packet|screen|mainline-scan|mainline-packet|mainline-source|mainline-finish|mainline-status|scan-documents|proposal-list|proposal-review|proposal-decide|proposal-status|propagation-list|propagation-status --record PATH --chat ID');
    const stat=await fs.lstat(o.recordPath);if(!stat.isFile()||stat.isSymbolicLink()||stat.size>40000)throw Error('Invalid daily disposition file');
    const record=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(await fs.readFile(o.recordPath)));
    const execute=actions[action];
    return {exitCode:0,output:JSON.stringify(await execute(o,record),null,2)};
  }
  if (command === 'cleanup') return { exitCode: 0, output: JSON.stringify(await cleanupCouncilProjects(o), null, 2) };
  if (command === 'onboard') return { exitCode: 0, output: await readStartupContext(o) };
  if (command === 'tasks') {
    if (o.memoryScope && o.memoryScope !== 'legacy-shared') throw new Error('Task catalogue operations do not alter an explicit workspace-session namespace');
    let result;
    if (action === 'save') {
      if (!o.recordPath) throw new Error('tasks save requires --record path');
      const stat = await fs.stat(o.recordPath);
      if (!stat.isFile() || stat.size > 16000) throw new Error('Invalid task record file');
      let record;
      try { record = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(await fs.readFile(o.recordPath))); }
      catch { throw new Error('Invalid UTF-8 task record JSON; preserve the private file for review'); }
      result = await saveTask(o, record);
    } else if (action === 'select') result = await selectTask(o, o.task);
    else if (action === 'fresh') result = await startFresh(o);
    else if (action === 'status') {
      if (o.resume !== undefined && !['true', 'false'].includes(o.resume)) throw new Error('--resume must be true or false');
      result = await setTaskStatus(o, o.task, o.status, { reason: o.reason || '', resume: o.resume === 'true' });
    } else if (action === 'list') result = await suggestTasks({ ...o, limit: o.limit === undefined ? 3 : Number(o.limit) });
    else if (action === 'receipt') {
      const file = await receiptPath(o);
      try { result = JSON.parse(await fs.readFile(file, 'utf8')); }
      catch (error) { if (error.code !== 'ENOENT') throw error; result = { status: 'not-observed', receipt: file }; }
    } else throw new Error('Usage: tasks save|select|fresh|status|list|receipt');
    return { exitCode: 0, output: JSON.stringify(result, null, 2) };
  }
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
