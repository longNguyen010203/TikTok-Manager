"""One-time local-runtime configuration and credential-key bootstrap."""

from __future__ import annotations

import argparse

from app.config import bootstrap_application_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ensure-key", action="store_true")
    args = parser.parse_args()
    config = bootstrap_application_config()
    config.database_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    print(f"config={config.config_path}")
    print(f"database={config.database_path}")
    if args.ensure_key:
        from app.database import SessionLocal
        from app.services.network_credentials import (
            MasterKeyManager,
            NetworkCredentialProvider,
        )

        with SessionLocal() as session:
            NetworkCredentialProvider(
                MasterKeyManager(config.credential_key_path)
            ).ensure_key(session)
        print(f"credential_key={config.credential_key_path}")


if __name__ == "__main__":
    main()
