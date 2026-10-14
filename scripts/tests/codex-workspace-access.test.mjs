import assert from 'node:assert/strict';
import test from 'node:test';
import path from 'node:path';
import * as fs from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const module = await import('../council-codex-config.mjs');
const merge = (text, roots) => {
  assert.equal(typeof module.mergeCodexWorkspaceRoots, 'function', 'Council writable-root merger is required');
  return module.mergeCodexWorkspaceRoots(text, roots);
};

test('WorkspaceRoots_AddsCouncilTable_PreservesUnrelatedSettings', () => {
  const original = '\uFEFFmodel = "developer-model"\r\n[mcp_servers.example]\r\nurl = "https://example.test"\r\n';
  const merged = merge(original, ['C:\\Users\\Developer Name\\.council']);
  assert(merged.startsWith(original));
  assert(merged.includes('[sandbox_workspace_write]'));
  assert.equal(merge(merged, ['C:\\Users\\Developer Name\\.council']), merged);
});

test('WorkspaceRoots_UnionsMultilineArray_PreservesNetworkAndProfileOverrides', () => {
  const original = 'approval_policy = "on-request"\n[sandbox_workspace_write]\nnetwork_access = false\nwritable_roots = [\n  \'C:\\Existing\', # owned array comment\n  "D:/Another",\n]\n[profiles.locked]\nsandbox_mode = "read-only"\n';
  const merged = merge(original, ['C:\\New User\\.council']);
  assert(merged.includes('network_access = false'));
  assert(merged.includes('C:\\\\Existing'));
  assert(merged.endsWith('[profiles.locked]\nsandbox_mode = "read-only"\n'));
  assert.equal(merge(merged, ['c:/new user/.council']), merged);
});

test('WorkspaceRoots_RejectsAmbiguousAndMalformedOwnedSettings', () => {
  for (const original of [
    '[sandbox_workspace_write]\nwritable_roots = 7\n',
    '[sandbox_workspace_write]\nwritable_roots = []\nwritable_roots = []\n',
    '[sandbox_workspace_write]\n[sandbox_workspace_write]\n',
    '[sandbox_workspace_write.writable_roots]\n',
    'sandbox_workspace_write.writable_roots = []\n',
    'sandbox_workspace_write = { writable_roots = [] }\n',
    '[sandbox_workspace_write]\nwritable_roots = ["secret-private", 7]\n',
  ]) assert.throws(() => merge(original, ['C:/Council']), /sandbox|writable|TOML/i);
  assert.throws(() => merge('', ['relative']), /absolute/i);
  assert.equal(merge('model = "unchanged"\n', []), 'model = "unchanged"\n');
});

test('WorkspaceRoots_PreservesHashCharactersAndTrailingComments', () => {
  const original = '[sandbox_workspace_write]\nwritable_roots = ["C:/Directory#Name"] # keep comment\n';
  const merged = merge(original, ['C:/Council']);
  assert(merged.includes('C:/Directory#Name'));
  assert(merged.endsWith(' # keep comment\n'));
  assert.equal(merge(merged, ['C:/Council']), merged);
});

test('WorkspaceRoots_CompletesTableWithoutNewline_AndKeepsProfileOverrides', () => {
  const merged = merge('[sandbox_workspace_write]', ['C:/Council']);
  assert(merged.includes('[sandbox_workspace_write]\nwritable_roots = ["C:/Council"]\n'));
  const profile = '[profiles.custom.sandbox_workspace_write]\nwritable_roots = ["D:/Custom"]\n';
  assert(merge(profile, ['C:/Council']).startsWith(profile));
});

test('CLI_UsesInstallationMetadata_WhenInvokedWithoutFlags', async () => {
  const {executeCommand} = await import('../council-codex.mjs');
  let metadata;
  try {metadata = JSON.parse(await fs.readFile(path.join(root,'installation.json'),'utf8'));}
  catch (error) {if (error.code !== 'ENOENT') throw error;}
  if (metadata) {
    const result = await executeCommand(['validate']);
    assert.equal(result.exitCode,0,result.output);
    assert.equal(JSON.parse(result.output).placement.status,'pass');
  } else {
    await assert.rejects(executeCommand(['validate']),{code:'ENOENT'});
  }
});

test('Installer_DeclaresPortableCouncilAccess_AndNativeOnlyProvisioning', async () => {
  const descriptor = JSON.parse(await fs.readFile(path.join(root, 'adapters/codex.json'), 'utf8'));
  assert.deepEqual(descriptor.workspace_write_roots, ['council-root']);
  const setup = await fs.readFile(path.join(root, 'setup-council.ps1'), 'utf8');
  assert(setup.includes('[switch]$NativeOnly'));
});
