#!/usr/bin/env python3
"""Fail when the application code could send data away or write camera pictures to disk.

Habit Guard's privacy promises are checked by looking at the source, not by
trusting it:

* no networking: nothing under ``src/habit_guard`` imports a network library
  (sockets, HTTP clients, Qt's network module, ...);
* no pictures written: no call to OpenCV's image and video writers, and none
  to Qt's ``save`` on an image or pixmap.

The scan is syntactic, so it can be fooled by deliberate obfuscation; it is a
guard rail against accidents and a prompt for review, not a sandbox.

Usage::

    python scripts/check_privacy.py          # scan src/habit_guard
    python scripts/check_privacy.py PATH...  # scan other files or folders
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = REPO_ROOT / "src" / "habit_guard"

#: Top-level modules that talk to a network.
NETWORK_MODULES = frozenset(
    {
        "socket",
        "ssl",
        "http",
        "urllib",
        "urllib3",
        "requests",
        "httpx",
        "aiohttp",
        "websocket",
        "websockets",
        "ftplib",
        "smtplib",
        "imaplib",
        "poplib",
        "telnetlib",
        "xmlrpc",
        "socketserver",
        "asyncio",
        "grpc",
        "paramiko",
        "boto3",
        "botocore",
        "PySide6.QtNetwork",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
    }
)
#: Allowed even though their parent package is on the list (pure string handling).
ALLOWED_MODULES = frozenset({"urllib.parse"})
#: Attribute names that write a picture or a video.
IMAGE_WRITERS = frozenset({"imwrite", "imencode", "VideoWriter", "VideoWriter_fourcc"})


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


def _is_network(module: str) -> bool:
    if any(module == a or module.startswith(a + ".") for a in ALLOWED_MODULES):
        return False
    return any(module == m or module.startswith(m + ".") for m in NETWORK_MODULES)


def scan_source(source: str, filename: str = "<string>") -> list[Violation]:
    """Violations of the privacy rules in one piece of Python source."""
    tree = ast.parse(source, filename)
    found: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_network(alias.name):
                    found.append(Violation(filename, node.lineno, f"imports {alias.name}"))
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            for name in names:
                if _is_network(name):
                    found.append(Violation(filename, node.lineno, f"imports {name}"))
                    break
            for alias in node.names:
                if alias.name in IMAGE_WRITERS:
                    found.append(
                        Violation(filename, node.lineno, f"imports {alias.name} (writes pictures)")
                    )
        elif isinstance(node, ast.Attribute) and node.attr in IMAGE_WRITERS:
            found.append(Violation(filename, node.lineno, f"uses {node.attr} (writes pictures)"))
        elif isinstance(node, ast.Name) and node.id in IMAGE_WRITERS:
            found.append(Violation(filename, node.lineno, f"uses {node.id} (writes pictures)"))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "save"
            and _looks_like_picture(node.func.value)
        ):  # `widget.grab().save(...)`, `image.save(...)`, `pixmap.save(...)` on Qt pictures
            found.append(Violation(filename, node.lineno, "saves a picture to disk"))
    return found


def _looks_like_picture(node: ast.expr) -> bool:
    """True for ``x.grab()``, ``QImage(...)``, ``QPixmap(...)`` and names ending in image/pixmap."""
    if isinstance(node, ast.Call):
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        return name in {"grab", "toImage", "toPixmap", "QImage", "QPixmap", "to_qimage"}
    if isinstance(node, ast.Name | ast.Attribute):
        name = node.id if isinstance(node, ast.Name) else node.attr
        return name.lower().endswith(("image", "pixmap", "img", "frame"))
    return False


def iter_python_files(targets: Iterable[Path]) -> Iterable[Path]:
    for target in targets:
        if target.is_dir():
            yield from sorted(p for p in target.rglob("*.py") if "__pycache__" not in p.parts)
        elif target.suffix == ".py":
            yield target


def scan_paths(targets: Iterable[Path]) -> list[Violation]:
    found: list[Violation] = []
    for path in iter_python_files(targets):
        try:
            label = str(path.relative_to(REPO_ROOT))
        except ValueError:
            label = str(path)
        found.extend(scan_source(path.read_text(encoding="utf-8"), label))
    return found


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    targets = [Path(a) for a in args] or [DEFAULT_TARGET]
    violations = scan_paths(targets)
    if violations:
        print("Privacy check FAILED:", file=sys.stderr)
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        return 1
    count = sum(1 for _ in iter_python_files(targets))
    print(f"Privacy check passed: {count} files, no networking and no picture writing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
