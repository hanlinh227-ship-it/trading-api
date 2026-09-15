import {validateLiveOverlay} from './model-mesh/canary-policy.js';

const envelope=JSON.parse(process.env.RESULT||'null');
const health=JSON.parse(process.env.HEALTH||'null');
const summary=validateLiveOverlay(envelope,health);
console.log(`MODEL_MESH_LIVE_OVERLAY=PASS active=${summary.activeCount}`);
