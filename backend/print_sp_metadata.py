"""Print SAML Service Provider metadata XML to stdout.

Usage:
    python -m backend.print_sp_metadata
"""
import sys

from backend.auth.saml import generate_sp_metadata


def main() -> None:
    metadata, errors = generate_sp_metadata()
    if errors:
        print("Metadata validation errors:", errors, file=sys.stderr)
        sys.exit(1)
    if isinstance(metadata, bytes):
        sys.stdout.buffer.write(metadata)
    else:
        print(metadata)


if __name__ == "__main__":
    main()
