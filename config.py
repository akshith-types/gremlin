from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    input_path: Path
    out_dir: Path
    debug: bool
    max_mutants: int
    max_steps: int


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got '{raw}'") from exc


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ConfigError(f"{name} must be a boolean, got '{raw}'")


def load_config() -> Config:
    load_dotenv()
    return Config(
        input_path=Path(os.getenv("GREMLIN_INPUT", "tests/data/valid1.gc")),
        out_dir=Path(os.getenv("GREMLIN_OUT", "out")),
        debug=_bool_env("GREMLIN_DEBUG", False),
        max_mutants=_int_env("GREMLIN_MAX_MUTANTS", 5),
        max_steps=_int_env("GREMLIN_MAX_STEPS", 200000),
    )