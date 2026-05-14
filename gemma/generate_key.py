"""Generate cryptographically secure API keys."""

import secrets
import argparse
import hashlib


def generate_api_key(prefix: str = "sk", num_bytes: int = 32, include_checksum: bool = True) -> str:
    """
    Generate a secure API key.

    Args:
        prefix: A short identifier prepended to the key (e.g., 'sk', 'pk', 'live').
        num_bytes: Number of random bytes (32 = 256 bits of entropy, recommended).
        include_checksum: Append a short checksum so typos can be detected.

    Returns:
        A string like 'sk_live_AbCdEf...XyZ_a1b2c3d4'
    """
    if num_bytes < 16:
        raise ValueError("num_bytes must be >= 16 for adequate entropy (128 bits).")

    # secrets.token_urlsafe uses os.urandom under the hood — cryptographically secure
    # and produces URL-safe base64 (no +, /, or padding).
    random_part = secrets.token_urlsafe(num_bytes)

    key = f"{prefix}_{random_part}" if prefix else random_part

    if include_checksum:
        # First 8 hex chars of SHA-256 is enough to catch transcription errors
        # without leaking meaningful information about the secret.
        checksum = hashlib.sha256(key.encode()).hexdigest()[:8]
        key = f"{key}_{checksum}"

    return key


def verify_checksum(key: str) -> bool:
    """Verify a key's trailing 8-char checksum matches its body."""
    try:
        body, checksum = key.rsplit("_", 1)
    except ValueError:
        return False
    if len(checksum) != 8:
        return False
    expected = hashlib.sha256(body.encode()).hexdigest()[:8]
    return secrets.compare_digest(checksum, expected)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a secure API key.")
    parser.add_argument("--prefix", default="sk", help="Key prefix (default: 'sk').")
    parser.add_argument("--bytes", type=int, default=32,
                        help="Bytes of entropy (default: 32 = 256 bits).")
    parser.add_argument("--no-checksum", action="store_true",
                        help="Omit the trailing checksum.")
    parser.add_argument("-n", "--count", type=int, default=1,
                        help="How many keys to generate.")
    args = parser.parse_args()

    for _ in range(args.count):
        print(generate_api_key(
            prefix=args.prefix,
            num_bytes=args.bytes,
            include_checksum=not args.no_checksum,
        ))


if __name__ == "__main__":
    main()