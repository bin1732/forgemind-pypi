/**
 * 门禁关卡的判据:拿合成状态双向验一遍。
 *
 * 判据错了,门禁就成了摆设 —— 门禁该拦的时候放行,比没有门禁更糟:
 * 流水线一片绿,发出去的东西没人验过。
 *
 * 用 node 自带的测试跑(仓库里的 UI 用 jest,这个不依赖任何包)。
 */
const test = require('node:test');
const assert = require('node:assert');

const { GATES, TEST_GATE, decide } = require('./gate_check.js');

function allGreen(extra = {}) {
  const state = {};
  for (const w of GATES) state[w] = 'success';
  return Object.assign(state, extra);
}

test('全绿就放行', () => {
  const v = decide(allGreen());
  assert.equal(v.ok, true, v.reason);
  assert.match(v.reason, /门禁全绿/);
});

test('有一档红了就不发布,并说清是哪一档', () => {
  const v = decide(allGreen({ 'ci-lint.yml': 'failure' }));
  assert.equal(v.ok, false);
  assert.match(v.reason, /ci-lint\.yml=failure/);
});

test('测试档没跑过就不发布', () => {
  const v = decide(allGreen({ [TEST_GATE]: 'not-started' }));
  assert.equal(v.ok, false);
  assert.match(v.reason, /测试档没有通过/);
});

test('测试档被取消也算没通过', () => {
  const v = decide(allGreen({ [TEST_GATE]: 'cancelled' }));
  assert.equal(v.ok, false);
  assert.match(v.reason, /测试档没有通过/);
});

test('其它档位被取消也要拦', () => {
  const v = decide(allGreen({ 'ci-ui.yml': 'cancelled' }));
  assert.equal(v.ok, false);
  assert.match(v.reason, /ci-ui\.yml=cancelled/);
});

test('其它档位被跳过也要拦', () => {
  const v = decide(allGreen({ 'ci-security.yml': 'skipped' }));
  assert.equal(v.ok, false);
  assert.match(v.reason, /ci-security\.yml=skipped/);
});

test('不适用于本次提交的档位不算红', () => {
  const v = decide(allGreen({ 'ci-ui.yml': 'not-applicable' }));
  assert.equal(v.ok, true, v.reason);
});

test('还在跑不算结论 —— 交回上层去等', () => {
  // decide 只在"都跑完了"之后调用;这里确认它不会把还在跑的当成绿。
  const v = decide(allGreen({ 'ci-ui.yml': 'in_progress' }));
  assert.equal(v.ok, false);
  assert.match(v.reason, /ci-ui\.yml=in_progress/);
});
