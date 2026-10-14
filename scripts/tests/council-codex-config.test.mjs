import assert from 'node:assert/strict';
import test from 'node:test';
import { mergeCodexDefaults } from '../council-codex-config.mjs';

const defaults = 'approval_policy = "on-request"\napprovals_reviewer = "auto_review"\nsandbox_mode = "workspace-write"\n';

test('Merge_PreservesCorrectScalarsCommentsAndMixedEndings', () => {
  const original = '\uFEFF"approval_policy" = \'on-request\' # approved\r\napprovals_reviewer="auto_review"\nsandbox_mode = "workspace-write"';

  assert.equal(mergeCodexDefaults(original, defaults), original);
});

test('Merge_PreservesMultilineSamplesArraysAndNestedOverrides', () => {
  const original = [
    'sample = """', 'approval_policy = "sample"', '[not.a.table]', '"""',
    "literal = '''", 'sandbox_mode = "sample"', "'''",
    'arguments = [', '  "approval_policy = sample", # retained', '  { name = "value" },', ']',
    '[mcp_servers.example]', 'command = "node --arg=\\"#quoted\\""',
    '[profiles.dev]', 'approval_policy = "never"', '',
  ].join('\n');

  assert.equal(mergeCodexDefaults(original, defaults), defaults + original);
});

test('Merge_PreservesExtraQuotesAtMultilineStringClosure', () => {
  const original = 'sample = """quoted content"""""\n';

  assert.equal(mergeCodexDefaults(original, defaults), defaults + original);
});

test('Merge_UpdatesLongUnicodeEscapedRootKey', () => {
  const original = '"\\U00000061pproval_policy" = "never"\n';

  assert.equal(mergeCodexDefaults(original, defaults), 'approvals_reviewer = "auto_review"\nsandbox_mode = "workspace-write"\n"\\U00000061pproval_policy" = "on-request"\n');
});

test('Merge_PreservesLiteralBackslashInUnrelatedQuotedKey', () => {
  const original = '"\\\\U00000061" = "value"\n';

  assert.equal(mergeCodexDefaults(original, defaults), defaults + original);
});

test('Merge_AddsKeysWithoutChangingBomOrLastLine', () => {
  const original = '\uFEFFmodel = "selected-model"';

  assert.equal(mergeCodexDefaults(original, defaults), '\uFEFF' + defaults + 'model = "selected-model"');
});

test('Merge_RejectsDuplicateLogicalKeys', () => {
  assert.throws(() => mergeCodexDefaults('approval_policy="never"\n"\\u0061pproval_policy"="never"\n', defaults), /duplicate.*approval_policy/i);
});

test('Merge_RejectsScopedOwnedKeys', () => {
  for (const original of ['approval_policy.granular = {}\n', '["\\u0061pproval_policy".granular]\n', '[[sandbox_mode]]\n']) {
    assert.throws(() => mergeCodexDefaults(original, defaults), /scoped/i);
  }
});

test('Merge_RejectsNonScalarOwnedValueWithoutLoggingIt', () => {
  assert.throws(() => mergeCodexDefaults('approval_policy={granular={private_marker=true}}\n', defaults), error => /single-line string/.test(error.message) && !error.message.includes('private_marker'));
});

test('Merge_RejectsIncompleteOrInvalidFragments', () => {
  assert.throws(() => mergeCodexDefaults('', 'approval_policy="on-request"\n'), /missing.*approvals_reviewer/i);
  assert.throws(() => mergeCodexDefaults('', defaults.replace('auto_review', 'private marker')), error => /invalid/i.test(error.message) && !error.message.includes('private marker'));
});

test('Merge_RejectsInvalidEnumInDefaultFragment', () => {
  assert.throws(() => mergeCodexDefaults('', defaults.replace('auto_review', 'auto_reveiw')), /invalid.*approvals_reviewer/i);
});

test('Merge_RejectsBrokenStringAndContainerBoundaries', () => {
  for (const original of ['model="unclosed\n', 'sample="""unclosed\n', 'array=["value"\n', 'array=[}\n']) {
    assert.throws(() => mergeCodexDefaults(original, defaults), /TOML/);
  }
});

test('Merge_RejectsInvalidQuotedKeyWithoutLoggingContents', () => {
  assert.throws(() => mergeCodexDefaults('"\\UFFFFFFFF"="private marker"\n', defaults), error => /quoted TOML key/.test(error.message) && !error.message.includes('private marker'));
});
