"""Launch independent mock processes and stop every child on exit."""

import argparse
from contextlib import contextmanager
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import threading

SITES = ("pixboard", "friendlink", "localnews", "shadygallery", "host", "search")
ROOT = Path(__file__).resolve().parents[1]


def available(ports):
    sockets = []
    try:
        for port in ports:
            listener = socket.socket()
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sockets.append(listener)
            try:
                listener.bind(("127.0.0.1", port))
            except OSError:
                raise SystemExit(f"Port {port} is unavailable; choose API_PORT=<free port> and BASE_PORT=<free mock range> for make demo.") from None
    finally:
        for listener in sockets:
            listener.close()


def ignore_shutdown_signals():
    """Cleanup is non-interruptible, including a second signal forwarded by uv."""
    if threading.current_thread() is threading.main_thread():
        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, signal.SIG_IGN)


@contextmanager
def cleanup_signals():
    main = threading.current_thread() is threading.main_thread()
    previous = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)} if main else {}
    ignore_shutdown_signals()
    try:
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def interrupted(signum, frame):
    # Ignore repeats before raising, not after the stack starts unwinding.
    ignore_shutdown_signals()
    raise KeyboardInterrupt


def stop(process):
    with cleanup_signals():
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@contextmanager
def running(root, base_port=8811, logs=None, extended=False, mail_command=None, mail_env=None):
    count = 9 if extended else 8
    available(range(base_port, base_port + count))
    commands = []
    for index, site in enumerate(SITES):
        commands.append(
            [
                sys.executable,
                "-m",
                "mockweb.server",
                "--root",
                str(root / site),
                "--site",
                site,
                "--port",
                str(base_port + index),
                "--customer-port",
                str(base_port + 3),
            ]
        )
    commands.append(
        [
            sys.executable,
            "-m",
            "mockweb.registry",
            "--port",
            str(base_port + 6),
            "--customer-port",
            str(base_port + 3),
            "--host-port",
            str(base_port + 4),
        ]
    )
    commands.append(
        [
            sys.executable,
            "-m",
            "mockweb.mail_receiver",
            "--port",
            str(base_port + 7),
            "--site-port",
            str(base_port),
            "--host-port",
            str(base_port + 4),
        ]
    )
    if mail_command is not None:
        commands[7] = mail_command
    if extended:
        commands.append(
            [
                sys.executable,
                "-m",
                "mockweb.server",
                "--root",
                str(root / "editorial"),
                "--site",
                "editorial",
                "--port",
                str(base_port + 8),
            ]
        )
    children = []
    streams = []
    try:
        if logs:
            logs.mkdir(parents=True, exist_ok=True)
        for index, command in enumerate(commands):
            stream = (logs / f"mock-{index}.log").open("w") if logs else subprocess.DEVNULL
            if logs:
                streams.append(stream)
            children.append(subprocess.Popen(
                command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                env=mail_env if index == 7 else None,
            ))
        deadline = time.monotonic() + 15
        for port in range(base_port, base_port + count):
            while True:
                if any(child.poll() is not None for child in children):
                    raise RuntimeError("Mock server exited during startup")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"Mock port {port} did not start")
                    time.sleep(0.05)
        yield children
    finally:
        with cleanup_signals():
            try:
                for child in reversed(children):
                    stop(child)
            finally:
                for stream in streams:
                    stream.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base-port", type=int, default=8811)
    args = parser.parse_args()

    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        with running(args.root.resolve(), args.base_port):
            print(f"Mock web listening on 127.0.0.1:{args.base_port}-{args.base_port + 7}", flush=True)
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
