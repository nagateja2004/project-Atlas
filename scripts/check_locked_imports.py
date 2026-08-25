"""
Fail if the code imports something the lock file does not pin.

This guards a fault that has shipped twice, and both times it was invisible
locally and fatal in CI:

  - `pywin32` was pinned without an environment marker, so the lock could not be
    installed on Linux at all.
  - `pydantic.EmailStr` needs the separate `email-validator` package. It happened
    to be installed on the development machine and was absent from the lock, so
    `app.auth` imported fine locally and failed to import in CI - taking every
    backend test with it.

The shape is the same each time: the developer's environment satisfies an import
that the pinned set does not, so the test suite passes on the machine where the
code was written and nowhere else. A green local run is not evidence, which is
what makes this worth a check rather than a habit.

    python3 scripts/check_locked_imports.py                     # requirements-dev.lock
    python3 scripts/check_locked_imports.py --lock requirements.lock --roots app scripts

Note what this does NOT prove: it reads the CURRENT environment to learn which
distribution provides a module, so it cannot see a dependency that is missing
both from the lock and from this machine. Installing the lock into a clean
environment remains the only complete check. This catches the common case early
and cheaply.
"""

from __future__ import annotations

import argparse
import ast
import importlib.metadata as metadata
import pathlib
import sys

# Directories that are part of this repository rather than dependencies.
FIRST_PARTY = {"app", "scripts", "evaluation", "tests", "migrations"}

DEFAULT_ROOTS = ("app", "scripts", "migrations", "evaluation", "tests")


def locked_distributions(lock_path: pathlib.Path) -> set[str]:
    names: set[str] = set()
    for line in lock_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # "package==1.2.3 ; marker" -> "package"
        name = line.split("==")[0].split(";")[0].split("[")[0].strip()
        if name:
            names.add(normalise(name))
    return names


def normalise(name: str) -> str:
    return name.lower().replace("_", "-")


def imported_modules(roots: tuple[str, ...]) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for root in roots:
        base = pathlib.Path(root)
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        found.setdefault(alias.name.split(".")[0], set()).add(str(path))
                elif isinstance(node, ast.ImportFrom):
                    # level > 0 is a relative import, so first-party by definition.
                    if node.module and node.level == 0:
                        found.setdefault(node.module.split(".")[0], set()).add(str(path))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", default="requirements-dev.lock")
    parser.add_argument("--roots", nargs="*", default=list(DEFAULT_ROOTS))
    args = parser.parse_args()

    lock_path = pathlib.Path(args.lock)
    if not lock_path.is_file():
        print(f"error: {lock_path} not found", file=sys.stderr)
        return 1

    locked = locked_distributions(lock_path)
    provided = metadata.packages_distributions()
    stdlib = set(sys.stdlib_module_names)

    problems: list[tuple[str, str, list[str]]] = []
    checked = 0

    for module, files in sorted(imported_modules(tuple(args.roots)).items()):
        if module in stdlib or module in FIRST_PARTY:
            continue
        checked += 1
        distributions = {normalise(d) for d in provided.get(module, [])}
        if not distributions:
            problems.append((module, "no installed distribution provides this module", sorted(files)))
        elif not distributions & locked:
            problems.append((
                module,
                f"provided by {', '.join(sorted(distributions))} - not pinned in {lock_path.name}",
                sorted(files),
            ))

    print(f"checked {checked} third-party imports against {lock_path.name}")

    if problems:
        print(f"\n{len(problems)} import(s) not satisfied by {lock_path.name}:\n", file=sys.stderr)
        for module, reason, files in problems:
            print(f"  {module}: {reason}", file=sys.stderr)
            for path in files[:4]:
                print(f"      {path}", file=sys.stderr)
            if len(files) > 4:
                print(f"      ... and {len(files) - 4} more", file=sys.stderr)
        print(
            "\nAdd the distribution to pyproject.toml and regenerate the lock, or remove\n"
            "the import. Passing tests locally does not mean CI can install it.",
            file=sys.stderr,
        )
        return 1

    print("every third-party import is pinned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
