from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from uuid import uuid4

import mido


@dataclass(frozen=True)
class MidiMeta:
    bpm: float
    numerator: int
    denominator: int


def _ensure_exists(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")


def _generate_output_path(original_path: Path, suffix: str) -> Path:
    output_dir = original_path.parent
    stem = original_path.stem
    extension = original_path.suffix or ".mid"
    for _ in range(10):
        candidate = output_dir / f"{stem}-{suffix}-{uuid4().hex[:8]}{extension}"
        if not candidate.exists():
            return candidate.resolve()
    raise FileExistsError("Failed to generate a unique output path.")


def _get_midi_meta(midi: mido.MidiFile) -> MidiMeta:
    bpm = 120.0
    numerator = 4
    denominator = 4
    for track in midi.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                bpm = mido.tempo2bpm(msg.tempo)
            if msg.type == "time_signature":
                numerator = msg.numerator
                denominator = msg.denominator
        if bpm != 120.0 or (numerator, denominator) != (4, 4):
            break
    return MidiMeta(bpm=bpm, numerator=numerator, denominator=denominator)


def change_tempo(path: Path, ratio: float) -> Path:
    _ensure_exists(path)
    if ratio <= 0:
        raise ValueError("ratio must be > 0")
    midi = mido.MidiFile(path)
    for track in midi.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                msg.tempo = max(1, int(msg.tempo / ratio))
    output_path = _generate_output_path(path, "tempo")
    midi.save(output_path)
    return output_path


def transpose(path: Path, delta: int) -> Path:
    _ensure_exists(path)
    midi = mido.MidiFile(path)
    for track in midi.tracks:
        for msg in track:
            if msg.type in {"note_on", "note_off"}:
                msg.note = max(0, min(127, msg.note + delta))
    output_path = _generate_output_path(path, "transpose")
    midi.save(output_path)
    return output_path


def common_to_swing(path: Path) -> Path:
    _ensure_exists(path)
    midi = mido.MidiFile(path)
    meta = _get_midi_meta(midi)
    ticks_per_beat = midi.ticks_per_beat
    beats_per_measure = meta.numerator * (4 / meta.denominator)
    measure_ticks = ticks_per_beat * beats_per_measure
    beat_ticks = ticks_per_beat

    def warp_time(abs_time: int) -> int:
        if beat_ticks <= 0:
            return abs_time
        measure_index = int(abs_time // measure_ticks)
        time_in_measure = abs_time - measure_index * measure_ticks
        beat_index = int(time_in_measure // beat_ticks)
        time_in_beat = time_in_measure - beat_index * beat_ticks
        half_beat = beat_ticks / 2
        if time_in_beat <= half_beat:
            new_time_in_beat = time_in_beat * (2 / 3) / 0.5
        else:
            new_time_in_beat = (2 / 3) * beat_ticks + (time_in_beat - half_beat) * (
                1 / 3
            ) / 0.5
        return int(round(measure_index * measure_ticks + beat_index * beat_ticks + new_time_in_beat))

    new_tracks: list[mido.MidiTrack] = []
    for track in midi.tracks:
        abs_events: list[tuple[int, int, mido.Message]] = []
        abs_time = 0
        for idx, msg in enumerate(track):
            abs_time += msg.time
            abs_events.append((abs_time, idx, msg))
        warped_events: list[tuple[int, int, mido.Message]] = []
        for abs_time, idx, msg in abs_events:
            warped_events.append((warp_time(abs_time), idx, msg))
        warped_events.sort(key=lambda item: (item[0], item[1]))
        new_track = mido.MidiTrack()
        last_time = 0
        for abs_time, _, msg in warped_events:
            new_msg = msg.copy(time=max(0, abs_time - last_time))
            new_track.append(new_msg)
            last_time = abs_time
        new_tracks.append(new_track)

    swung = mido.MidiFile(ticks_per_beat=midi.ticks_per_beat)
    swung.tracks.extend(new_tracks)
    output_path = _generate_output_path(path, "swing")
    swung.save(output_path)
    return output_path


def extract_melody_track(midi: mido.MidiFile) -> list[int]:
    melody_tracks = [
        track
        for track in midi.tracks
        if track.name and "melody" in track.name.lower()
    ]
    if len(melody_tracks) != 1:
        return []
    return extract_pitch_sequence(melody_tracks[0])


def extract_pitch_sequence(track: Iterable[mido.Message]) -> list[int]:
    sequence: list[int] = []
    for msg in track:
        if msg.type == "note_on" and msg.velocity > 0:
            sequence.append(msg.note)
    return sequence
