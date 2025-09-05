#!/usr/bin/env python3
"""
Update Product/Build Version in iOS backup bundle plists.

Usage:
  python update_backup_version.py /path/to/Backup.mobiletransfer [--version 17.0] [--build 21A123] [--backup]

If --version/--build are omitted, the script will interactively prompt for them.

This script updates both `Info.plist` and `Manifest.plist` at the root
of the provided backup bundle path. For `Manifest.plist`, keys are updated
under the `Lockdown` dictionary using canonical names `ProductVersion` and
`BuildVersion` (without spaces). `Info.plist` uses `Product Version` and
`Build Version` (with spaces). It preserves the original plist format
(binary or XML). Backups are opt-in via `--backup`.

Interactive flow:
- Reads and shows current Product/Build versions from both plists first.
- Asks for confirmation (Y/N) to overwrite, then prompts for new values if needed.
"""

import argparse
import os
import plistlib
import shutil
import sys
import tempfile


def detect_plist_format(path: str) -> str:
    """Return plistlib.FMT_BINARY or plistlib.FMT_XML based on file signature."""
    try:
        with open(path, 'rb') as f:
            header = f.read(8)
        if header.startswith(b"bplist00"):
            return plistlib.FMT_BINARY
        return plistlib.FMT_XML
    except FileNotFoundError:
        raise


def load_plist(path: str):
    with open(path, 'rb') as f:
        return plistlib.load(f)


def atomic_write_plist(path: str, data, fmt) -> None:
    """Write plist atomically, preserving permissions when possible."""
    dname = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".plist.tmp_", dir=dname)
    os.close(fd)
    try:
        with open(tmp_path, 'wb') as f:
            plistlib.dump(data, f, fmt=fmt)
        # Preserve original mode if file exists
        try:
            st = os.stat(path)
            os.chmod(tmp_path, st.st_mode)
        except FileNotFoundError:
            pass
        os.replace(tmp_path, path)
    finally:
        # If replace failed for any reason, ensure tmp is removed
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def backup_file(path: str) -> str:
    bak_path = path + ".bak"
    if not os.path.exists(bak_path):
        shutil.copy2(path, bak_path)
    return bak_path


def set_key_if_changed(plist_data, key: str, value: str) -> bool:
    """Set key to value; return True if changed."""
    curr = plist_data.get(key)
    if curr == value:
        return False
    plist_data[key] = value
    return True


def ensure_path_dict(root, path_keys):
    """Ensure nested dict exists for path_keys; return the dict at that path.

    Raises ValueError if encountering a non-dict on the way.
    """
    node = root
    for k in path_keys or []:
        if k not in node:
            node[k] = {}
        if not isinstance(node[k], dict):
            raise ValueError(f"Path '{'/'.join(path_keys)}' is not a dictionary; cannot write keys there")
        node = node[k]
    return node


def update_plist(path: str, product_version: str, build_version: str, make_backup: bool = False, key_path=None, key_names=None) -> bool:
    fmt = detect_plist_format(path)
    data = load_plist(path)
    target = ensure_path_dict(data, key_path or [])
    changed = False
    prod_key = (key_names or {}).get("product", "Product Version")
    build_key = (key_names or {}).get("build", "Build Version")
    changed |= set_key_if_changed(target, prod_key, product_version)
    changed |= set_key_if_changed(target, build_key, build_version)
    if not changed:
        return False
    if make_backup:
        backup_file(path)
    atomic_write_plist(path, data, fmt)
    return True


def validate_bundle_path(bundle_path: str) -> None:
    if not os.path.exists(bundle_path):
        sys.exit(f"Error: Path does not exist: {bundle_path}")
    if not os.path.isdir(bundle_path):
        sys.exit(f"Error: Path is not a directory-like bundle: {bundle_path}")


def parse_args(argv):
    p = argparse.ArgumentParser(description="Update Product/Build Version in backup bundle plists")
    p.add_argument("bundle", help="Path to backup bundle (e.g., *.mobiletransfer)")
    p.add_argument("--version", dest="version", help="Target Product Version (e.g., 17.0)")
    p.add_argument("--build", dest="build", help="Target Build Version (e.g., 21A123)")
    p.add_argument("--backup", action="store_true", help="Create .bak files before writing")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    bundle_path = os.path.expanduser(args.bundle)
    validate_bundle_path(bundle_path)

    # Resolve required files
    
    info_path = os.path.join(bundle_path, "Info.plist")
    manifest_path = os.path.join(bundle_path, "Manifest.plist")

    missing = [p for p in (info_path, manifest_path) if not os.path.isfile(p)]
    if missing:
        msg = "\n".join(["Missing required files:"] + missing + [
            "",
            "Ensure the provided path is a backup bundle containing Info.plist and Manifest.plist.",
        ])
        sys.exit(msg)

    # Read and show current versions
    def read_versions(path: str, key_path=None, allow_alias=False):
        data = load_plist(path)
        node = data
        for k in key_path or []:
            node = node.get(k, {}) if isinstance(node, dict) else {}
        pv = bv = None
        if isinstance(node, dict):
            # Prefer canonical names; optionally check aliases
            pv = node.get("Product Version")
            bv = node.get("Build Version")
            if allow_alias:
                if pv is None:
                    pv = node.get("ProductVersion")
                if bv is None:
                    bv = node.get("BuildVersion")
        return pv, bv

    info_pv, info_bv = read_versions(info_path, None, allow_alias=True)
    # For Manifest, canonical keys typically have no spaces
    man_pv, man_bv = read_versions(manifest_path, ["Lockdown"], allow_alias=True)

    print("Current values:")
    print(f"- Info.plist: Product Version={info_pv!r}, Build Version={info_bv!r}")
    print(f"- Manifest.plist/Lockdown: ProductVersion={man_pv!r}, BuildVersion={man_bv!r}")

    # Confirm overwrite
    try:
        confirm = input("Overwrite with new version? (Y/N): ").strip().lower()
    except EOFError:
        confirm = "n"
    if confirm not in ("y", "yes"):
        print("Cancelled. No changes made.")
        return 0

    # Gather target versions
    version = args.version
    if not version:
        try:
            version = input("Enter Product Version (e.g., 17.0): ").strip()
        except EOFError:
            version = ""
    if not version:
        sys.exit("Error: No Product Version provided. Use --version or interactive prompt.")

    build = args.build
    if not build:
        try:
            build = input("Enter Build Version (e.g., 21A123): ").strip()
        except EOFError:
            build = ""
    if not build:
        sys.exit("Error: No Build Version provided. Use --build or interactive prompt.")

    updated_any = False
    for plist_path, label, key_path, key_names in (
        (info_path, "Info.plist", None, {"product": "Product Version", "build": "Build Version"}),
        (manifest_path, "Manifest.plist", ["Lockdown"], {"product": "ProductVersion", "build": "BuildVersion"}),
    ):
        try:
            changed = update_plist(
                plist_path,
                version,
                build,
                make_backup=args.backup,
                key_path=key_path,
                key_names=key_names,
            )
            if changed:
                print(f"Updated {label}: Product Version -> {version}, Build Version -> {build}")
                updated_any = True
            else:
                print(f"{label} already has target versions. No change.")
        except Exception as e:
            sys.exit(f"Failed to update {label}: {e}")

    if updated_any:
        print("Done: Plists updated as requested.")
    else:
        print("No changes: Both plists already contained target versions.")


if __name__ == "__main__":
    main()
