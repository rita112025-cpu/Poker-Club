"""Construct the container database URL without shell interpolation or secret output."""

import os
import sys

from sqlalchemy import URL


def main() -> None:
    os.environ["DATABASE_URL"] = URL.create(
        "postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host="db",
        database=os.environ["POSTGRES_DB"],
    ).render_as_string(hide_password=False)
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
