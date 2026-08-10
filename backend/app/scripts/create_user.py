import argparse
import getpass

from sqlalchemy import select

from app.core.passwords import hash_password
from app.db.session import SessionLocal
from app.models.user import AppUser


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a local Planets Intel user."
    )

    parser.add_argument(
        "username",
    )

    parser.add_argument(
        "--display-name",
        default=None,
    )

    return parser.parse_args()


def normalize_username(
    username: str,
) -> str:
    return username.strip().casefold()


def main() -> None:
    args = parse_args()

    username = normalize_username(
        args.username
    )

    if not username:
        raise SystemExit(
            "username must not be empty"
        )

    display_name = (
        args.display_name.strip()
        if args.display_name
        else args.username.strip()
    )

    password = getpass.getpass(
        "Password: "
    )

    password_repeat = getpass.getpass(
        "Repeat password: "
    )

    if password != password_repeat:
        raise SystemExit(
            "passwords do not match"
        )

    if len(password) < 12:
        raise SystemExit(
            "password must contain at least 12 characters"
        )

    password_hash = hash_password(
        password
    )

    del password
    del password_repeat

    with SessionLocal() as session:
        existing = session.execute(
            select(AppUser).where(
                AppUser.username == username
            )
        ).scalar_one_or_none()

        if existing is not None:
            raise SystemExit(
                f"user already exists: {username}"
            )

        user = AppUser(
            username=username,
            display_name=display_name,
            password_hash=password_hash,
            is_active=True,
        )

        session.add(user)
        session.commit()
        session.refresh(user)

        print(
            f"created user id={user.id} "
            f"username={user.username!r}"
        )


if __name__ == "__main__":
    main()
