"""Management commands.

  python -m app.cli seed                 Create permissions/roles and the initial admin from env (idempotent)
  python -m app.cli create-admin EMAIL   Create or reset an admin account (prompts for password)
  python -m app.cli check                Verify PostgreSQL and Redis connectivity
"""

import argparse
import getpass
import sys

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_sync_sessionmaker
from app.core.permissions import PERMISSIONS, ROLES
from app.core.redis import get_sync_redis
from app.core.security import hash_password
from app.models import Permission, Role, User
from app.schemas.auth import validate_password_strength


def seed_rbac(session: Session) -> None:
    existing = {p.code: p for p in session.execute(select(Permission)).scalars()}
    for code, description in PERMISSIONS.items():
        if code not in existing:
            existing[code] = Permission(code=code, description=description)
            session.add(existing[code])
    for name, spec in ROLES.items():
        role = session.execute(select(Role).where(Role.name == name)).scalar_one_or_none()
        if role is None:
            role = Role(name=name, description=spec["description"], is_system=True)
            session.add(role)
        role.permissions = [existing[c] for c in spec["permissions"]]
    session.commit()


def upsert_admin(session: Session, email: str, password: str) -> str:
    validate_password_strength(password)
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    admin_role = session.execute(select(Role).where(Role.name == "admin")).scalar_one()
    user = session.execute(select(User).where(func.lower(User.email) == email.lower())).scalar_one_or_none()
    action = "updated"
    if user is None:
        user = User(email=email.lower(), full_name="Administrator", password_hash="")
        session.add(user)
        action = "created"
    user.password_hash = hash_password(password)
    user.is_active = True
    user.is_superuser = True
    user.failed_login_count = 0
    user.locked_until = None
    if admin_role not in user.roles:
        user.roles.append(admin_role)
    session.commit()
    return action


def cmd_seed(_: argparse.Namespace) -> int:
    s = get_settings()
    with get_sync_sessionmaker()() as session:
        seed_rbac(session)
        print(f"Seeded {len(PERMISSIONS)} permissions and {len(ROLES)} roles")
        password = s.initial_admin_password.get_secret_value() if s.initial_admin_password else ""
        if s.initial_admin_email and password:
            exists = session.execute(select(User.id).where(func.lower(User.email) == s.initial_admin_email.lower())).first()
            if exists:
                print(f"Admin {s.initial_admin_email} already exists (unchanged)")
            else:
                upsert_admin(session, s.initial_admin_email, password)
                print(f"Created initial admin {s.initial_admin_email}")
        else:
            print("INITIAL_ADMIN_EMAIL/INITIAL_ADMIN_PASSWORD not set; skipping admin creation")
    return 0


def cmd_create_admin(args: argparse.Namespace) -> int:
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Confirm: "):
        print("Passwords do not match", file=sys.stderr)
        return 1
    with get_sync_sessionmaker()() as session:
        seed_rbac(session)
        try:
            action = upsert_admin(session, args.email, password)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    print(f"Admin {args.email} {action}")
    return 0


def cmd_check(_: argparse.Namespace) -> int:
    ok = True
    try:
        with get_sync_sessionmaker()() as session:
            print("PostgreSQL:", session.execute(text("SHOW server_version")).scalar_one())
    except Exception as exc:  # noqa: BLE001
        ok = False
        print("PostgreSQL: FAILED", exc)
    try:
        print("Redis:", "PONG" if get_sync_redis().ping() else "no response")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print("Redis: FAILED", exc)
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed").set_defaults(func=cmd_seed)
    admin = sub.add_parser("create-admin")
    admin.add_argument("email")
    admin.set_defaults(func=cmd_create_admin)
    sub.add_parser("check").set_defaults(func=cmd_check)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
