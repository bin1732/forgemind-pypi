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

// ===== 跑起来的那一段:API 调对了没有 =====
//
// 只测 decide() 不够:判据对了,但 API 调错方法名,门禁照样是坏的。
// 这里用 mock 驱动一遍 run(),盯住两件事:用的是"整个仓的运行"那个接口,
// 以及结论怎么落到 core.setFailed。
const { run } = require('./gate_check.js');

function mockIo(conclusions, sha = 'abc123') {
  const paths = {
    'ci-security.yml': '.github/workflows/ci-security.yml',
    'ci-tests.yml': '.github/workflows/ci-tests.yml',
    'ci-ui.yml': '.github/workflows/ci-ui.yml',
    'ci-lint.yml': '.github/workflows/ci-lint.yml',
  };
  const runs = Object.entries(paths).map(([file, path]) => ({
    path,
    head_sha: sha,
    conclusion: conclusions[file],
    status: conclusions[file] ? 'completed' : 'in_progress',
  }));
  const failures = [];
  const io = {
    github: {
      rest: {
        actions: {
          // 整个仓的运行:listWorkflowRunsForRepo。
          // listWorkflowRuns 是"按某个工作流列",少了 workflow_id 会拼出
          // /actions/workflows//runs,平台回 404 —— 门禁当场失败。
          listWorkflowRunsForRepo: async () => ({ data: { workflow_runs: runs } }),
          listWorkflowRuns: async () => {
            throw new Error(
              '用错了接口:listWorkflowRuns 需要 workflow_id,不给会拼出 /workflows//runs'
            );
          },
        },
      },
    },
    context: { repo: { owner: 'bin1732', repo: 'forgemind-pypi' }, sha, ref: 'refs/heads/main' },
    core: {
      info: () => {},
      setFailed: (msg) => failures.push(msg),
    },
  };
  return { io, failures };
}

test('run 用的是整个仓的运行那个接口', async () => {
  const { io, failures } = mockIo({
    'ci-security.yml': 'success',
    'ci-tests.yml': 'success',
    'ci-ui.yml': 'success',
    'ci-lint.yml': 'success',
  });
  await run(io, { graceMs: 0, deadlineMs: 1000, sleepMs: 1 });
  assert.deepEqual(failures, [], failures.join('\n'));
});

test('run 遇到红的门禁会拦下发布,并说清是哪一档', async () => {
  const { io, failures } = mockIo({
    'ci-security.yml': 'success',
    'ci-tests.yml': 'success',
    'ci-ui.yml': 'success',
    'ci-lint.yml': 'failure',
  });
  await run(io, { graceMs: 0, deadlineMs: 1000, sleepMs: 1 });
  assert.equal(failures.length, 1, failures.join('\n'));
  assert.match(failures[0], /ci-lint\.yml=failure/);
});

test('run 遇到没跑过的测试档会拦下发布', async () => {
  const { io, failures } = mockIo({
    'ci-security.yml': 'success',
    'ci-tests.yml': 'success',
    'ci-ui.yml': 'success',
    'ci-lint.yml': 'success',
  });
  io.github.rest.actions.listWorkflowRunsForRepo = async () => ({
    data: { workflow_runs: [] },
  });
  await run(io, { graceMs: 0, deadlineMs: 1000, sleepMs: 1 });
  assert.equal(failures.length, 1, failures.join('\n'));
  assert.match(failures[0], /测试档没有通过/);
});
