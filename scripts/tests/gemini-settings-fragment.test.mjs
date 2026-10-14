import assert from 'node:assert/strict';
import test from 'node:test';
import path from 'node:path';
import {mergeGeminiSettings} from '../council-codex-lib.mjs';

test('GeminiSettings_UsesCentralFragment_PreservesUserValuesAndDeduplicatesPaths', () => {
  const options = {councilRoot: path.resolve('Council Fixture')};
  const additional = path.join(options.councilRoot,'exclusions/additional.ignore');
  const fragment = {context:{fileFiltering:{respectGeminiIgnore:false,customIgnoreFilePaths:[additional,additional]}}};
  const original = {security:{retain:true},context:{fileFiltering:{respectGeminiIgnore:true,customIgnoreFilePaths:['D:/Existing']}}};
  const merged = mergeGeminiSettings(original,options,fragment);
  assert(merged.context.fileFiltering.customIgnoreFilePaths.includes(additional));
  assert.equal(merged.context.fileFiltering.customIgnoreFilePaths.filter(value=>value===additional).length,1);
  assert.equal(merged.context.fileFiltering.respectGeminiIgnore,true);
  assert.deepEqual(merged.security,original.security);
  assert.equal(mergeGeminiSettings({},options,fragment).context.fileFiltering.respectGeminiIgnore,false);
  assert.deepEqual(mergeGeminiSettings(merged,options,fragment),merged);
  assert.deepEqual(original.context.fileFiltering.customIgnoreFilePaths,['D:/Existing']);
});

test('GeminiSettings_RejectsMalformedCentralFragment_BeforeNativeWrites', () => {
  const options = {councilRoot:path.resolve('Council Fixture')};
  for(const fragment of [{context:{fileFiltering:{customIgnoreFilePaths:7}}},{context:{fileFiltering:{customIgnoreFilePaths:[42]}}},{context:{fileFiltering:{respectGeminiIgnore:'yes'}}}]) {
    assert.throws(()=>mergeGeminiSettings({},options,fragment),/fragment/i);
  }
});
