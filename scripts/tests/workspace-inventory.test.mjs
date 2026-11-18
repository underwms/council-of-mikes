import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { discoverWorkspaceRepositories } from '../council-codex-lib.mjs';

test('Council discovers nested inventory repositories and preserves flat fallback',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'council-inventory-'));
 t.after(async()=>{assert.ok(path.basename(root).startsWith('council-inventory-'));await fs.rm(root,{recursive:true,force:true});});
 await fs.mkdir(path.join(root,'flat','.git'),{recursive:true});
 assert.deepEqual(await discoverWorkspaceRepositories(root),[path.join(root,'flat')]);
 const nested=path.join(root,'order-management','shipping','repos','sample');
 await fs.mkdir(path.join(nested,'.git'),{recursive:true});
 await fs.writeFile(path.join(root,'workspace-repositories.json'),JSON.stringify({schema_version:1,repositories:[{name:'sample',path:'order-management/shipping/repos/sample'}]}));
 assert.deepEqual(await discoverWorkspaceRepositories(root),[nested]);
 await fs.writeFile(path.join(root,'workspace-repositories.json'),JSON.stringify({schema_version:1,repositories:[{name:'escape',path:'../outside'}]}));
 await assert.rejects(discoverWorkspaceRepositories(root),/scope|path|workspace/i);
});
