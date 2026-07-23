#!/usr/bin/env python3
"""Fail when tracked files contain obvious secrets or deceptive filenames."""

from __future__ import annotations

import re
import subprocess
import sys
import unicodedata
from pathlib import Path, PurePosixPath

BIDI_AND_FORMAT_CATEGORIES = {"Cf"}
ALLOWED_ENV_TEMPLATES = {".env.example"}
SENSITIVE_ENV_KEYS = {
    "BOT_TOKEN",
    "API_KEY",
    "SECRET",
    "PASSWORD",
    "PRIVATE_KEY",
}

TELEGRAM_BOT_TOKEN = re.compile(r"(?<![A-Za-z0-9_-])\d{8,12}:[A-Za-z0-9_-]{30,}(?![A-Za-z0-9_-])")
PRIVATE_KEY_HEADER = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
ENV_ASSIGNMENT = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$")


def tracked_files() -> list[str]:
    try:
        output = subprocess.check_output(["git", "ls-files", "-z"])
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Unable to list tracked files with git") from exc
    return [entry.decode("utf-8") for entry in output.split(b"\0") if entry]


def format_characters(value: str) -> list[str]:
    return [
        f"U+{ord(char):04X} ({unicodedata.name(char, 'UNKNOWN')})"
        for char in value
        if unicodedata.category(char) in BIDI_AND_FORMAT_CATEGORIES
    ]


def normalized_basename(path: str) -> str:
    without_format_chars = "".join(
        char for char in path if unicodedata.category(char) not in BIDI_AND_FORMAT_CATEGORIES
    )
    return PurePosixPath(without_format_chars).name.lower()


def is_forbidden_env_file(basename: str) -> bool:
    if basename in ALLOWED_ENV_TEMPLATES:
        return False
    return basename == ".env" or basename.startswith(".env.") or basename.endswith(".env")


def read_text(path: str) -> str | None:
    data = Path(path).read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def main() -> int:
    errors: list[str] = []

    for path in tracked_files():
        hidden_chars = format_characters(path)
        if hidden_chars:
            errors.append(f"{path!r}: filename contains hidden formatting characters: {', '.join(hidden_chars)}")

        basename = normalized_basename(path)
        if is_forbidden_env_file(basename):
            errors.append(f"{path!r}: environment/secret files must not be tracked")

        text = read_text(path)
        if text is None:
            continue

        if TELEGRAM_BOT_TOKEN.search(text):
            errors.append(f"{path!r}: contains a value matching a Telegram bot token")

        if PRIVATE_KEY_HEADER.search(text):
            errors.append(f"{path!r}: contains a private-key header")

        if basename in ALLOWED_ENV_TEMPLATES:
            for line_number, line in enumerate(text.splitlines(), start=1):
                match = ENV_ASSIGNMENT.match(line)
                if not match:
                    continue
                key, value = match.groups()
                value = value.strip().strip("\"'")
                if key in SENSITIVE_ENV_KEYS and value:
                    errors.append(
                        f"{path!r}:{line_number}: template value for {key} must remain empty"
                    )

    if errors:
        print("Repository security check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Repository security check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
