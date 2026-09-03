"""Generates a self-signed TLS cert+key for run.bat to serve HTTPS.

Usage: python generate_cert.py <hostname-or-ip>

Writes certs/cert.pem and certs/key.pem. Self-signed means browsers will
warn until the cert is trusted on each client - see README.md.
"""
import ipaddress
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

CERT_DIR = Path(__file__).parent / "certs"


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python generate_cert.py <hostname-or-ip>")
        print("Example: python generate_cert.py freeze-notifier.company.local")
        sys.exit(1)

    host = sys.argv[1]
    CERT_DIR.mkdir(exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])

    try:
        san = x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(host))])
    except ValueError:
        san = x509.SubjectAlternativeName([x509.DNSName(host)])

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=730))
        .add_extension(san, critical=False)
        .sign(key, hashes.SHA256())
    )

    (CERT_DIR / "key.pem").write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    (CERT_DIR / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    print(f"Wrote {CERT_DIR / 'cert.pem'} and {CERT_DIR / 'key.pem'} for host '{host}', valid 730 days.")
    print("Self-signed - browsers will warn until this cert is trusted on client machines. See README.md.")


if __name__ == "__main__":
    main()
