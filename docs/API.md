# SentinelFlow API Reference

This document describes the HTTP/SSE API exposed by a SentinelFlow node ("cluster server").

- API style: REST-ish JSON + Server-Sent Events (SSE)
- Base URL (default dev): `http://127.0.0.1:8000`
- Content-Type for JSON requests: `application/json`
- Identity: most entities are identified by `uuid` (string UUID)

## Quick Concepts

### Normalized coordinates

Several endpoints use normalized coordinates in the range `[0, 1]`:

- `x = 0` is left edge, `x = 1` is right edge
- `y = 0` is top edge, `y = 1` is bottom edge

This applies to:
- Condition ROI (`roi.{xNormalized,yNormalized,widthNormalized,heightNormalized}`)
- `/api/control/click` (`x`, `y`)
- Action macro step `Click` parameters (`x`/`y` or `xNormalized`/`yNormalized`)

### Images (base64)

- For condition templates you can send either:
  - raw base64, or
  - a data URL like `data:image/png;base64,....` (the server strips the prefix)

- Many responses include image thumbnails as *raw base64* (no prefix). To render in a browser, prefix it:
  - `data:image/jpeg;base64,${templateThumbBase64}`

### SSE basics

SSE endpoints return `text/event-stream`. Clients should use `EventSource`.

- The server emits `retry: 1000` (client reconnect hint)
- The server emits keepalives as comments: `: keepalive`
- Event types are explicitly named (e.g. `event: status`, `event: frame`)

Example:

```js
const es = new EventSource("/api/triggers/status/stream");
es.addEventListener("status", (ev) => {
  const payload = JSON.parse(ev.data);
  console.log(payload);
});
```

## Enums

### `ConditionType`

- `ImageMatchRoi`
- `ProgressBar`

### `MacroType`

- `Click`
- `KeyStroke`
- `Delay`

### `TriggerComparator`

- `Equals`
- `NotEquals`
- `GreaterThan`
- `LessThan`
- `GreaterThanOrEqual`
- `LessThanOrEqual`

## Server Identity

### `GET /api/server/info`

Returns the stable identity of this node.

Response:

```json
{ "serverUuid": "6b7c5a7f-..." }
```

Notes:
- `serverUuid` is persisted in `state.json`.

## State (Persistence / Cluster Orchestration)

State is stored in `state.json` (written atomically as `state.json.tmp` then replaced).

### `GET /api/state/export?includeServerUuid=false`

Exports the node configuration as a JSON object.

Query params:
- `includeServerUuid` (bool, default `false`): include `serverUuid` in the exported payload

Response (shape):

```json
{
  "version": 1,
  "savedAtUnix": 1730000000.0,
  "serverUuid": "... (only if includeServerUuid=true)",
  "conditions": [ ... ],
  "actions": [ ... ],
  "triggers": [ ... ]
}
```

### `POST /api/state/import`

Imports a state object into the running node.

Request:

```json
{
  "state": { "version": 1, "conditions": [], "actions": [], "triggers": [] },
  "keepServerUuid": true
}
```

Notes:
- If `keepServerUuid=true` (default), the target node keeps its current identity even if the incoming state contains `serverUuid`.
- The server saves the imported state to `state.json`.

Response:

```json
{ "ok": true }
```

Errors:
- `400` if the state is invalid (version mismatch, schema issues, etc.)

### `POST /api/state/reload`

Reloads local `state.json` into the running process (no restart required).

Response:

```json
{ "ok": true, "serverUuid": "..." }
```

Errors:
- `404` if `state.json` does not exist
- `400` if parsing/import fails

## App Window Management

These configure which application window is being captured/controlled.

### `POST /api/app/launch`

Launches an application and attaches capture/control.

Request:

```json
{
  "app_path": "C:/Path/To/App.exe",
  "left": 0,
  "top": 0,
  "width": 640,
  "height": 480
}
```

Response:

```json
{ "ok": true }
```

### `POST /api/app/attach`

Attach by window title.

Request:

```json
{
  "window_title": "My Game",
  "left": 0,
  "top": 0,
  "width": 640,
  "height": 480
}
```

Response:

```json
{ "ok": true }
```

### `POST /api/app/close`

Closes/detaches the attached application.

Response:

```json
{ "ok": true }
```

## Capture (Frames)

### `POST /api/capture/start`

Start capture worker.

Request:

```json
{ "intervalSeconds": 1.0 }
```

Response:

```json
{ "ok": true }
```

### `POST /api/capture/stop`

Stops capture.

Response:

```json
{ "ok": true }
```

### `GET /api/capture/latest?fmt=png|jpg`

Returns the most recent captured frame as an image binary.

Query params:
- `fmt`: `png` (default) or `jpg`

Responses:
- `200` with `image/png` or `image/jpeg`
- `404` if no frame is available yet (start capture first)

### `GET /api/capture/events` (SSE)

Lightweight event stream that emits a sequence number when a new frame arrives.

Events:
- `event: frame` with data = capture sequence number (integer as text)

Example payload:

```
event: frame
data: 42

```

### `GET /api/capture/stream?fmt=jpg&quality=70` (SSE)

Streams frames directly over SSE as base64 JPEG to avoid a second HTTP request per frame.

Query params:
- `fmt`: must be `jpg`/`jpeg` (default `jpg`)
- `quality`: `10..95` (default `70`)

Events:
- `event: frame` with data = base64 JPEG bytes (string)

Client rendering example:

```js
es.addEventListener("frame", (ev) => {
  const b64 = ev.data;
  img.src = "data:image/jpeg;base64," + b64;
});
```

## Control (Input)

These enqueue input into the control worker. They require an attached window.

### `POST /api/control/click`

Click at normalized coordinates.

Request:

```json
{ "x": 0.5, "y": 0.5 }
```

Response:

```json
{ "ok": true }
```

### `POST /api/control/key`

Send a keystroke by key name.

Request:

```json
{ "keyName": "ENTER" }
```

Response:

```json
{ "ok": true }
```

## Conditions

### `GET /api/conditions`

Returns configured conditions (definition only).

Response:

```json
[
  {
    "uuid": "...",
    "name": "HP Bar",
    "type": "ProgressBar",
    "roi": {
      "xNormalized": 0.1,
      "yNormalized": 0.2,
      "widthNormalized": 0.3,
      "heightNormalized": 0.1
    }
  }
]
```

### `POST /api/conditions`

Creates a new condition (new UUID).

Request:

```json
{
  "name": "Enemy Icon",
  "type": "ImageMatchRoi",
  "roi": { "xNormalized": 0.1, "yNormalized": 0.2, "widthNormalized": 0.2, "heightNormalized": 0.2 },
  "templateImageBase64": "...optional...",
  "templateFromLive": false
}
```

Notes:
- If `templateImageBase64` is provided it is used.
- Else if `templateFromLive=true`, the server crops the latest capture frame using `roi`.

Response:

```json
{ "ok": true, "uuid": "..." }
```

Errors:
- `400` if name is empty or ROI size is invalid
- `404` if `templateFromLive=true` but no capture frame exists

### `POST /api/conditions/set_from_live`

Updates an existing condition by UUID (ROI, optional name/type, optional template).

Request:

```json
{
  "uuid": "...",
  "roi": { "xNormalized": 0.1, "yNormalized": 0.2, "widthNormalized": 0.2, "heightNormalized": 0.2 },
  "name": "optional",
  "type": "optional",
  "templateImageBase64": "optional",
  "templateFromLive": true
}
```

Response:

```json
{ "ok": true }
```

### `POST /api/conditions/move`

Moves a condition up/down in display/evaluation order.

Request:

```json
{ "uuid": "...", "direction": "up" }
```

`direction` must be `up` or `down`.

Response:

```json
{ "ok": true }
```

### `POST /api/conditions/remove_uuid`

Remove a condition by UUID.

Request:

```json
{ "uuid": "..." }
```

Response:

```json
{ "ok": true }
```

### `POST /api/conditions/clear`

Remove all conditions.

Response:

```json
{ "ok": true }
```

### `POST /api/conditions/remove?name=...`

Legacy remove-by-name (kept for backwards compatibility).

Response:

```json
{ "ok": true, "removed": 1 }
```

### `GET /api/conditions/status`

Returns the latest condition status keyed by UUID.

Response:

```json
{
  "order": ["uuid1", "uuid2"],
  "byUuid": {
    "uuid1": {
      "uuid": "uuid1",
      "index": 0,
      "name": "...",
      "type": "ImageMatchRoi",
      "templateThumbBase64": "...",
      "cropThumbBase64": "...",
      "last": 0.93
    }
  }
}
```

### `GET /api/conditions/stream` (SSE)

Streams the same `{order, byUuid}` payload whenever condition status changes.

Events:
- `event: status` with data = compact JSON

## Actions (Macros)

### `GET /api/actions`

Returns all actions.

Response:

```json
[
  {
    "uuid": "...",
    "name": "Heal",
    "steps": [
      { "action": "KeyStroke", "parameters": { "keyName": "H" } },
      { "action": "Delay", "parameters": { "ms": 200 } }
    ]
  }
]
```

### `POST /api/actions/upsert`

Create/update an action.

Request:

```json
{
  "uuid": null,
  "name": "Heal",
  "steps": [
    { "action": "KeyStroke", "parameters": { "keyName": "H" } },
    { "action": "Delay", "parameters": { "ms": 200 } },
    { "action": "Click", "parameters": { "x": 0.5, "y": 0.5 } }
  ]
}
```

Notes on step parameters:
- `Click`: supports `x`/`y` or `xNormalized`/`yNormalized` (normalized 0..1)
- `KeyStroke`: supports `keyName` (or `key`)
- `Delay`: supports `ms` (preferred) or `seconds`

Response:

```json
{ "ok": true, "uuid": "..." }
```

### `POST /api/actions/remove_uuid`

Request:

```json
{ "uuid": "..." }
```

Response:

```json
{ "ok": true }
```

### `POST /api/actions/run`

Enqueues an action for execution.

Request:

```json
{ "uuid": "..." }
```

Response:

```json
{ "ok": true }
```

### `GET /api/actions/debug`

Returns macro execution diagnostics.

Response:

```json
{
  "lastError": "...or null",
  "macroQueueSize": 0
}
```

## Triggers

A trigger ties a set of criteria (condition comparisons) to an action.

### `GET /api/triggers`

Returns trigger definitions.

Response:

```json
[
  {
    "uuid": "...",
    "name": "Auto Heal",
    "enabled": true,
    "retriggerMs": 5000,
    "triggerCiterias": [
      { "conditionUuid": "...", "expectedValue": 0.3, "comparator": "LessThanOrEqual" }
    ],
    "action": "..."
  }
]
```

### `POST /api/triggers/upsert`

Create/update a trigger.

Request:

```json
{
  "uuid": null,
  "name": "Auto Heal",
  "enabled": true,
  "retriggerMs": 5000,
  "triggerCiterias": [
    { "conditionUuid": "...", "expectedValue": 0.3, "comparator": "LessThanOrEqual" }
  ],
  "action": "..."
}
```

Notes:
- `retriggerMs`:
  - `<= 0`: rising-edge only (fires once when criteria becomes true)
  - `> 0`: can fire again every `retriggerMs` while criteria remains true

Response:

```json
{ "ok": true, "uuid": "..." }
```

Errors:
- `404` if referenced condition/action UUIDs are missing
- `400` on invalid name/comparator/retriggerMs

### `POST /api/triggers/remove_uuid`

Request:

```json
{ "uuid": "..." }
```

Response:

```json
{ "ok": true }
```

### `POST /api/triggers/set_enabled`

Request:

```json
{ "uuid": "...", "enabled": true }
```

Response:

```json
{ "ok": true, "uuid": "...", "enabled": true }
```

### `GET /api/triggers/status`

Returns the current trigger evaluation snapshot and macro state.

Response (shape):

```json
{
  "items": [
    {
      "uuid": "...",
      "name": "...",
      "enabled": true,
      "retriggerMs": 5000,
      "actionUuid": "...",
      "actionName": "...",
      "lastMatch": false,
      "fireCount": 12,
      "lastFireUnix": 1730000000.0,
      "eval": [
        {
          "conditionUuid": "...",
          "conditionName": "...",
          "conditionType": "ImageMatchRoi",
          "last": 0.93,
          "comparator": "GreaterThan",
          "expected": 0.9,
          "ok": true
        }
      ],
      "actionRunCount": 12,
      "actionLastStartedUnix": 1730000000.0,
      "actionLastCompletedUnix": 1730000000.2,
      "actionIsRunning": false
    }
  ],
  "lastError": "...or null",
  "macro": {
    "queueSize": 0,
    "currentActionUuid": null,
    "currentStartedUnix": null,
    "lastEnqueuedActionUuid": null,
    "lastEnqueuedUnix": null,
    "lastCompletedActionUuid": null,
    "lastCompletedUnix": null
  }
}
```

(Exact keys inside each `items[]` entry may evolve; the intent is: last evaluation details + fire history + action execution stats.)

### `GET /api/triggers/status/stream` (SSE)

Streams trigger status updates when the status sequence changes.

Events:
- `event: status` with JSON payload:

```json
{
  "seq": 123,
  "items": [ ...same as /api/triggers/status... ],
  "lastError": "...or null",
  "macro": { ... }
}
```

### `GET /api/triggers/debug`

Returns internal debug counters keyed by trigger UUID.

Response:

```json
{
  "lastError": "...or null",
  "lastMatchByUuid": { "uuid": true },
  "fireCountByUuid": { "uuid": 3 },
  "lastFireUnixByUuid": { "uuid": 1730000000.0 }
}
```

## Minimal cURL Examples

Get server UUID:

```bash
curl http://127.0.0.1:8000/api/server/info
```

Export state (portable, without identity):

```bash
curl "http://127.0.0.1:8000/api/state/export?includeServerUuid=false" > state.json
```

Import state into a different node (preserve target identity):

```bash
curl -X POST http://127.0.0.1:8000/api/state/import \
  -H "Content-Type: application/json" \
  -d @import_request.json
```

Where `import_request.json` is:

```json
{ "state": { /* exported object */ }, "keepServerUuid": true }
```

Reload local `state.json`:

```bash
curl -X POST http://127.0.0.1:8000/api/state/reload
```
