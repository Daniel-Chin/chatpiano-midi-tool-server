'''
AI-generated.  
'''

from __future__ import annotations

import json
import sys
from pathlib import Path

import mido
from tqdm import tqdm

from midi_tool_server.midi_ops import extract_melody_track

INDEX_FILENAME = "maestro_index.json"


def build_index(database_root: Path) -> dict:
    maestro_root = database_root / "maestro"
    if not maestro_root.is_dir():
        raise FileNotFoundError(f"Missing maestro directory: {maestro_root}")

    entries: list[dict] = []
    year_dirs = sorted(path for path in maestro_root.glob("20??") if path.is_dir())
    n_ok = 0
    n_failed = 0
    for year_dir in year_dirs:
        midi_paths = sorted({*year_dir.glob("*.mid"), *year_dir.glob("*.midi")})
        for midi_path in tqdm(midi_paths, desc=f"Indexing {year_dir.name}"):
            midi = mido.MidiFile(midi_path)
            melody_sequence = extract_melody_track(midi)
            if melody_sequence:
                n_ok += 1
                entries.append(
                    {
                        "path": str(midi_path.resolve()),
                        "melody_sequence": melody_sequence,
                    }
                )
            else:
                n_failed += 1
                # print(
                #     f"Warning: failed to extract melody track in {midi_path}",
                #     file=sys.stderr,
                # )
    print(f'{n_ok = }, {n_failed = }')
    return {
        "database_root": str(database_root.resolve()),
        "entries": entries,
    }


def write_index(database_root: Path) -> Path:
    index_path = database_root / "maestro" / INDEX_FILENAME
    index_data = build_index(database_root)
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
