/**
 * 发布前的一道关:门禁没绿,就不发布。
 *
 * 以前没有这道关:门禁那几档与发布是并行的,门禁红了照样发 ——
 * 实测过:一次提交的 lint 与测试都红了,发布照样完成,用户装到的是一个
 * 没验过的版本,而流水线上一半是绿的。
 *
 * 门禁那几档的触发条件与发布完全一致(都只对 main 的推送、都忽略
 * releases/ 与 pypi/),所以它们一定会有一次运行。发布的构件在等门禁的
 * 这段时间里已经构建好了,多出来的等待大多是并行的那部分 —— 慢的
 * 那一档说了算。
 *
 * 这个文件只管"结论怎么算",不管"怎么问":问的那部分在 workflow 里,
 * 结论这部分在这里,可以单独验。
 */

/** 要等的门禁档位(工作流文件名)。测试档单独挑出来:它是"这次提交验过了"的唯一凭据。 */
const GATES = ['ci-security.yml', 'ci-tests.yml', 'ci-ui.yml', 'ci-lint.yml'];
const TEST_GATE = 'ci-tests.yml';

/** 还没跑完的状态。 */
const PENDING = ['not-started', 'queued', 'in_progress', 'waiting', 'requested', 'pending'];
/** 跑完了但不算绿的状态。 */
const NOT_GREEN = ['failure', 'cancelled', 'skipped'];

/**
 * 按各档的状态算结论。
 *
 * @param {Record<string, string>} state 各档的结论或状态
 * @returns {{ok: boolean, reason: string}} 能不能发布,以及不能的话为什么
 */
function decide(state) {
  const test = state[TEST_GATE];
  if (test !== 'success') {
    return {
      ok: false,
      reason:
        `测试档没有通过(${TEST_GATE}=${test}),这次不发布 —— ` +
        '发布出去的版本必须是门禁绿过的那个版本',
    };
  }
  const bad = GATES.filter((w) => {
    const s = state[w];
    if (s === 'success') return false;
    if (s === 'not-applicable') return false;
    return true;
  });
  if (bad.length) {
    const detail = bad.map((w) => `${w}=${state[w]}`).join(' ');
    return { ok: false, reason: `门禁没绿,这次不发布:${detail}` };
  }
  return { ok: true, reason: '门禁全绿,继续发布' };
}

/**
 * 等门禁跑完,再问结论。
 *
 * @param {{github: any, context: any, core: any}} io github-script 给的三样东西
 */
async function run({ github, context, core }) {
  const deadline = Date.now() + 45 * 60 * 1000;
  const grace = 5 * 60 * 1000;
  const started = Date.now();
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  let state = {};
  while (Date.now() < deadline) {
    const { data } = await github.rest.actions.listWorkflowRuns({
      owner: context.repo.owner,
      repo: context.repo.repo,
      branch: context.ref.replace('refs/heads/', ''),
      per_page: 30,
    });
    state = {};
    for (const wf of GATES) {
      const hit = data.workflow_runs.find(
        (r) => r.path.endsWith(wf) && r.head_sha === context.sha,
      );
      state[wf] = hit ? hit.conclusion || hit.status : 'not-started';
    }
    // 等了五分钟还没出现,就不是"还没开始",而是这次提交压根不触发它 ——
    // 当作不适用,别把发布卡死在这儿。
    if (Date.now() - started > grace) {
      for (const wf of GATES) {
        if (state[wf] === 'not-started') state[wf] = 'not-applicable';
      }
    }
    core.info(`门禁状态:${GATES.map((w) => `${w}=${state[w]}`).join(' ')}`);
    const pending = GATES.filter(
      (w) => PENDING.includes(state[w]) && state[w] !== 'not-applicable',
    );
    if (pending.length === 0) break;
    await sleep(30000);
  }

  const verdict = decide(state);
  if (!verdict.ok) {
    core.setFailed(verdict.reason);
    return;
  }
  core.info(verdict.reason);
}

module.exports = { GATES, TEST_GATE, PENDING, NOT_GREEN, decide, run };
