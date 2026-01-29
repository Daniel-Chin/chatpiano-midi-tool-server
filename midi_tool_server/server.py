'''
AI-generated.  
'''

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import mido
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

from midi_tool_server.shared import PORT
from midi_tool_server.midi_ops import (
    change_tempo,
    common_to_swing,
    extract_pitch_sequence,
    transpose,
)


class ChangeTempoRequest(BaseModel):
    path_to_original_midi: str
    ratio: float = Field(default=1.0, gt=0)


class TransposeRequest(BaseModel):
    path_to_original_midi: str
    delta_in_semitones: int = 0


class CommonToSwingRequest(BaseModel):
    path_to_original_midi: str


class HardMatchRequest(BaseModel):
    path_to_midi_database: str
    path_to_query_midi_segment: str


def ok_response(result: dict[str, Any]) -> JSONResponse:
    return JSONResponse({"ok": True, "result": result})


def error_response(
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        {
            "ok": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
        },
        status_code=status_code,
    )


app = FastAPI()


@app.exception_handler(FileNotFoundError)
async def handle_file_not_found(_: Request, exc: FileNotFoundError) -> JSONResponse:
    return error_response(
        "FILE_NOT_FOUND", str(exc), status.HTTP_404_NOT_FOUND, details={}
    )


@app.exception_handler(ValueError)
async def handle_value_error(_: Request, exc: ValueError) -> JSONResponse:
    return error_response(
        "INVALID_ARGUMENT", str(exc), status.HTTP_400_BAD_REQUEST, details={}
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    return error_response(
        "INVALID_ARGUMENT",
        "Invalid request payload",
        status.HTTP_400_BAD_REQUEST,
        details={"errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def handle_exception(_: Request, exc: Exception) -> JSONResponse:
    return error_response(
        "INTERNAL_ERROR", "Unhandled server failure", status.HTTP_500_INTERNAL_SERVER_ERROR
    )


@app.post("/v1/midi/change-tempo")
def change_tempo_endpoint(payload: ChangeTempoRequest) -> JSONResponse:
    output_path = change_tempo(Path(payload.path_to_original_midi), payload.ratio)
    return ok_response({"path_to_output_midi": str(output_path)})


@app.post("/v1/midi/transpose")
def transpose_endpoint(payload: TransposeRequest) -> JSONResponse:
    output_path = transpose(
        Path(payload.path_to_original_midi), payload.delta_in_semitones
    )
    return ok_response({"path_to_output_midi": str(output_path)})


@app.post("/v1/midi/common-to-swing")
def swing_endpoint(payload: CommonToSwingRequest) -> JSONResponse:
    output_path = common_to_swing(Path(payload.path_to_original_midi))
    return ok_response({"path_to_output_midi": str(output_path)})


def _load_index(database_root: Path) -> dict:
    index_path = database_root / "maestro" / INDEX_FILENAME
    if not index_path.exists():
        raise FileNotFoundError(f"Index not found at {index_path}")
    return json.loads(index_path.read_text(encoding="utf-8"))


def _query_sequence(path: Path) -> list[int]:
    midi = mido.MidiFile(path)
    for track in midi.tracks:
        sequence = extract_pitch_sequence(track)
        if sequence:
            return sequence
    return []


def _contains_subsequence(sequence: list[int], query: list[int]) -> bool:
    if not query or len(query) > len(sequence):
        return False
    for i in range(len(sequence) - len(query) + 1):
        if sequence[i : i + len(query)] == query:
            return True
    return False


@app.post("/v1/midi/retrieval/hard-match")
def hard_match_endpoint(payload: HardMatchRequest) -> JSONResponse:
    database_root = Path(payload.path_to_midi_database)
    if not database_root.is_dir():
        raise FileNotFoundError(f"Database directory not found: {database_root}")
    query_path = Path(payload.path_to_query_midi_segment)
    if not query_path.exists():
        raise FileNotFoundError(f"Query MIDI not found: {query_path}")

    index_data = _load_index(database_root)
    query_sequence = _query_sequence(query_path)
    if not query_sequence:
        return ok_response({"paths_to_matched_song": []})

    matches: list[str] = []
    for entry in index_data.get("entries", []):
        melody_sequence = entry.get("melody_sequence", [])
        if _contains_subsequence(melody_sequence, query_sequence):
            matches.append(entry["path"])

    return ok_response({"paths_to_matched_song": matches})


def run() -> None:
    uvicorn.run(app, host="localhost", port=PORT)


__all__ = ["app", "run"]
