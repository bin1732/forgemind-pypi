"""检查 workflow:凡是用到 bash 专有语法的 step,必须声明 shell: bash"""
import pathlib, re, sys
bad = []
for wf in sorted(pathlib.Path(".github/workflows").glob("*.yml")):
    text = wf.read_text()
    # 按 step 切块
    for m in re.finditer(r"^      - (name|uses):.*?(?=^      - (?:name|uses):|\Z)",
                         text, re.S | re.M):
        blk = m.group(0)
        if "run: |" not in blk: continue
        # bash 专有语法
        uses_bash = bool(re.search(r"set -euo pipefail|\[\[|PIPESTATUS|shopt -s|\$\(\(|&>/dev/null|timeout \d+ ", blk))
        has_shell = "shell: bash" in blk
        if uses_bash and not has_shell:
            name = re.search(r"name: (.+)", blk)
            bad.append(f"{wf.name} / {name.group(1) if name else '?'}")
print(f"检查 {len(list(pathlib.Path('.github/workflows').glob('*.yml')))} 个 workflow")
if bad:
    print("以下 step 用了 bash 语法但没声明 shell: bash:")
    for b in bad: print("  ✗", b)
    sys.exit(1)
print("✓ 全部 bash 步骤都已声明 shell: bash")
