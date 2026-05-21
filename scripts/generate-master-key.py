"""Generate a fresh 32-byte AES-256 master key, base64-encoded.

Run once per deployment. Paste the output into the `RELAY_MASTER_KEY_B64`
line of your .env file (dev) or into /etc/relay/master.key (prod, mode
0400, owned by the relay system user, loaded by the systemd unit's
EnvironmentFile directive).

Rotating the master key requires re-encrypting every envelope-encrypted
row with the new key. That's a one-shot migration script, not part of
this generator.
"""
import base64
import os
import sys


def main() -> int:
    raw = os.urandom(32)
    b64 = base64.b64encode(raw).decode("ascii")
    print(b64)
    print("", file=sys.stderr)
    print("Paste the line above into .env as:", file=sys.stderr)
    print(f"  RELAY_MASTER_KEY_B64={b64}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
