"""工具自身的测试。跑法：python -m unittest discover -s tests

一张卷子最该被检查的三件事：
  · 答案是不是真的来自代码（而不是出题人的记忆）；
  · 答案有没有泄漏在卷子里；
  · 判卷是不是确定的（同样的作答必须得同样的分）。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from repoexam import analyze, exam  # noqa: E402

SRC = {
    "a.py": "def foo(x):\n    if x < 0:\n        raise ValueError('neg')\n    return x\n",
    "b.py": "from a import foo\n\n\ndef bar(y):\n    return foo(y) + foo(y + 1)\n",
    "c.py": "import json\nfrom pathlib import Path\n\n\ndef dump(p, d):\n"
            "    Path(p).write_text(json.dumps(d))\n",
}


def make_repo(tmp: Path) -> Path:
    for n, s in SRC.items():
        (tmp / n).write_text(s, encoding="utf-8")
    return tmp


class TestAnalyze(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.r = analyze.scan(make_repo(self.tmp))

    def test_定义位置来自代码(self):
        self.assertEqual(self.r.syms["foo"].file, "a.py")
        self.assertEqual(self.r.syms["bar"].file, "b.py")

    def test_调用点被完整找出(self):
        self.assertIn("b.py", analyze.callers(self.r, "foo"))

    def test_影响面含定义文件与调用文件(self):
        imp = analyze.impact(self.r, "foo")
        self.assertIn("a.py", imp)
        self.assertIn("b.py", imp)

    def test_异常面(self):
        self.assertIn("ValueError", self.r.syms["foo"].raises)

    def test_副作用信号(self):
        self.assertIn("写文件", self.r.syms["dump"].effects)

    def test_依赖方向有向(self):
        self.assertTrue(analyze.depends(self.r, "b", "a"))
        self.assertFalse(analyze.depends(self.r, "a", "b"))


class TestExam(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.r = analyze.scan(make_repo(self.tmp))
        self.paper, self.key = exam.build(self.r, 12, seed=7)

    def test_答案不在卷子里(self):
        blob = json.dumps(self.paper, ensure_ascii=False)
        for k in self.key["答案"]:
            std = k["标准答案"]
            if len(std) > 3 and std not in ("是", "否", "（空）"):
                self.assertNotIn(f'"{std}"', blob,
                                 "标准答案不得出现在卷子文件里")

    def test_全对即通过(self):
        ki = {k["id"]: k["标准答案"] for k in self.key["答案"]}
        for q in self.paper["题目"]:
            q["answer"] = ki[q["id"]]
        g = exam.grade(self.paper, self.key)
        self.assertTrue(g["通过"])
        self.assertEqual(g["得分率"], 1.0)

    def test_全空不通过(self):
        for q in self.paper["题目"]:
            q["answer"] = "（空）"
        g = exam.grade(self.paper, self.key)
        self.assertFalse(g["通过"])

    def test_判卷确定(self):
        ki = {k["id"]: k["标准答案"] for k in self.key["答案"]}
        for q in self.paper["题目"]:
            q["answer"] = ki[q["id"]]
        a = exam.grade(self.paper, self.key)
        b = exam.grade(self.paper, self.key)
        self.assertEqual(a["得分"], b["得分"], "同样的作答必须得同样的分")

    def test_答案被改动则拒绝判卷(self):
        self.key["答案"][0]["标准答案"] = "被改过的答案"
        with self.assertRaises(SystemExit):
            exam.grade(self.paper, self.key)

    def test_多选顺序无关(self):
        self.assertEqual(exam._norm("b.py｜a.py"), exam._norm("a.py｜b.py"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
