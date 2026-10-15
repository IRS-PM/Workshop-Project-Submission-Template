"""Create private, persistent local Langfuse credentials. Never overwrite existing values."""

import argparse
import os
import secrets
from pathlib import Path
from uuid import uuid4

from dotenv import dotenv_values, set_key


def initialize(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(fd)
    path.chmod(0o600)
    current = dotenv_values(path, interpolate=False)
    defaults = {
        "LANGFUSE_PORT": "3031",
        "LANGFUSE_PUBLIC_KEY": "pk-lf-" + str(uuid4()),
        "LANGFUSE_SECRET_KEY": "sk-lf-" + secrets.token_hex(32),
        "LANGFUSE_POSTGRES_PASSWORD": secrets.token_hex(32),
        "LANGFUSE_CLICKHOUSE_PASSWORD": secrets.token_hex(32),
        "LANGFUSE_REDIS_PASSWORD": secrets.token_hex(32),
        "LANGFUSE_MINIO_PASSWORD": secrets.token_hex(32),
        "LANGFUSE_SALT": secrets.token_hex(32),
        "LANGFUSE_ENCRYPTION_KEY": secrets.token_hex(32),
        "LANGFUSE_NEXTAUTH_SECRET": secrets.token_hex(32),
        "LANGFUSE_INIT_USER_EMAIL": "admin@remy.local",
        "LANGFUSE_INIT_USER_PASSWORD": secrets.token_urlsafe(32),
        "REMY_EVALUATION_TOKEN": secrets.token_urlsafe(32),
        "REMY_POSTGRES_PASSWORD": secrets.token_hex(32),
        "REMY_JWT_SECRET": secrets.token_urlsafe(48),
    }
    for key, value in defaults.items():
        if not current.get(key):
            set_key(path, key, value, quote_mode="always")
    return dotenv_values(path, interpolate=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=Path(".env.nonprod"))
    args = parser.parse_args()
    initialize(args.path)
    print(f"Local Langfuse credentials ready in {args.path}; values hidden.")
