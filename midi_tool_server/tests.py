from __future__ import annotations

import json
from pathlib import Path

import requests

from midi_tool_server.shared import PORT

POP909_PATH = Path('~/POP909-Dataset').expanduser()

def test_swing():
    midi_in_path = POP909_PATH / 'POP909' / '001' / '001.mid'
    url = f'http://localhost:{PORT}/v1/midi/common-to-swing'
    response = requests.post(url, json={
        'path_to_original_midi': str(midi_in_path),
    })
    assert response.status_code == 200, f'{response.status_code=}, {response.text=}'
    data = response.json()
    assert data['ok']
    swung_midi_info = data['result']
    print(json.dumps(swung_midi_info, indent=2))

def tests():
    test_swing()

if __name__ == "__main__":
    tests()
