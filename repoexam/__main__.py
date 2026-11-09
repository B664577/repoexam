"""repoexam 命令行入口。

    python -m repoexam make  --repo <仓库> --out <目录> [--n 20] [--seed 0]
    python -m repoexam grade --exam <卷子.json> --key <答案.json>

退出码：0 通过（允许改代码）　5 未达线（不允许）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import analyze, exam


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="repoexam", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["make", "grade"])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default="exam")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--exam", default="exam/卷子.json")
    ap.add_argument("--key", default="exam/答案.json")
    a = ap.parse_args(argv)

    if a.cmd == "make":
        r = analyze.scan(Path(a.repo).resolve())
        if not r.syms:
            print("这个仓库里没扫到任何函数或类定义。", file=sys.stderr)
            return 1
        paper, key = exam.build(r, a.n, a.seed)
        out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
        (out / "卷子.json").write_text(
            json.dumps(paper, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / "答案.json").write_text(
            json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
        kinds = {}
        for q in paper["题目"]:
            kinds[q["类型"]] = kinds.get(q["类型"], 0) + 1
        print(f"已出卷 {paper['题数']} 题 → {out/'卷子.json'}")
        print("  题型分布：" + "　".join(f"{k} {v}" for k, v in sorted(kinds.items())))
        print(f"  答案另存 {out/'答案.json'}　指纹 {paper['答案指纹'][:16]}…")
        print("  答案不在卷子里——否则这张卷子一文不值。")
        return 0

    paper = json.loads(Path(a.exam).read_text(encoding="utf-8"))
    key = json.loads(Path(a.key).read_text(encoding="utf-8"))
    g = exam.grade(paper, key)
    Path(a.exam).with_name("成绩单.json").write_text(
        json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
    print(exam.render(g))
    return exam.PASS if g["通过"] else exam.FAIL


if __name__ == "__main__":
    sys.exit(main())
