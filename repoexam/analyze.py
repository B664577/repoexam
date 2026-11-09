"""仓库静态分析：定义、调用点、import 图、异常面、副作用。

这一层的产出就是卷子的标准答案，所以它必须**只报它确实看得见的东西**。
静态分析看不见反射调用、getattr 拼出来的名字、插件注册与运行时猴补丁 ——
看不见的一律不猜，并在成绩单上写明这条边界。
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

# 被当作副作用信号的调用名。宁可少报也不乱报：
# 这些名字出现不等于一定有副作用，所以成绩单上的措辞是「静态可见的副作用信号」。
SIDE_EFFECT_NAMES = {
    "写文件": {"open", "write", "write_text", "write_bytes", "mkdir",
               "makedirs", "remove", "unlink", "rename", "rmtree"},
    "联网": {"urlopen", "request", "get", "post", "connect", "socket"},
    "执行": {"system", "run", "Popen", "call", "check_output", "exec", "eval"},
}


@dataclass
class Sym:
    name: str
    file: str
    line: int
    kind: str                      # function | class
    raises: set[str] = field(default_factory=set)
    effects: set[str] = field(default_factory=set)
    uses_global: bool = False


@dataclass
class Repo:
    root: Path
    syms: dict[str, Sym] = field(default_factory=dict)
    calls: dict[str, set[str]] = field(default_factory=dict)   # 名字 → 调用它的文件集
    imports: dict[str, set[str]] = field(default_factory=dict)  # 模块 → 它 import 的模块
    files: list[str] = field(default_factory=list)


def _effects(node: ast.AST) -> tuple[set[str], set[str], bool]:
    raises: set[str] = set()
    effects: set[str] = set()
    uses_global = False
    for n in ast.walk(node):
        if isinstance(n, ast.Raise):
            e = n.exc
            if isinstance(e, ast.Call):
                e = e.func
            nm = getattr(e, "id", None) or getattr(e, "attr", None)
            if nm:
                raises.add(nm)
        elif isinstance(n, ast.Global):
            uses_global = True
        elif isinstance(n, ast.Call):
            nm = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
            for label, names in SIDE_EFFECT_NAMES.items():
                if nm in names:
                    effects.add(label)
    return raises, effects, uses_global


def scan(root: Path) -> Repo:
    r = Repo(root=root)
    for py in sorted(root.rglob("*.py")):
        if any(p in {"__pycache__", ".venv", "tests"} for p in py.parts):
            continue
        rel = py.relative_to(root).as_posix()
        r.files.append(rel)
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        mod = rel[:-3].replace("/", ".")
        r.imports.setdefault(mod, set())
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                raises, eff, g = _effects(n)
                kind = "class" if isinstance(n, ast.ClassDef) else "function"
                r.syms[n.name] = Sym(n.name, rel, n.lineno, kind, raises, eff, g)
            elif isinstance(n, ast.Call):
                nm = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
                if nm:
                    r.calls.setdefault(nm, set()).add(rel)
            elif isinstance(n, ast.Import):
                for al in n.names:
                    r.imports[mod].add(al.name.split(".")[0])
            elif isinstance(n, ast.ImportFrom):
                if n.module:
                    r.imports[mod].add(n.module.split(".")[0])
    return r


def callers(r: Repo, name: str) -> list[str]:
    """调用该符号的文件，排除它自己的定义文件里的递归调用点之外的噪声。"""
    return sorted(r.calls.get(name, set()))


def impact(r: Repo, name: str) -> list[str]:
    """改签名的静态可见影响面：调用点所在文件 + 定义所在文件。"""
    s = set(callers(r, name))
    if name in r.syms:
        s.add(r.syms[name].file)
    return sorted(s)


def depends(r: Repo, a: str, b: str) -> bool:
    """模块 a 是否（直接或间接）依赖 b。"""
    seen, stack = set(), [a]
    while stack:
        cur = stack.pop()
        if cur == b and cur != a:
            return True
        if cur in seen:
            continue
        seen.add(cur)
        for nxt in r.imports.get(cur, ()):
            if nxt == b:
                return True
            stack.append(nxt)
    return False
