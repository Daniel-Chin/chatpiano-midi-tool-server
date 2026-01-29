import typing as tp
from pathlib import Path

def iter_maestro(path_to_maestro: Path) -> tp.Iterable[Path]:
    path_to_maestro = path_to_maestro.expanduser()
    maestro_root = path_to_maestro / "maestro"
    if not maestro_root.is_dir():
        raise FileNotFoundError(f"Missing maestro directory: {maestro_root}")

    year_dirs = sorted(path for path in maestro_root.glob("20??") if path.is_dir())
    for year_dir in year_dirs:
        midi_paths = sorted({*year_dir.glob("*.mid"), *year_dir.glob("*.midi")})
        for midi_path in midi_paths:
            yield midi_path.resolve()

def iter_pop909(path_to_pop909_dataset: Path) -> tp.Iterable[Path]:
    path_to_pop909_dataset = path_to_pop909_dataset.expanduser()
    for song_dir in sorted((path_to_pop909_dataset / 'POP909').iterdir(), key=lambda p: p.name):
        if not song_dir.is_dir():
            continue
        if song_dir.name.startswith("."):
            continue

        midi_paths = sorted({*song_dir.glob("*.mid"), *song_dir.glob("*.midi")})
        if len(midi_paths) != 1:
            raise FileNotFoundError(
                f"Expected exactly 1 MIDI file in {song_dir}, found {len(midi_paths)}"
            )

        yield midi_paths[0].resolve()

def test():
    for i, path in enumerate(
        iter_pop909(Path("~/POP909-Dataset"))
    ):
        if i < 5:
            print(path)
    for i, path in enumerate(
        iter_maestro(Path("~"))
    ):
        if i < 5:
            print(path)

if __name__ == "__main__":
    test()
