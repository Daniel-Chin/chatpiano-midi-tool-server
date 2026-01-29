'''
AI-generated.  
'''

from __future__ import annotations

from pathlib import Path
from typing import Iterable
from uuid import uuid4
import math

import mido
import pretty_midi


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


def change_tempo(path: Path, ratio: float) -> Path:
    _ensure_exists(path)
    if ratio <= 0:
        raise ValueError("ratio must be > 0")
    midi = mido.MidiFile(path)
    has_tempo_meta = False
    for track in midi.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                has_tempo_meta = True
                msg.tempo = max(1, int(msg.tempo / ratio))
    if not has_tempo_meta:
        new_midi = mido.MidiFile()
        for track in midi.tracks:
            new_track = mido.MidiTrack()
            new_midi.tracks.append(new_track)
            tick_rounded = 0
            tick_precise = 0.0
            for msg in track:
                tick_precise += msg.time / ratio
                new_tick = int(round(tick_precise))
                delta_tick = new_tick - tick_rounded
                tick_rounded = new_tick
                new_msg = msg.copy(time=delta_tick)
                new_track.append(new_msg)
        midi = new_midi
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


def _post_process_bpm(bpm_estimated_by_pretty_midi: float) -> float:
    REFERENCE = 120.0
    if bpm_estimated_by_pretty_midi <= 0.0:
        return REFERENCE
    expon = math.log2(bpm_estimated_by_pretty_midi / REFERENCE)
    remainder = expon % 1.0
    if remainder > 0.5:
        remainder -= 1.0
    return REFERENCE * (2 ** remainder)

def _test_post_process_bpm():
    from matplotlib import pyplot as plt
    xs = [i for i in range(30, 301)]
    ys = [_post_process_bpm(x) for x in xs]
    plt.plot(xs, ys)
    plt.xlim(0, 310)
    plt.ylim(0, 200)
    plt.show()

def common_to_swing(path: Path) -> Path:
    _ensure_exists(path)
    midi = mido.MidiFile(path)
    e_tempo = pretty_midi.PrettyMIDI(str(path)).estimate_tempo()
    bpm = _post_process_bpm(e_tempo)
    beats_per_bar = 2   # assumed

    # cached vars
    beats_per_sec = bpm / 60.0
    sec_per_bar = beats_per_bar / beats_per_sec
    microsec_per_beat = 60_000_000 / bpm

    def time_remap(t: float) -> float:
        n_bar = int(t / sec_per_bar)
        bar_start = n_bar * sec_per_bar
        t_in_bar = t - bar_start
        ratio_in_bar = t_in_bar / sec_per_bar
        if ratio_in_bar < 0.5:
            new_ratio = ratio_in_bar * 4 / 3.0
        else:
            new_ratio = 0.5 + (ratio_in_bar - 0.5) * 2 / 3.0
        return bar_start + new_ratio * sec_per_bar
    
    new_midi = mido.MidiFile()
    new_midi.ticks_per_beat = midi.ticks_per_beat
    for track in midi.tracks:
        new_track = mido.MidiTrack()
        new_midi.tracks.append(new_track)
        old_abs_time = 0.0
        new_ticks_acc = 0
        for msg in track:
            old_abs_time += mido.tick2second(msg.time, midi.ticks_per_beat, microsec_per_beat)
            new_abs_time = time_remap(old_abs_time)
            new_tick = mido.second2tick(new_abs_time, midi.ticks_per_beat, microsec_per_beat)
            new_delta_tick = new_tick - new_ticks_acc
            new_ticks_acc = new_tick
            new_msg = msg.copy(time=new_delta_tick)
            new_track.append(new_msg)
    output_path = _generate_output_path(path, "swing")
    new_midi.save(output_path)
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
    abs_tick = 0.0
    for msg in track:
        abs_tick += mido.tick2second(msg.time, 480, 500000)  # assuming 120bpm, 480ppq
        if msg.type == "note_on" and msg.velocity > 0:
            if msg.note in active_notes:
                continue    # nobody cares
            sequence.append(msg.note)
            active_notes[msg.note] = abs_tick
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            if msg.note not in active_notes:
                print('Warning: note_off for inactive note')
                continue
            active_notes.pop(msg.note)
            for _, other_start_time in active_notes.items():
                if abs_tick - other_start_time >= monophonicity_tolerance_sec:
                    return None
    return sequence

if __name__ == "__main__":
    _test_post_process_bpm()
