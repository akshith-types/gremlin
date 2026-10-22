from __future__ import annotations

import json
import operator
from dataclasses import dataclass
from typing import Callable, Union

from .tac import CONCAT, STR_CONST, Instr, Op, is_const

Value = Union[int, str, list[int]]


class _Undefined(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class _Trap(Exception):
    """A runtime fault in the executed program (bad index, type confusion, ...)."""


def _tdiv(a: int, b: int) -> int:
    """C-style truncating division (round toward zero), immune to float overflow."""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


_BINOPS: dict[str, Callable[[int, int], int]] = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
}
_INT_RELOPS: dict[str, Callable[[int, int], bool]] = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}
_STR_RELOPS: dict[str, Callable[[str, str], bool]] = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}


def show(value: Value) -> str:
    """Canonical printed form: 5, "text", [1,2,3]."""
    if isinstance(value, list):
        return "[" + ",".join(str(v) for v in value) + "]"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _kind(v: Value) -> str:
    return "array" if isinstance(v, list) else "string" if isinstance(v, str) else "int"


@dataclass(frozen=True)
class RunResult:
    output: tuple[str, ...]
    env: dict[str, Value]
    trap: str | None


def run(tac: tuple[Instr, ...], max_steps: int) -> RunResult:
    """Total function: every possible execution path returns a RunResult.
    Nothing escapes as an uncaught exception."""
    label_pos: dict[str, int] = {}
    for pos, ins in enumerate(tac):
        if ins.op == Op.LABEL and ins.arg1 is not None:
            label_pos[ins.arg1] = pos

    env: dict[str, Value] = {}
    out: list[str] = []

    def resolve(name: str) -> Value:
        if is_const(name):
            return int(name)
        if name in env:
            return env[name]
        raise _Undefined(name)

    def as_int(name: str, at: int) -> int:
        v = resolve(name)
        if isinstance(v, bool) or not isinstance(v, int):
            raise _Trap(f"expected an int in '{name}' but found a {_kind(v)} at instruction {at}")
        return v

    def as_str(name: str, at: int) -> str:
        v = resolve(name)
        if not isinstance(v, str):
            raise _Trap(f"expected a string in '{name}' but found a {_kind(v)} at instruction {at}")
        return v

    def snapshot() -> dict[str, Value]:
        return {k: (list(v) if isinstance(v, list) else v) for k, v in env.items()}

    def trap(msg: str) -> RunResult:
        return RunResult(tuple(out), snapshot(), msg)

    pc = 0
    steps = 0
    try:
        while pc < len(tac):
            steps += 1
            if steps > max_steps:
                return trap(f"step limit ({max_steps}) exceeded - possible infinite loop")
            ins = tac[pc]
            op = ins.op
            at = ins.index

            if op == Op.CONST:
                if ins.dest is None or ins.arg1 is None:
                    return trap(f"malformed const at instruction {at}")
                env[ins.dest] = ins.arg1 if ins.extra == STR_CONST else int(ins.arg1)
            elif op == Op.COPY:
                if ins.dest is None or ins.arg1 is None:
                    return trap(f"malformed copy at instruction {at}")
                v = resolve(ins.arg1)
                env[ins.dest] = list(v) if isinstance(v, list) else v
            elif op == Op.NEG:
                if ins.dest is None or ins.arg1 is None:
                    return trap(f"malformed neg at instruction {at}")
                env[ins.dest] = -as_int(ins.arg1, at)
            elif op == Op.LEN:
                if ins.dest is None or ins.arg1 is None:
                    return trap(f"malformed len at instruction {at}")
                v = resolve(ins.arg1)
                if isinstance(v, int):
                    return trap(f"len() of an int at instruction {at}")
                env[ins.dest] = len(v)
            elif op == Op.NEWARR:
                if ins.dest is None or ins.arg1 is None:
                    return trap(f"malformed newarr at instruction {at}")
                env[ins.dest] = [0] * as_int(ins.arg1, at)
            elif op == Op.LOAD:
                if ins.dest is None or ins.arg1 is None or ins.arg2 is None:
                    return trap(f"malformed load at instruction {at}")
                base = resolve(ins.arg1)
                idx = as_int(ins.arg2, at)
                if isinstance(base, int):
                    return trap(f"cannot index the int '{ins.arg1}' at instruction {at}")
                if not 0 <= idx < len(base):
                    return trap(f"index {idx} out of bounds for '{ins.arg1}' "
                                f"(length {len(base)}) at instruction {at}")
                env[ins.dest] = base[idx]
            elif op == Op.STORE:
                if ins.dest is None or ins.arg1 is None or ins.arg2 is None:
                    return trap(f"malformed store at instruction {at}")
                arr = resolve(ins.dest)
                if not isinstance(arr, list):
                    return trap(f"store into non-array '{ins.dest}' at instruction {at}")
                idx = as_int(ins.arg1, at)
                if not 0 <= idx < len(arr):
                    return trap(f"index {idx} out of bounds for '{ins.dest}' "
                                f"(length {len(arr)}) at instruction {at}")
                arr[idx] = as_int(ins.arg2, at)
            elif op == Op.BINOP:
                if ins.dest is None or ins.arg1 is None or ins.arg2 is None:
                    return trap(f"malformed binop at instruction {at}")
                if ins.extra == CONCAT:
                    env[ins.dest] = as_str(ins.arg1, at) + as_str(ins.arg2, at)
                    pc += 1
                    continue
                fn = _BINOPS.get(ins.extra)
                if fn is not None:
                    env[ins.dest] = fn(as_int(ins.arg1, at), as_int(ins.arg2, at))
                elif ins.extra in ("/", "%"):
                    divisor = as_int(ins.arg2, at)
                    if divisor == 0:
                        return trap(f"division by zero at instruction {at}")
                    dividend = as_int(ins.arg1, at)
                    q = _tdiv(dividend, divisor)
                    env[ins.dest] = q if ins.extra == "/" else dividend - q * divisor
                else:
                    return trap(f"unknown operator '{ins.extra}' at instruction {at}")
            elif op == Op.IF_FALSE:
                if ins.dest is None or ins.arg1 is None or ins.arg2 is None:
                    return trap(f"malformed if_false at instruction {at}")
                if ins.extra not in _INT_RELOPS:
                    return trap(f"unknown relop '{ins.extra}' at instruction {at}")
                left, right = resolve(ins.arg1), resolve(ins.arg2)
                if isinstance(left, int) and isinstance(right, int):
                    holds = _INT_RELOPS[ins.extra](left, right)
                elif isinstance(left, str) and isinstance(right, str):
                    holds = _STR_RELOPS[ins.extra](left, right)
                else:
                    return trap(f"cannot compare {_kind(left)} with {_kind(right)} at instruction {at}")
                if not holds:
                    tgt = label_pos.get(ins.dest)
                    if tgt is None:
                        return trap(f"jump to undefined label '{ins.dest}' at instruction {at}")
                    pc = tgt
                    continue
            elif op == Op.GOTO:
                if ins.arg1 is None:
                    return trap(f"malformed goto at instruction {at}")
                tgt = label_pos.get(ins.arg1)
                if tgt is None:
                    return trap(f"jump to undefined label '{ins.arg1}' at instruction {at}")
                pc = tgt
                continue
            elif op == Op.PRINT:
                if ins.arg1 is None:
                    return trap(f"malformed print at instruction {at}")
                out.append(f"{ins.arg1}={show(resolve(ins.arg1))}")
            elif op == Op.LABEL:
                pass
            elif op == Op.HALT:
                return RunResult(tuple(out), snapshot(), None)
            else:
                return trap(f"unknown opcode '{op}' at instruction {at}")
            pc += 1
        return RunResult(tuple(out), snapshot(), None)
    except _Undefined as exc:
        return trap(f"read of undefined value '{exc.name}' (a definition was killed?)")
    except _Trap as exc:
        return trap(str(exc))
