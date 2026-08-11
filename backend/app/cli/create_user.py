import argparse
from getpass import getpass

from sqlalchemy import select

from app.core.passwords import hash_password
from app.db.session import SessionLocal
from app.models.user import AppUser
from app.services.auth import normalize_username


MIN_PASSWORD_LENGTH = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a local Planets.nu Intel Client user. "
            "The password is read interactively and is never printed."
        )
    )
    parser.add_argument(
        "username",
        help="Local Intel Client username",
    )
    parser.add_argument(
        "--display-name",
        default=None,
        help="Display name; defaults to the supplied username",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    raw_username = args.username.strip()
    username = normalize_username(raw_username)
    display_name = (
        args.display_name.strip()
        if args.display_name is not None
        else raw_username
    )

    if not username:
        raise SystemExit("Username must not be empty")

    if len(username) > 64:
        raise SystemExit("Username must be at most 64 characters")

    if not display_name:
        raise SystemExit("Display name must not be empty")

    if len(display_name) > 128:
        raise SystemExit("Display name must be at most 128 characters")

    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")

    if password != confirmation:
        raise SystemExit("Passwords do not match")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        )

    with SessionLocal() as session:
        existing = session.execute(
            select(AppUser).where(
                AppUser.username == username
            )
        ).scalar_one_or_none()

        if existing is not None:
            raise SystemExit(
                f"Local user '{username}' already exists"
            )

        user = AppUser(
            username=username,
            display_name=display_name,
            password_hash=hash_password(password),
            is_active=True,
        )

        session.add(user)
        session.commit()
        session.refresh(user)

        print(
            f"Created local user id={user.id} username={user.username}"
        )


if __name__ == "__main__":
    main()
