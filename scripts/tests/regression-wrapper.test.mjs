import assert from 'node:assert/strict';
import test from 'node:test';
import { runTests } from './council-codex.test.mjs';

test('all existing installation and lifecycle regression scenarios', async () => {
  const report = await runTests();
  assert(report.total >= 40, 'Existing installation scenarios must not disappear');
  assert.equal(report.failed, 0, JSON.stringify(report.results.filter(result => result.status !== 'pass')));
});
