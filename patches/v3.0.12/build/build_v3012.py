"""v3.0.12 PyInstaller build script.

Run from a working directory containing the merged v3.0.11 + v3.0.12 source tree.
Discovers all root-level .py modules and bundles them both as PYZ (Analysis via
--paths) and as loose data files (so main.py's runtime sys.path manipulation
finds them too).
"""
import glob
import os
import sys

import PyInstaller.__main__


def main() -> int:
    cwd = os.getcwd()
    print(f"[build] cwd = {cwd}")

    # Root-level .py files that need to be importable at runtime.
    # main.py's `from auth_module import ...` etc. must resolve.
    root_py = sorted(
        f for f in glob.glob("*.py")
        if os.path.isfile(f) and f not in ("build_v3012.py",)
    )
    print(f"[build] root modules found: {root_py}")

    # Sanity check: auth_module must be present
    if "auth_module.py" not in root_py:
        print("[build] ERROR: auth_module.py missing from cwd")
        return 1

    sep = ";"  # Windows path separator for --add-data
    add_data = [
        f"VERSION.txt{sep}.",
        f"ui{sep}ui",
        f"dashboard{sep}dashboard",
        f"manual{sep}manual",
        f"config.json.template{sep}.",
        f"accounting.db{sep}.",
    ]
    # Each root .py file: bundle as loose data so sys.path-based imports work
    add_data += [f"{name}{sep}." for name in root_py]

    # --hidden-import for each root module (safety: handles dynamic imports)
    # Skip names starting with digits (e.g. "02_setup_sales") - not valid module names
    hidden = [
        os.path.splitext(name)[0] for name in root_py
        if not os.path.splitext(name)[0][0].isdigit()
    ]
    print(f"[build] hidden imports: {hidden}")

    args = [
        "--noconfirm",
        "--windowed",
        "--name", "JWSteel",
        # Where Analysis should look for modules referenced by main.py
        "--paths", cwd,
        "--paths", os.path.join(cwd, "ui"),
    ]
    for d in add_data:
        args += ["--add-data", d]
    for h in hidden:
        args += ["--hidden-import", h]
    args.append("ui/main.py")

    print("[build] PyInstaller args:")
    for a in args:
        print(f"    {a}")

    PyInstaller.__main__.run(args)

    # Verify auth_module ended up in the bundle
    dist_internal = os.path.join("dist", "JWSteel", "_internal")
    found = []
    for d, _, files in os.walk(dist_internal):
        for f in files:
            if f.startswith("auth_module"):
                found.append(os.path.join(d, f))
    print(f"[build] auth_module artifacts in dist: {found}")
    if not found:
        print("[build] WARNING: auth_module not visible in dist!")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
