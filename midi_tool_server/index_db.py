'''
AI-generated.  
'''

from __future__ import annotations

import json
import sys
from pathlib import Path

import mido

from midi_tool_server.midi_ops import extract_melody_track

INDEX_FILENAME = "maestro_index.json"


def build_index(database_root: Path) -> dict:
    maestro_root = database_root / "maestro"
    if not maestro_root.is_dir():
        raise FileNotFoundError(f"Missing maestro directory: {maestro_root}")

    entries: list[dict] = []
    year_dirs = sorted(path for path in maestro_root.glob("20??") if path.is_dir())
    for year_dir in year_dirs:
        for midi_path in sorted(year_dir.glob("*.mid")):
            midi = mido.MidiFile(midi_path)
            melody_sequence = extract_melody_track(midi)
            if not melody_sequence:
                print(
                    f"Warning: expected exactly one melody track in {midi_path}",
                    file=sys.stderr,
                )
            entries.append(
                {
                    "path": str(midi_path.resolve()),
                    "melody_sequence": melody_sequence,
                }
            )
    return {
        "database_root": str(database_root.resolve()),
        "entries": entries,
    }


def write_index(database_root: Path) -> Path:
    index_data = build_index(database_root)
    index_path = database_root / "maestro" / INDEX_FILENAME
    index_path.write_text(json.dumps(index_data, indent=2), encoding="utf-8")
    return index_path


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: midi-db-index /abs/path/to/midi_database", file=sys.stderr)
        raise SystemExit(1)
    database_root = Path(sys.argv[1]).expanduser()
    index_path = write_index(database_root)
    print(f"Wrote index to {index_path}")


if __name__ == "__main__":
    main()
