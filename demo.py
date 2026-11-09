"""一条命令跑完整演示：出一张卷子，让三位考生作答，分别判卷。

三位考生刻意设计成三种真实的失败方式：

  全对的　　　　每题照代码事实作答　　　　　　　　　　→ 通过
  只会背文件名　定义位置全对，影响面与调用点靠猜　　　→ 未达线
  瞎猜的　　　　一律填「（空）」或「是」　　　　　　　→ 未达线

第二位是最值得看的一种：它看起来"熟悉这个仓库"（文件名都说得出来），
但一问到"改了会牵动谁"就露馅——而那恰恰是让 AI 动手前最该确认的事。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAM = HERE / "exam"


def run(args: list[str]) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "repoexam", *args],
                       cwd=HERE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def answer(paper: dict, key: dict, style: str) -> dict:
    """按考生类型填 answer 字段。"""
    ki = {k["id"]: k for k in key["答案"]}
    p = json.loads(json.dumps(paper, ensure_ascii=False))
    for q in p["题目"]:
        std = ki[q["id"]]["标准答案"]
        if style == "full":
            q["answer"] = std
        elif style == "filename":
            # 只记得住文件在哪；一问影响面与调用点就只敢说定义文件
            q["answer"] = std if q["类型"] in ("定义位置", "异常面") else (
                std.split("｜")[0] if q["类型"] in ("调用点", "影响面") else "是")
        else:
            q["answer"] = "是" if q["类型"] == "依赖方向" else "（空）"
    return p


def main() -> int:
    bar = "=" * 78
    print(bar); print("第 1 步　从演示仓库出一张卷子"); print(bar)
    code, out = run(["make", "--repo", "demo_repo", "--out", "exam", "--n", "14"])
    print(out.rstrip())
    if code != 0:
        return code

    paper = json.loads((EXAM / "卷子.json").read_text(encoding="utf-8"))
    key = json.loads((EXAM / "答案.json").read_text(encoding="utf-8"))

    for tag, style, want in (("考生甲：照代码事实作答", "full", 0),
                             ("考生乙：只会背文件名", "filename", 5),
                             ("考生丙：一律空着或瞎猜", "guess", 5)):
        print("\n" + bar); print(f"第 2 步　{tag}"); print(bar)
        f = EXAM / f"卷子_{style}.json"
        f.write_text(json.dumps(answer(paper, key, style), ensure_ascii=False,
                                indent=1), encoding="utf-8")
        code, out = run(["grade", "--exam", str(f.relative_to(HERE)),
                         "--key", "exam/答案.json"])
        print(out.rstrip())
        print(f"\n[退出码 {code}　预期 {want}　"
              + ("符合" if code == want else "**不符**") + "]")

    print("\n" + bar)
    print("考不过的不许改代码——这张卷子的全部用处就在这一句上。")
    print("注意考生乙：它说得出每个文件在哪，但一问「改了会牵动谁」就露馅，")
    print("而那恰恰是让它动手之前最该确认的事。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
