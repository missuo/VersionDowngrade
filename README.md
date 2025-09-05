# iOS Backup Version Patcher

A small Python utility to edit the Product/Build versions inside iPhone/iPad backup bundles so you can attempt to restore backups when downgrading iOS/iPadOS.

Important: This is not guaranteed to make a backup restorable on a downgraded system. Restores may still fail depending on the backup contents and OS constraints. Proceed at your own risk.

## What it does

- Reads current versions and shows them for confirmation.
- Updates two files in the backup bundle root:
  - `Info.plist`: sets top‑level `Product Version` and `Build Version`.
  - `Manifest.plist`: sets `Lockdown/ProductVersion` and `Lockdown/BuildVersion` (keys without spaces under the `Lockdown` dictionary).
- Preserves the original plist format (binary or XML) and writes atomically.
- Optional `.bak` file creation with `--backup`.

## Requirements

- Python 3.8+
- macOS optional tools for verification:
  - `plutil` (ships with macOS)
  - `PlistBuddy` (ships with Xcode tools)

## Usage

Interactive (recommended first run):

```
python update_backup_version.py \
  "/path/to/Your Device-YYYYMMDD-HHMM.mobiletransfer"
```

- The script will display current versions, ask “Overwrite with new version? (Y/N)”, and then prompt for new values if you confirm.

Provide versions via flags (still asks to confirm):

```
python update_backup_version.py \
  "/path/to/Your Device-YYYYMMDD-HHMM.mobiletransfer" \
  --version 17.0 --build 21A123
```

Create `.bak` backups before writing:

```
python update_backup_version.py \
  "/path/to/Your Device-YYYYMMDD-HHMM.mobiletransfer" \
  --version 17.0 --build 21A123 --backup
```

## Verifying changes

Binary plists won’t display correctly with `cat`. Use one of the following:

- `plutil` (macOS):

```
plutil -p \
  "/path/to/.../Manifest.plist" | sed -n '1,120p'

plutil -p \
  "/path/to/.../Info.plist" | sed -n '1,120p'
```

- `PlistBuddy` (macOS):

```
/usr/libexec/PlistBuddy -c "Print :Lockdown" \
  "/path/to/.../Manifest.plist"
```

## Notes and limitations

- Not a guaranteed fix: Some backups cannot be restored after downgrading due to system and app data compatibility.
- Scope is limited: Only the version keys listed above are modified; other compatibility markers (if any) are untouched.
- Atomic writes: Files are replaced atomically to reduce corruption risk. Use `--backup` if you want `.bak` copies.
- Permissions: The tool attempts to preserve original file permissions when overwriting.

## Example

Sample output flow:

```
Current values:
- Info.plist: Product Version='18.6.2', Build Version='22G100'
- Manifest.plist/Lockdown: ProductVersion='18.6.2', BuildVersion='22G100'
Overwrite with new version? (Y/N): Y
Enter Product Version (e.g., 17.0): 17.0
Enter Build Version (e.g., 21A123): 21A123
Updated Info.plist: Product Version -> 17.0, Build Version -> 21A123
Updated Manifest.plist: Product Version -> 17.0, Build Version -> 21A123
Done: Plists updated as requested.
```

## License

No license specified. Use at your own risk.

