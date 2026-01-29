# MIDI Tool Server – REST API Specification

## Overview

This document specifies a **local-host, HTTP-only REST API** for a MIDI processing and retrieval tool server.

- **Protocol:** HTTP (explicitly **not HTTPS**)
- **Deployment target:** localhost
- **Style:** synchronous (blocking) REST
- **Data format:** JSON
- **Filesystem model:** server-side paths (no file uploads)

The semantics of the MIDI operations are assumed to be known by the client; this document focuses strictly on interface and protocol guarantees.

---

## Base Configuration

- **Base URL:** `http://localhost:{port}`
  - Example: `http://localhost:8765`
- **Content-Type:** `application/json; charset=utf-8`
- **API Versioning:** URI-based (`/v1/...`)

---

## Execution Model

- All endpoints are **blocking**.
- The HTTP response is sent **only after the operation has fully completed** and any output files have been written.
- If the HTTP connection is broken during execution, the operation is considered **failed**.
  - The server must not assume the client received or can rely on partial results.

---

## Output Path Policy

- Output paths are **automatically determined by the server**.
- Clients **must not** specify output filenames or directories.
- The server is fully responsible for ensuring:
  - **No filename collisions**
  - Safe and atomic output creation
- Returned output paths are **absolute filesystem paths**.

---

## Common Response Structure

### Success Response

````json
{
  "ok": true,
  "result": {}
}
````

### Error Response

````json
{
  "ok": false,
  "error": {
    "code": "STRING_CODE",
    "message": "Human-readable description",
    "details": {}
  }
}
````

---

## Standard Error Codes

| HTTP Status | Code              | Meaning                                  |
|------------|-------------------|------------------------------------------|
| 400        | INVALID_ARGUMENT  | Missing, malformed, or invalid parameter |
| 404        | FILE_NOT_FOUND    | Input file or directory does not exist   |
| 409        | OUTPUT_CONFLICT   | Output collision (should not occur)      |
| 500        | INTERNAL_ERROR    | Unhandled server failure                 |
| 501        | NOT_IMPLEMENTED   | Endpoint stubbed but not implemented     |

---

## Endpoints

### 1. Change MIDI Tempo

**POST** `/v1/midi/change-tempo`

Adjusts the tempo of a MIDI file by a multiplicative ratio.

#### Request

````json
{
  "path_to_original_midi": "/abs/path/original.mid",
  "ratio": 1.0
}
````

- `path_to_original_midi` (string, required)
- `ratio` (number, optional, default = `1.0`)
  - Must be `> 0`

#### Response

````json
{
  "ok": true,
  "result": {
    "path_to_output_midi": "/abs/path/output.mid"
  }
}
````

---

### 2. Transpose MIDI

**POST** `/v1/midi/transpose`

Transposes all notes in a MIDI file by a fixed number of semitones.

#### Request

````json
{
  "path_to_original_midi": "/abs/path/original.mid",
  "delta_in_semitones": 0
}
````

- `delta_in_semitones` (integer, optional, default = `0`)

#### Response

````json
{
  "ok": true,
  "result": {
    "path_to_output_midi": "/abs/path/output.mid"
  }
}
````

---

### 3. Convert Common Time to Swing

**POST** `/v1/midi/common-to-swing`

Converts a MIDI file from straight/common timing to swing timing.

#### Request

````json
{
  "path_to_original_midi": "/abs/path/original.mid"
}
````

#### Response

````json
{
  "ok": true,
  "result": {
    "path_to_output_midi": "/abs/path/output.mid"
  }
}
````

---

### 4. MIDI Retrieval – Hard Match

**POST** `/v1/midi/retrieval/hard-match`

Performs a hard-match retrieval of MIDI files from a database using a query MIDI segment.

#### Request

````json
{
  "path_to_midi_database": "/abs/path/to/database_dir",
  "path_to_query_midi_segment": "/abs/path/query.mid"
}
````

- `path_to_midi_database` (string, required)
  - Must be a directory
- `path_to_query_midi_segment` (string, required)

#### Response

````json
{
  "ok": true,
  "result": {
    "paths_to_matched_song": [
      "/abs/path/to/database_dir/song1.mid",
      "/abs/path/to/database_dir/song2.mid"
    ]
  }
}
````

- Returned paths are absolute paths to files **within the provided database directory**.
