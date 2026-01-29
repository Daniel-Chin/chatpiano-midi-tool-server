"""
AI-generated.  
Download and extract the MAESTRO v3.0.0 MIDI dataset.

The MAESTRO dataset contains ~1,276 MIDI files of classical piano
performances with metadata including composer, title, and year.
"""

import hashlib
import logging
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

# MAESTRO v3.0.0 MIDI-only package
MAESTRO_URL = "https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0/maestro-v3.0.0-midi.zip"
MAESTRO_ZIP_FILENAME = "maestro-v3.0.0-midi.zip"

# Expected SHA256 hash for verification (optional, can be None to skip)
MAESTRO_SHA256 = None  # The official source doesn't provide hash

# Default data directory relative to this package
DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data" / "maestro"


def get_file_size(url: str) -> Optional[int]:
    """Get the file size from HTTP headers.

    Args:
        url: URL to query.

    Returns:
        File size in bytes, or None if not available.
    """
    try:
        request = Request(url, method="HEAD")
        with urlopen(request, timeout=10) as response:
            content_length = response.headers.get("Content-Length")
            if content_length:
                return int(content_length)
    except Exception:
        pass
    return None


def format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def download_file(
    url: str,
    dest: Path,
    chunk_size: int = 8192,
    show_progress: bool = True,
) -> None:
    """Download a file from URL with progress indication.

    Args:
        url: URL to download from.
        dest: Destination path for the downloaded file.
        chunk_size: Size of download chunks in bytes.
        show_progress: Whether to show download progress.

    Raises:
        URLError: If the download fails.
        IOError: If writing to disk fails.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Get file size for progress
    total_size = get_file_size(url)
    if show_progress and total_size:
        print(f"Downloading: {dest.name} ({format_size(total_size)})")
    elif show_progress:
        print(f"Downloading: {dest.name}")

    try:
        request = Request(url)
        request.add_header("User-Agent", "Mozilla/5.0")

        with urlopen(request, timeout=60) as response:
            downloaded = 0
            last_percent = -1

            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)

                    # Show progress
                    if show_progress and total_size:
                        percent = int(100 * downloaded / total_size)
                        if percent != last_percent and percent % 5 == 0:
                            progress_bar = "=" * (percent // 2) + ">" + " " * (50 - percent // 2)
                            sys.stdout.write(
                                f"\r  [{progress_bar}] {percent}% "
                                f"({format_size(downloaded)}/{format_size(total_size)})"
                            )
                            sys.stdout.flush()
                            last_percent = percent

        if show_progress:
            print()  # New line after progress
            print(f"Download complete: {dest}")

    except HTTPError as e:
        raise URLError(f"HTTP Error {e.code}: {e.reason}") from e
    except Exception as e:
        # Clean up partial download
        if dest.exists():
            dest.unlink()
        raise


def verify_checksum(file_path: Path, expected_hash: str) -> bool:
    """Verify SHA256 checksum of a file.

    Args:
        file_path: Path to the file to verify.
        expected_hash: Expected SHA256 hash (hex string).

    Returns:
        True if hash matches, False otherwise.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    actual_hash = sha256.hexdigest()
    return actual_hash.lower() == expected_hash.lower()


def extract_zip(
    zip_path: Path,
    extract_dir: Path,
    show_progress: bool = True,
) -> None:
    """Extract a ZIP file to the specified directory.

    Args:
        zip_path: Path to the ZIP file.
        extract_dir: Directory to extract to.
        show_progress: Whether to show extraction progress.

    Raises:
        zipfile.BadZipFile: If the ZIP file is corrupted.
    """
    if show_progress:
        print(f"Extracting: {zip_path.name}")

    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.namelist()
        total = len(members)

        for i, member in enumerate(members):
            if show_progress and ((i + 1) % 100 == 0 or i == total - 1):
                percent = int(100 * (i + 1) / total)
                sys.stdout.write(f"\r  Extracting: {i + 1}/{total} ({percent}%)")
                sys.stdout.flush()

            zf.extract(member, extract_dir)

    if show_progress:
        print()
        print(f"Extraction complete: {extract_dir}")


def count_midi_files(directory: Path) -> int:
    """Count MIDI files in a directory recursively."""
    count = 0
    for ext in ["*.mid", "*.midi", "*.MID", "*.MIDI"]:
        count += len(list(directory.rglob(ext)))
    return count


def main(
    data_dir: Optional[Path] = None,
    force_download: bool = False,
    keep_zip: bool = False,
) -> None:
    """Download and extract the MAESTRO MIDI dataset.

    Args:
        data_dir: Directory to store the data. Defaults to tools/query_midi/data/maestro/.
        force_download: If True, re-download even if files exist.
        keep_zip: If True, keep the ZIP file after extraction.
    """
    if data_dir is None:
        data_dir = DEFAULT_DATA_DIR

    data_dir = Path(data_dir)
    zip_path = data_dir / MAESTRO_ZIP_FILENAME

    print("=" * 60)
    print("MAESTRO v3.0.0 MIDI Dataset Downloader")
    print("=" * 60)
    print(f"Source: {MAESTRO_URL}")
    print(f"Target: {data_dir}")
    print()

    # Check if already downloaded and extracted
    if data_dir.exists() and not force_download:
        midi_count = count_midi_files(data_dir)
        if midi_count > 0:
            print(f"Dataset already exists with {midi_count} MIDI files.")
            print("Use --force to re-download.")
            return

    # Create data directory
    data_dir.mkdir(parents=True, exist_ok=True)

    # Download ZIP file
    if not zip_path.exists() or force_download:
        try:
            download_file(MAESTRO_URL, zip_path)
        except URLError as e:
            print(f"Error downloading dataset: {e}")
            print("\nYou can manually download from:")
            print(f"  {MAESTRO_URL}")
            print(f"\nAnd place the file at:")
            print(f"  {zip_path}")
            return
    else:
        print(f"Using existing ZIP file: {zip_path}")

    # Verify checksum if available
    if MAESTRO_SHA256:
        print("Verifying checksum...")
        if verify_checksum(zip_path, MAESTRO_SHA256):
            print("Checksum verified.")
        else:
            print("WARNING: Checksum mismatch! The file may be corrupted.")
            print("Continuing anyway...")

    # Extract ZIP
    try:
        extract_zip(zip_path, data_dir)
    except zipfile.BadZipFile as e:
        print(f"Error extracting ZIP file: {e}")
        print("The download may have been corrupted. Try again with --force")
        return

    # Move contents from nested directory if needed
    # MAESTRO ZIP extracts to maestro-v3.0.0/ subdirectory
    nested_dir = data_dir / "maestro-v3.0.0"
    if nested_dir.exists():
        print("Moving files from nested directory...")
        for item in nested_dir.iterdir():
            dest = data_dir / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))
        nested_dir.rmdir()

    # Clean up ZIP file
    if not keep_zip and zip_path.exists():
        print(f"Removing ZIP file: {zip_path}")
        zip_path.unlink()

    # Verify extraction
    midi_count = count_midi_files(data_dir)
    csv_files = list(data_dir.glob("*.csv"))

    print()
    print("=" * 60)
    print("Download and extraction complete!")
    print("=" * 60)
    print(f"  MIDI files: {midi_count}")
    print(f"  CSV files: {len(csv_files)}")
    print(f"  Location: {data_dir}")

    if csv_files:
        print(f"  Metadata: {csv_files[0].name}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Download and extract the MAESTRO v3.0.0 MIDI dataset."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help=f"Directory to store data (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if files exist.",
    )
    parser.add_argument(
        "--keep-zip",
        action="store_true",
        help="Keep the ZIP file after extraction.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    main(
        data_dir=args.data_dir,
        force_download=args.force,
        keep_zip=args.keep_zip,
    )
