"""User configuration for filenotes.

Config lives at ``$FILENOTES_CONFIG`` or, by default,
``$XDG_CONFIG_HOME/filenotes/config.toml`` (i.e. ``~/.config/filenotes/config.toml``).
It is optional; sensible defaults apply when it is missing.

Supported keys (flat, TOML-compatible ``key = value`` lines)::

    recent_count = 5    # files shown by the `note` recent-file selector

Individual keys can be overridden by environment variables, e.g.
``FILENOTES_RECENT_COUNT``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

DEFAULTS: Dict[str, object] = {
    "recent_count": 5,
    "stamp_commit": True,
    "embed_images": False,
}


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def config_path() -> Path:
    override = os.environ.get("FILENOTES_CONFIG")
    if override:
        return Path(override)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "filenotes" / "config.toml"


def _parse(text: str) -> Dict[str, object]:
    """Parse simple ``key = value`` lines (a subset of TOML).

    Uses the stdlib TOML parser when available (Python 3.11+), otherwise falls
    back to a tiny scalar parser so config still works on older interpreters.
    """
    try:
        import tomllib  # Python 3.11+

        return dict(tomllib.loads(text))
    except ModuleNotFoundError:
        pass

    parsed: Dict[str, object] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if value.lstrip("-").isdigit():
            parsed[key] = int(value)
        elif value.lower() in ("true", "false"):
            parsed[key] = value.lower() == "true"
        else:
            parsed[key] = value
    return parsed


def load_config() -> Dict[str, object]:
    cfg = dict(DEFAULTS)

    path = config_path()
    if path.is_file():
        try:
            cfg.update(_parse(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass  # malformed config should not break note-taking

    # Environment overrides win over the file.
    env_count = os.environ.get("FILENOTES_RECENT_COUNT")
    if env_count and env_count.isdigit():
        cfg["recent_count"] = int(env_count)

    env_stamp = os.environ.get("FILENOTES_STAMP_COMMIT")
    if env_stamp is not None:
        cfg["stamp_commit"] = _as_bool(env_stamp)

    env_embed = os.environ.get("FILENOTES_EMBED_IMAGES")
    if env_embed is not None:
        cfg["embed_images"] = _as_bool(env_embed)

    try:
        cfg["recent_count"] = max(1, int(cfg["recent_count"]))
    except (TypeError, ValueError):
        cfg["recent_count"] = DEFAULTS["recent_count"]
    cfg["stamp_commit"] = _as_bool(cfg["stamp_commit"])
    cfg["embed_images"] = _as_bool(cfg["embed_images"])

    return cfg
