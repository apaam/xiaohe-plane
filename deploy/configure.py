#!/usr/bin/env python3
"""Prepare Plane's plane.env for a 4GB staging deployment.

Secrets are preserved across runs. Set PLANE_ROTATE_SECRETS=1 to rotate them
(only do this together with the database / RabbitMQ credentials).
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path


def main() -> int:
    env_path = Path.home() / "plane-selfhost" / "plane.env"
    if not env_path.exists():
        raise SystemExit(f"missing {env_path}; download the release variables.env first")

    existing: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            existing[key.strip()] = value.strip().strip('"')

    app_domain = os.environ.get("PLANE_APP_DOMAIN", existing.get("APP_DOMAIN", "127.0.0.1:18080"))
    web_url = os.environ.get("PLANE_WEB_URL", f"http://{app_domain}")
    cors = os.environ.get("PLANE_CORS", web_url)
    bind_ip = os.environ.get("PLANE_BIND_IP", "127.0.0.1")
    release = os.environ.get("PLANE_RELEASE", existing.get("APP_RELEASE", "v1.5.0"))
    rotate = os.environ.get("PLANE_ROTATE_SECRETS") == "1"

    def keep(key: str, placeholders: set[str], generator) -> str:
        current = existing.get(key, "")
        if rotate or not current or current in placeholders:
            return generator()
        return current

    postgres_password = keep(
        "POSTGRES_PASSWORD", {"", "plane", "__GENERATE__"}, lambda: secrets.token_hex(24)
    )
    rabbitmq_password = keep(
        "RABBITMQ_PASSWORD", {"", "plane", "__GENERATE__"}, lambda: secrets.token_hex(24)
    )
    secret_key = keep(
        "SECRET_KEY",
        {"", "change-this-key-on-deployment", "__GENERATE__"},
        lambda: secrets.token_hex(32),
    )
    live_key = keep(
        "LIVE_SERVER_SECRET_KEY",
        {"", "change-this-key-on-deployment", "__GENERATE__"},
        lambda: secrets.token_hex(32),
    )
    aws_key_id = keep(
        "AWS_ACCESS_KEY_ID", {"", "access-key", "__GENERATE__"}, lambda: secrets.token_hex(16)
    )
    aws_secret = keep(
        "AWS_SECRET_ACCESS_KEY", {"", "secret-key", "__GENERATE__"}, lambda: secrets.token_hex(32)
    )

    values = {
        "APP_RELEASE": release,
        "APP_DOMAIN": app_domain,
        "WEB_URL": web_url,
        "CORS_ALLOWED_ORIGINS": cors,
        "PLANE_BIND_IP": bind_ip,
        "LISTEN_HTTP_PORT": "8080",
        "LISTEN_HTTPS_PORT": "8443",
        "POSTGRES_USER": "plane",
        "POSTGRES_DB": "plane",
        "POSTGRES_PASSWORD": postgres_password,
        "DATABASE_URL": f"postgresql://plane:{postgres_password}@plane-db/plane",
        "RABBITMQ_USER": "plane",
        "RABBITMQ_PASSWORD": rabbitmq_password,
        "AMQP_URL": f"amqp://plane:{rabbitmq_password}@plane-mq:5672/plane",
        "SECRET_KEY": secret_key,
        "LIVE_SERVER_SECRET_KEY": live_key,
        "AWS_ACCESS_KEY_ID": aws_key_id,
        "AWS_SECRET_ACCESS_KEY": aws_secret,
        "GUNICORN_WORKERS": "1",
        "USE_MINIO": "1",
        "CERT_EMAIL": "",
    }

    lines = env_path.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in values:
                output.append(f"{key}={values[key]}")
                seen.add(key)
                continue
        output.append(line)

    for key, value in values.items():
        if key not in seen:
            output.append(f"{key}={value}")

    env_path.write_text("\n".join(output) + "\n", encoding="utf-8")
    print(f"updated {env_path} (secrets preserved unless PLANE_ROTATE_SECRETS=1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
