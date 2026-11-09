"""出卷、判卷、成绩单。

出卷时**答案不写进卷子**：卷子与答案分成两个文件，
答案文件带哈希，交卷后才用它判分。否则这张卷子一文不值。
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .analyze import Repo, callers, depends, impact

BJ = timezone(timedelta(hours=8))
PASS, FAIL = 0, 5

# 每类题的分值。影响面与副作用给得高，因为它们正是「没读懂就动手」的事故源头。
WEIGHT = {"定义位置": 1.0, "调用点": 1.5, "影响面": 2.0,
          "依赖方向": 1.0, "异常面": 1.5, "副作用": 2.0}
PASS_LINE = 0.75


def _fmt(v) -> str:
    if isinstance(v, (list, set, tuple)):
        return "｜".join(sorted(str(x) for x in v)) or "（空）"
    return str(v)


def build(r: Repo, n: int, seed: int = 0) -> tuple[dict, dict]:
    rng = random.Random(seed)
    names = [s for s in sorted(r.syms) if not s.startswith("_")]
    mods = sorted(r.imports)
    qs, key = [], []

    def add(kind: str, q: str, ans, hint: str = ""):
        i = len(qs) + 1
        qs.append({"id": i, "类型": kind, "题目": q, "作答格式": hint, "answer": ""})
        key.append({"id": i, "类型": kind, "标准答案": _fmt(ans)})

    pool = []
    for nm in names:
        s = r.syms[nm]
        pool += [
            ("定义位置", f"符号 `{nm}` 定义在哪个文件？", s.file, "填相对路径"),
            ("调用点", f"哪些文件里调用了 `{nm}`？", callers(r, nm),
             "多个用｜分隔，无则填「（空）」"),
            ("影响面", f"若修改 `{nm}` 的签名，静态可见地会牵动哪些文件？",
             impact(r, nm), "多个用｜分隔"),
            ("异常面", f"`{nm}` 内部可能抛出哪些异常类型？", s.raises,
             "多个用｜分隔，无则填「（空）」"),
            ("副作用", f"`{nm}` 有哪些静态可见的副作用信号"
                       f"（写文件／联网／执行）？", s.effects,
             "多个用｜分隔，无则填「（空）」"),
        ]
    for a in mods:
        for b in mods:
            if a != b:
                pool.append(("依赖方向", f"模块 `{a}` 是否（直接或间接）依赖 `{b}`？",
                             "是" if depends(r, a, b) else "否", "填 是 或 否"))

    rng.shuffle(pool)
    # 每类至少一题，再按比例补足
    seen_kind: set[str] = set()
    ordered = [p for p in pool if not (p[0] in seen_kind or seen_kind.add(p[0]))]
    ordered += [p for p in pool if p not in ordered]
    for kind, q, ans, hint in ordered[:n]:
        add(kind, q, ans, hint)

    kjson = json.dumps(key, ensure_ascii=False, sort_keys=True)
    paper = {
        "仓库": r.root.name, "题数": len(qs), "出卷时间（北京）":
            datetime.now(BJ).isoformat(timespec="seconds"),
        "随机种子": seed,
        "答案指纹": hashlib.sha256(kjson.encode("utf-8")).hexdigest(),
        "说明": ["答案不在本文件里。把每题的 answer 字段填好后交卷。",
                 "多选题用｜分隔；没有则填「（空）」。"],
        "题目": qs,
    }
    return paper, {"答案指纹": paper["答案指纹"], "答案": key}


def grade(paper: dict, key: dict) -> dict:
    kjson = json.dumps(key["答案"], ensure_ascii=False, sort_keys=True)
    if hashlib.sha256(kjson.encode("utf-8")).hexdigest() != key["答案指纹"]:
        raise SystemExit("答案文件指纹不符，已被改动过，拒绝判卷。")
    if paper.get("答案指纹") != key["答案指纹"]:
        raise SystemExit("卷子与答案不配对，拒绝判卷。")

    ki = {k["id"]: k for k in key["答案"]}
    per: dict[str, list[int]] = {}
    rows, got, full = [], 0.0, 0.0
    for q in paper["题目"]:
        k = ki.get(q["id"])
        if not k:
            continue
        w = WEIGHT.get(q["类型"], 1.0)
        full += w
        a = _norm(q.get("answer", ""))
        b = _norm(k["标准答案"])
        ok = a == b
        got += w if ok else 0.0
        per.setdefault(q["类型"], [0, 0])
        per[q["类型"]][1] += 1
        per[q["类型"]][0] += 1 if ok else 0
        rows.append({"id": q["id"], "类型": q["类型"], "题目": q["题目"],
                     "作答": q.get("answer", ""), "标准答案": k["标准答案"],
                     "对": ok, "分值": w})
    rate = got / full if full else 0.0
    return {
        "仓库": paper.get("仓库"), "题数": len(rows),
        "得分": round(got, 2), "满分": round(full, 2), "得分率": round(rate, 4),
        "通过线": PASS_LINE, "通过": rate >= PASS_LINE,
        "分类": {k: {"对": v[0], "共": v[1]} for k, v in sorted(per.items())},
        "明细": rows,
        "边界": [
            "静态分析看不见反射调用、getattr 拼出的名字、插件注册与运行时猴补丁；"
            "因此「影响面」是静态可见的影响面，不是全部影响面。",
            "考过不等于会改：本卷量的是读懂了多少，不是改得对不对。",
        ],
    }


def _norm(s: str) -> str:
    s = (s or "").strip()
    if s in ("", "（空）", "()", "无", "none", "None"):
        return ""
    return "｜".join(sorted(x.strip() for x in s.replace("|", "｜").split("｜")
                            if x.strip()))


def render(g: dict) -> str:
    L = [f"仓库带背·成绩单　{g['仓库']}",
         f"得分 {g['得分']}／{g['满分']}　得分率 {g['得分率']:.1%}　"
         f"通过线 {g['通过线']:.0%}　→　"
         + ("**通过，允许改代码**" if g["通过"] else "**未达线，不允许改代码**"),
         ""]
    L.append(f"{'题型':<10}{'对':>5}{'共':>5}   薄弱处")
    L.append("─" * 58)
    for k, v in g["分类"].items():
        weak = "" if v["对"] == v["共"] else "  ←"
        L.append(f"{k:<10}{v['对']:>5}{v['共']:>5}{weak}")
    wrong = [r for r in g["明细"] if not r["对"]]
    if wrong:
        L += ["", f"错题 {len(wrong)} 道："]
        for r in wrong[:10]:
            L.append(f"  #{r['id']}　[{r['类型']}] {r['题目']}")
            L.append(f"      作答 {r['作答']!r}")
            L.append(f"      标准 {r['标准答案']!r}")
    else:
        L += ["", "全对。"]
    L += ["", "边界："]
    for b in g["边界"]:
        L.append("  · " + b)
    return "\n".join(L)
