import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveCalibratedTarget, preflightDom, detectBlockingState } from '../chrome_extension/lib/dom_adapter.js';

function el({ visible=true, disabled=false, text='', aria='', editable=false }={}) {
  return {
    disabled,
    innerText:text,
    textContent:text,
    isContentEditable: editable,
    getAttribute(name) {
      if (name === 'aria-label') return aria;
      if (name === 'contenteditable') return editable ? 'true' : null;
      return null;
    },
    getBoundingClientRect() { return visible ? { width:100, height:40, top:10, left:10, bottom:50, right:110 } : { width:0, height:0, top:0, left:0, bottom:0, right:0 }; }
  };
}

function doc(map={}, bodyText='') {
  return {
    body: { innerText: bodyText, textContent: bodyText },
    querySelectorAll(selector) { return map[selector] || []; }
  };
}

const calibration = {
  prompt: { selector: '#prompt' },
  generate: { selector: '#generate' }
};

test('fails when calibrated target has zero matches', () => {
  const result = resolveCalibratedTarget(doc({}), calibration.prompt, 'prompt');
  assert.equal(result.ok,false);
  assert.equal(result.errorCode,'PROMPT_NOT_FOUND');
});

test('fails when calibrated target has multiple visible matches', () => {
  const result = resolveCalibratedTarget(doc({'#prompt':[el({editable:true}),el({editable:true})]}), calibration.prompt, 'prompt');
  assert.equal(result.ok,false);
  assert.equal(result.errorCode,'PROMPT_AMBIGUOUS');
});

test('fails when generate target is disabled', () => {
  const result = resolveCalibratedTarget(doc({'#generate':[el({disabled:true})]}), calibration.generate, 'generate');
  assert.equal(result.ok,false);
  assert.equal(result.errorCode,'GENERATE_DISABLED');
});

test('preflight passes with exactly one visible prompt and enabled generate', () => {
  const d = doc({
    '#prompt':[el({editable:true})],
    '#generate':[el({disabled:false,text:'Generate'})]
  });
  assert.deepEqual(preflightDom(d, calibration), { ok:true, errors:[] });
});

test('detects login, captcha and quota blockers', () => {
  assert.equal(detectBlockingState(doc({}, 'Sign in to continue')), 'LOGIN_REQUIRED');
  assert.equal(detectBlockingState(doc({}, 'Verify you are human CAPTCHA')), 'CAPTCHA_REQUIRED');
  assert.equal(detectBlockingState(doc({}, 'You have no credits remaining')), 'QUOTA_EXHAUSTED');
  assert.equal(detectBlockingState(doc({}, 'All good')), null);
});
