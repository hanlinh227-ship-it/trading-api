import assert from 'node:assert/strict';
import fs from 'node:fs';

const index=fs.readFileSync('index.js','utf8');
const prep=fs.readFileSync('prepare-wrangler.mjs','utf8');
const example=fs.readFileSync('wrangler.example.jsonc','utf8');
const batchState=fs.readFileSync('image-render/batch-state.js','utf8');

assert.match(index,/export \{ImageRenderBatchState\} from '\.\/image-render\/batch-state\.js'/);
assert.match(prep,/name:'IMAGE_RENDER_BATCH',class_name:'ImageRenderBatchState'/);
assert.match(prep,/tag:'image-render-batch-v1',new_sqlite_classes:\['ImageRenderBatchState'\]/);
assert.match(example,/"name"\s*:\s*"IMAGE_RENDER_BATCH"/);
assert.match(example,/"class_name"\s*:\s*"ImageRenderBatchState"/);
assert.match(example,/"tag"\s*:\s*"image-render-batch-v1"/);
assert.doesNotMatch(batchState,/TRADING_STATE/);
const cronBlocks=[...example.matchAll(/"crons"\s*:\s*\[([^\]]*)\]/g)];
assert.equal(cronBlocks.length,1,'image batch must not add another cron block');
assert.doesNotMatch(example,/image.*cron|cron.*image/i,'image rendering must use Durable Object alarms, not image crons');
console.log('IMAGE_RENDER_V2_DEPLOY_WIRING_TEST=PASS');
