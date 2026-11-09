"""第三处调用点——最容易被漏掉的那一个。"""
from store import get, warm


def bootstrap(path: str, key: str):
    warm(path)
    from store import _CACHE
    return get(_CACHE, key)
