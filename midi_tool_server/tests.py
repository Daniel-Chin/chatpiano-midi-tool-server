from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import mido
import requests

from midi_tool_server.shared import PORT

POP909_PATH = Path('~/POP909-Dataset').expanduser()


BASE_URL = f'http://localhost:{PORT}'


def _require_server() -> None:
    try:
        response = requests.get(f'{BASE_URL}/openapi.json', timeout=(1, 5))
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Server not reachable at {BASE_URL}. Start it with: `uv run midi-tool-server`"
        ) from exc
    assert response.status_code == 200, f"Unexpected status from /openapi.json: {response.status_code}"


def _post_json(path: str, payload: dict[str, Any]) -> requests.Response:
    return requests.post(
        f'{BASE_URL}{path}',
        json=payload,
        timeout=(2, 120),
    )


def _assert_ok_response(response: requests.Response) -> dict[str, Any]:
    assert response.status_code == 200, f'{response.status_code=}, {response.text=}'
    data = response.json()
    assert data.get('ok') is True, f'Expected ok=true, got: {data}'
    assert 'result' in data and isinstance(data['result'], dict), f'Bad result shape: {data}'
    return data['result']


def _assert_error_response(
    response: requests.Response,
    *,
    status_code: int,
    code: str,
) -> dict[str, Any]:
    assert response.status_code == status_code, f'{response.status_code=}, {response.text=}'
    data = response.json()
    assert data.get('ok') is False, f'Expected ok=false, got: {data}'
    err = data.get('error')
    assert isinstance(err, dict), f'Expected error object, got: {data}'
    assert err.get('code') == code, f"Expected error.code={code!r}, got: {err}"
    assert isinstance(err.get('message'), str) and err['message'], f'Bad error.message: {err}'
    assert isinstance(err.get('details'), dict), f'Bad error.details: {err}'
    return err


def _write_minimal_midi(path: Path, *, note: int = 60, tempo: int = 500_000) -> None:
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))
    track.append(mido.Message('note_on', note=note, velocity=64, time=0))
    track.append(mido.Message('note_off', note=note, velocity=64, time=480))
    track.append(mido.Message('note_on', note=note+2, velocity=64, time=100))
    track.append(mido.Message('note_off', note=note+2, velocity=64, time=480))
    track.append(mido.Message('note_on', note=note+3, velocity=64, time=100))
    track.append(mido.Message('note_off', note=note+3, velocity=64, time=480))
    midi.save(path)


def _extract_first_tempo(path: Path) -> int | None:
    midi = mido.MidiFile(path)
    for track in midi.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                return int(msg.tempo)
    return None


def _extract_first_note_on(path: Path) -> int | None:
    midi = mido.MidiFile(path)
    for track in midi.tracks:
        for msg in track:
            if msg.type == 'note_on' and getattr(msg, 'velocity', 0) > 0:
                return int(msg.note)
    return None

def test_swing():
    _require_server()
    midi_in_path = POP909_PATH / 'POP909' / '001' / '001.mid'
    url = f'http://localhost:{PORT}/v1/midi/common-to-swing'
    response = requests.post(url, json={
        'path_to_original_midi': str(midi_in_path),
    }, timeout=(2, 120))
    result = _assert_ok_response(response)
    output_path = Path(result['path_to_output_midi'])
    assert output_path.exists(), f'Output not found: {output_path}'


def test_change_tempo_success():
    _require_server()
    with tempfile.TemporaryDirectory() as td:
        midi_in_path = Path(td) / 'in.mid'
        _write_minimal_midi(midi_in_path, note=60, tempo=500_000)
        response = _post_json(
            '/v1/midi/change-tempo',
            {'path_to_original_midi': str(midi_in_path), 'ratio': 2.0},
        )
        result = _assert_ok_response(response)
        output_path = Path(result['path_to_output_midi'])
        assert output_path.exists(), f'Output not found: {output_path}'
        assert output_path.is_absolute(), f'Expected absolute output path, got: {output_path}'
        in_tempo = _extract_first_tempo(midi_in_path)
        out_tempo = _extract_first_tempo(output_path)
        assert in_tempo is not None and out_tempo is not None
        assert out_tempo == max(1, int(in_tempo / 2.0))


def test_change_tempo_invalid_ratio_400():
    _require_server()
    with tempfile.TemporaryDirectory() as td:
        midi_in_path = Path(td) / 'in.mid'
        _write_minimal_midi(midi_in_path)
        response = _post_json(
            '/v1/midi/change-tempo',
            {'path_to_original_midi': str(midi_in_path), 'ratio': 0},
        )
        err = _assert_error_response(response, status_code=400, code='INVALID_ARGUMENT')
        # For schema validation errors, server includes pydantic error details
        if 'errors' in err.get('details', {}):
            assert isinstance(err['details']['errors'], list)


def test_transpose_success():
    _require_server()
    with tempfile.TemporaryDirectory() as td:
        midi_in_path = Path(td) / 'in.mid'
        _write_minimal_midi(midi_in_path, note=60)
        response = _post_json(
            '/v1/midi/transpose',
            {'path_to_original_midi': str(midi_in_path), 'delta_in_semitones': 12},
        )
        result = _assert_ok_response(response)
        output_path = Path(result['path_to_output_midi'])
        assert output_path.exists(), f'Output not found: {output_path}'
        out_note = _extract_first_note_on(output_path)
        assert out_note == 72


def test_common_to_swing_file_not_found_404():
    _require_server()
    response = _post_json(
        '/v1/midi/common-to-swing',
        {'path_to_original_midi': '/definitely/not/a/real/file.mid'},
    )
    _assert_error_response(response, status_code=404, code='FILE_NOT_FOUND')


def test_hard_match_dir_not_found_404():
    _require_server()
    response = _post_json(
        '/v1/midi/retrieval/hard-match',
        {
            'path_to_midi_database': '/definitely/not/a/real/dir',
            'path_to_query_midi_segment': '/definitely/not/a/real/file.mid',
        },
    )
    _assert_error_response(response, status_code=404, code='FILE_NOT_FOUND')


def test_hard_match_query_not_found_404():
    _require_server()
    with tempfile.TemporaryDirectory() as td:
        response = _post_json(
            '/v1/midi/retrieval/hard-match',
            {
                'path_to_midi_database': td,
                'path_to_query_midi_segment': str(Path(td) / 'missing.mid'),
            },
        )
        _assert_error_response(response, status_code=404, code='FILE_NOT_FOUND')


def test_hard_match_success_pop909():
    _require_server()
    midi_in_path = POP909_PATH / 'POP909' / '001' / '001.mid'
    if not midi_in_path.exists():
        print(f'SKIP: POP909 not found at {POP909_PATH}')
        return
    response = _post_json(
        '/v1/midi/retrieval/hard-match',
        {
            'path_to_midi_database': str(POP909_PATH),
            'path_to_query_midi_segment': str(midi_in_path),
        },
    )
    result = _assert_ok_response(response)
    matches = result['paths_to_matched_song']
    assert isinstance(matches, list)
    assert str(midi_in_path) in matches, 'Expected query song to match itself'
    assert all(Path(p).is_absolute() for p in matches)
    assert all(str(p).startswith(str(POP909_PATH)) for p in matches)

def tests():
    # Integration tests: require the server running locally.
    test_change_tempo_success()
    test_change_tempo_invalid_ratio_400()
    test_transpose_success()
    test_swing()
    test_common_to_swing_file_not_found_404()
    test_hard_match_dir_not_found_404()
    test_hard_match_query_not_found_404()
    test_hard_match_success_pop909()

if __name__ == "__main__":
    tests()
