import test from 'node:test';
import assert from 'node:assert/strict';
import { preflightRender, executeRenderCurrent, captureCompletionSnapshot, detectCompletionSignal } from '../chrome_extension/lib/executor.js';

function promptEl() {
  return {
    value:'',
    isContentEditable:false,
    events:[],
    focus(){},
    dispatchEvent(evt){ this.events.push(evt.type); }
  };
}
function buttonEl() {
  return { clicks:0, disabled:false, click(){ this.clicks += 1; } };
}

const baseCommand = {
  command_id:'flow-scene24-1',
  action:'render',
  project_url:'https://labs.google/fx/tools/flow/project',
  scene:24,
  prompt:'gentle animation',
  duration_seconds:8,
  aspect_ratio:'16:9',
  start_image:{mode:'current'},
  end_image:{mode:'none'},
  retry:{max_attempts:1}
};

test('preflight accepts current start image and none end image', () => {
  const result = preflightRender(baseCommand, { href:baseCommand.project_url, blockingState:null }, {
    prompt:{ok:true,element:promptEl()}, generate:{ok:true,element:buttonEl()}
  });
  assert.equal(result.ok,true);
  assert.deepEqual(result.errors,[]);
});

test('preflight fails closed for local_file and remote_url modes in v0.3 acceptance implementation', () => {
  for (const mode of ['local_file','remote_url']) {
    const result = preflightRender({...baseCommand,start_image:{mode}}, { href:baseCommand.project_url, blockingState:null }, {
      prompt:{ok:true,element:promptEl()}, generate:{ok:true,element:buttonEl()}
    });
    assert.equal(result.ok,false);
    assert.match(result.errors.join('\n'), /ASSET_MODE_UNSUPPORTED/);
  }
});

test('execute fills prompt and clicks Generate exactly once', async () => {
  const p = promptEl();
  const g = buttonEl();
  const result = await executeRenderCurrent(baseCommand,{prompt:p,generate:g});
  assert.equal(result.submitted,true);
  assert.equal(p.value,'gentle animation');
  assert.equal(g.clicks,1);
  assert.ok(p.events.includes('input'));
});

test('execute does not click when required targets are absent', async () => {
  const g = buttonEl();
  await assert.rejects(() => executeRenderCurrent(baseCommand,{prompt:null,generate:g}),/PROMPT_TARGET_MISSING/);
  assert.equal(g.clicks,0);
});

function resultDoc({downloads=[], videos=[]}={}) {
  return {
    querySelectorAll(selector) {
      if (selector === '.download') return downloads;
      if (selector === 'video[src]') return videos.map(src => ({ src }));
      return [];
    }
  };
}

test('detects a newly appeared calibrated download control as completion evidence', () => {
  const before = captureCompletionSnapshot(resultDoc({downloads:[{}]}), {selector:'.download'});
  const after = captureCompletionSnapshot(resultDoc({downloads:[{},{}]}), {selector:'.download'});
  assert.equal(detectCompletionSignal(before, after), 'download');
});

test('detects a new video src as completion evidence', () => {
  const before = captureCompletionSnapshot(resultDoc({videos:['https://x/old.mp4']}), null);
  const after = captureCompletionSnapshot(resultDoc({videos:['https://x/old.mp4','https://x/new.mp4']}), null);
  assert.equal(detectCompletionSignal(before, after), 'video');
});

test('does not claim completion without a new observable result', () => {
  const before = captureCompletionSnapshot(resultDoc({downloads:[{}],videos:['https://x/a.mp4']}), {selector:'.download'});
  const after = captureCompletionSnapshot(resultDoc({downloads:[{}],videos:['https://x/a.mp4']}), {selector:'.download'});
  assert.equal(detectCompletionSignal(before, after), null);
});
