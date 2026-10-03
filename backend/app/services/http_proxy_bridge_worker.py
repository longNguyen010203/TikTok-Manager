"""Small HTTP proxy bridge worker launched only by the systemd supervisor."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
from pathlib import Path


async def _relay(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        writer.close()


async def _handle(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    upstream_host: str,
    upstream_port: int,
    authorization: str | None,
) -> None:
    try:
        header = await client_reader.readuntil(b"\r\n\r\n")
        lines = header.split(b"\r\n")
        request_line = lines[0]
        forwarded_headers = [
            line
            for line in lines[1:]
            if line
            and not line.lower().startswith(b"proxy-authorization:")
        ]
        if authorization:
            forwarded_headers.append(
                f"Proxy-Authorization: Basic {authorization}".encode()
            )
        forwarded_header = b"\r\n".join(
            [request_line, *forwarded_headers, b"", b""]
        )
        upstream_reader, upstream_writer = await asyncio.open_connection(
            upstream_host, upstream_port
        )
        upstream_writer.write(forwarded_header)
        await upstream_writer.drain()
        if request_line.upper().startswith(b"CONNECT "):
            response = await upstream_reader.readuntil(b"\r\n\r\n")
            client_writer.write(response)
            await client_writer.drain()
            if not response.startswith(b"HTTP/1.1 200") and not response.startswith(b"HTTP/1.0 200"):
                upstream_writer.close()
                return
        await asyncio.gather(
            _relay(client_reader, upstream_writer),
            _relay(upstream_reader, client_writer),
        )
    except (
        asyncio.IncompleteReadError,
        asyncio.LimitOverrunError,
        ConnectionError,
        OSError,
    ):
        client_writer.close()


async def _main(args: argparse.Namespace) -> None:
    credential_directory = os.environ.get("CREDENTIALS_DIRECTORY")
    if not credential_directory:
        raise RuntimeError("systemd credential directory is unavailable")
    payload = json.loads(
        (Path(credential_directory) / args.credential_name).read_text(encoding="utf-8")
    )
    username = payload.get("username")
    password = payload.get("password")
    authorization = None
    if username is not None or password is not None:
        raw = f"{username or ''}:{password or ''}".encode()
        authorization = base64.b64encode(raw).decode("ascii")
    server = await asyncio.start_server(
        lambda reader, writer: _handle(
            reader, writer, args.upstream_host, args.upstream_port, authorization
        ),
        host=args.listen_host,
        port=args.listen_port,
    )
    async with server:
        await server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-host", required=True, choices=("127.0.0.1", "::1"))
    parser.add_argument("--listen-port", required=True, type=int)
    parser.add_argument("--upstream-host", required=True)
    parser.add_argument("--upstream-port", required=True, type=int)
    parser.add_argument("--credential-name", default="proxy")
    asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    main()
