/**
 * JSX 里的注释不能被当文本渲染出来
 *
 * JSX 的子节点位置只认"花括号包起来的块注释"。写一行双斜杠注释在那儿,
 * 它会被当成**普通文本**渲染到界面上 —— 用户看到的是开发过程的说明,
 * 比如 K 线面板顶上那句 "1m / 5m / 15m / 1h 物理上拿不到"。
 *
 * 这类错编译得过、类型检查也过,只有真截图才看得见。所以这里拿
 * TypeScript 的 AST 把所有 JSXText 节点捞出来,凡是像注释的(以双斜杠
 * 开头或含块注释起始符)就报出来。
 */
import { readFileSync, readdirSync, statSync } from "fs";
import { join } from "path";
import * as ts from "typescript";

const UI = join(__dirname, "..", "..");

function walk(dir: string, out: string[] = []): string[] {
  for (const f of readdirSync(dir)) {
    if (f === "node_modules" || f === ".next" || f === "out" || f === "__tests__") continue;
    const p = join(dir, f);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (f.endsWith(".tsx")) out.push(p);
  }
  return out;
}

/** 界面上会被渲染出来的、长得像注释的文本 */
function leakedComments(file: string): { line: number; text: string }[] {
  const src = ts.createSourceFile(
    file,
    readFileSync(file, "utf8"),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const found: { line: number; text: string }[] = [];
  const visit = (node: ts.Node): void => {
    if (ts.isJsxText(node)) {
      const text = node.text.trim();
      // JSXText 里出现的注释痕迹:行首 // 或块注释起始
      if (text.startsWith("//") || text.includes("/*")) {
        const { line } = src.getLineAndCharacterOfPosition(node.getStart());
        found.push({ line: line + 1, text });
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(src);
  return found;
}

describe("JSX 注释不能漏到界面上", () => {
  const files = [
    ...walk(join(UI, "app")),
    ...walk(join(UI, "components")),
    ...walk(join(UI, "lib")),
  ];

  it("扫得到界面文件", () => {
    expect(files.length).toBeGreaterThan(5);
  });

  it("没有把注释当文本渲染出来", () => {
    const problems: string[] = [];
    for (const file of files) {
      for (const leak of leakedComments(file)) {
        problems.push(`${file.replace(UI + "/", "")}:${leak.line} ${leak.text.slice(0, 80)}`);
      }
    }
    expect(problems).toEqual([]);
  });

  it("检查器本身能抓到问题", () => {
    // 拿一个已知会漏的写法验证: JSX 子节点里的 // 注释
    const sample = `
      export function Demo() {
        return (
          <div>
            // 这行会被当文本渲染
            <span>hi</span>
          </div>
        );
      }
    `;
    const file = join(UI, "components", "__jsx_leak_probe__.tsx");
    const src = ts.createSourceFile(
      file,
      sample,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    );
    const texts: string[] = [];
    const visit = (node: ts.Node): void => {
      if (ts.isJsxText(node)) texts.push(node.text.trim());
      ts.forEachChild(node, visit);
    };
    visit(src);
    expect(texts.some((t) => t.startsWith("//"))).toBe(true);
  });
});
