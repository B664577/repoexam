"""演示仓库：一个很小的键值存储。有意留了一个容易被漏掉的调用点。"""
import json
from pathlib import Path

_CACHE = {}


class KeyMissing(Exception):
    pass


def load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise KeyMissing(f"{path} 不存在")
    return json.loads(p.read_text(encoding="utf-8"))


def save(path: str, data: dict) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def get(data: dict, key: str):
    if key not in data:
        raise KeyMissing(key)
    return data[key]


def warm(path: str) -> None:
    global _CACHE
    _CACHE = load(path)
