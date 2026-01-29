'''
AI-generated.  
'''

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
    output_dir = Path(__file__).parent.parent / "output"
    stem = original_path.stem
    extension = ".mid"
    while True:
        candidate = output_dir / f"{stem}-{suffix}-{uuid4().hex[:8]}{extension}"
        if not candidate.exists():
            return candidate.resolve()


def _get_midi_meta(midi: mido.MidiFile) -> MidiMeta:
    bpm = None
    numerator = None
    denominator = None
    for track in midi.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                bpm = mido.tempo2bpm(msg.tempo)
            if msg.type == "time_signature":
                numerator = msg.numerator
                denominator = msg.denominator
        if bpm is not None and numerator is not None and denominator is not None:
            break
    # todo: use existing library for smart detection
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
    def try_tracks(tracks: Iterable[mido.MidiTrack]) -> list[int] | None:
        t_s = [
            (track, extract_pitch_sequence(track))
            for track in tracks
        ]
        strong_candidates = [(t, s) for t, s in t_s if s is not None and len(s) > 3]
        if not strong_candidates:
            return None
        # pick the longest
        strong_candidates.sort(key=lambda item: len(item[1]), reverse=True)
        return strong_candidates[0][1]

    tracks = [((t.name or '').lower(), t) for t in midi.tracks]
    candidates = []
    remaining = []
    for name, track in tracks:
        if 'melody' in name or name == 'mel':
            candidates.append(track)
        else:
            remaining.append((name, track))
    results = try_tracks(candidates)
    if results is not None:
        return results
    tracks = remaining
    
    candidates = []
    remaining = []
    for name, track in tracks:
        if 'lead' in name:
            candidates.append(track)
        else:
            remaining.append((name, track))
    results = try_tracks(candidates)
    if results is not None:
        return results
    tracks = remaining

    results = try_tracks([track for name, track in tracks])
    if results is not None:
        return results
    
    try:
        pop909_mel_track, = [t for t in midi.tracks if t.name == 'MELODY']
    except ValueError:
        print('Warning: no melody track found:', [t.name for t in midi.tracks])
        return []
    print('Warning: not strictly monophonic.')
    results = extract_pitch_sequence(pop909_mel_track, 99999.0)
    assert results is not None
    return results


def extract_pitch_sequence(
    track: Iterable[mido.Message], 
    monophonicity_tolerance_sec: float = 0.1,
) -> list[int] | None:
    sequence: list[int] = []
    active_notes = dict[int, float]()
    for msg in track:
        if msg.type == "note_on" and msg.velocity > 0:
            if msg.note in active_notes:
                continue    # nobody cares
            sequence.append(msg.note)
            active_notes[msg.note] = msg.time
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            if msg.note not in active_notes:
                print('Warning: note_off for inactive note')
                continue
            active_notes.pop(msg.note)
            for _, other_start_time in active_notes.items():
                if msg.time - other_start_time >= monophonicity_tolerance_sec:
                    return None
    return sequence
