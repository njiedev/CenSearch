"""Generate a Caddy-compatible bcrypt hash without Docker or command-line passwords."""

import getpass
import sys
import bcrypt


def main():
    password = getpass.getpass("Shared app password: ")
    confirm = getpass.getpass("Confirm password: ")
    if not password or password != confirm:
        raise SystemExit("Passwords must be nonempty and match")
    if len(password.encode()) > 72:
        raise SystemExit("Bcrypt accepts at most 72 UTF-8 bytes")
    print(bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=14)).decode())


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        sys.exit(1)
