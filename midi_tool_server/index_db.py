'''
AI-generated.  
'''

from __future__ import annotations

import json
import sys
from pathlib import Path
import typing as tp

import mido
from tqdm import tqdm

from midi_tool_server.shared import INDEX_POP909
from midi_tool_server.midi_ops import extract_melody_track
from midi_tool_server.dataset_iter import iter_pop909


def build_index(iter_dataset: tp.Iterable[Path]) -> list[dict]:
    entries: list[dict] = []
    n_ok = 0
    n_failed = 0
    for midi_path in tqdm([*iter_dataset]):
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
    return entries


def write_index(
    iter_dataset: tp.Iterable[Path], 
    database_root: Path, 
    index_path: Path,
) -> None:
    entries = build_index(iter_dataset)
    index_path.write_text(json.dumps({
        "database_root": str(database_root.resolve()),
        "entries": entries,
    }, indent=2), encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: midi-db-index /abs/path/to/pop909_dataset", file=sys.stderr)
        raise SystemExit(1)
    database_root = Path(sys.argv[1]).expanduser()
    write_index(
        iter_pop909(database_root),
        database_root, 
        INDEX_POP909,
    )
    print(f"Wrote index to {INDEX_POP909}")


if __name__ == "__main__":
    main()
