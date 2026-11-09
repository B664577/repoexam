"""对外接口。注意 get 在这里被调用了两次，而 service.py 里还有第三次。"""
from store import get, load, save


def read_one(path: str, key: str):
    return get(load(path), key)


def read_two(path: str, k1: str, k2: str):
    d = load(path)
    return get(d, k1), get(d, k2)


def write(path: str, data: dict) -> None:
    save(path, data)
