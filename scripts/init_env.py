#!/usr/bin/env python3
"""Create .env files from .env.example templates, replacing `change-me` secrets with random values.

Existing .env files are never overwritten; only missing keys are appended so upgrades pick up new settings.
"""

import re
import secrets
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = [ROOT, ROOT / "backend", ROOT / "frontend", ROOT / "agent"]
LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")


def admin_password() -> str:
    alphabet = string.ascii_letters + string.digits
    core = "".join(secrets.choice(alphabet) for _ in range(18))
    return f"Sp-{core}-9a"


GENERATORS = {
    "APP_SECRET_KEY": lambda: secrets.token_urlsafe(64),
    "JWT_SECRET_KEY": lambda: secrets.token_urlsafe(64),
    "POSTGRES_PASSWORD": lambda: secrets.token_urlsafe(24),
    "INITIAL_ADMIN_PASSWORD": admin_password,
}


def render(template: str) -> str:
    out = []
    for line in template.splitlines():
        m = LINE.match(line)
        if m and m.group(2) == "change-me" and m.group(1) in GENERATORS:
            line = f"{m.group(1)}={GENERATORS[m.group(1)]()}"
        out.append(line)
    return "\n".join(out) + "\n"


def keys(text: str) -> set[str]:
    return {m.group(1) for line in text.splitlines() if (m := LINE.match(line))}


def main() -> int:
    for directory in TARGETS:
        example, target = directory / ".env.example", directory / ".env"
        if not example.exists():
            continue
        rel = target.relative_to(ROOT)
        if not target.exists():
            target.write_text(render(example.read_text()))
            target.chmod(0o600)
            print(f"  created {rel}")
            continue
        existing = target.read_text()
        missing = keys(example.read_text()) - keys(existing)
        if missing:
            additions = [line for line in render(example.read_text()).splitlines()
                         if (m := LINE.match(line)) and m.group(1) in missing]
            target.write_text(existing.rstrip("\n") + "\n\n# Added by init_env.py\n" + "\n".join(additions) + "\n")
            print(f"  updated {rel} (+{', '.join(sorted(missing))})")
        else:
            print(f"  kept    {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
