# SentinelFlow API Reference

This document describes the HTTP/SSE API exposed by a SentinelFlow node ("cluster server").

This repo also contains a separate centralized server ("orchestrator") which can keep track of multiple cluster servers by UUID and a human label.

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

### `POST /api/server/reset_uuid`

Generates a new server UUID and persists it to `state.json`.

Response:

```json
{ "ok": true, "serverUuid": "6b7c5a7f-..." }
```

Notes:
- This changes the node identity used by the orchestrator.

## Central Orchestrator (Registry)

The orchestrator is a separate FastAPI app intended to run as a central registry for multiple cluster servers.

- Default base URL (dev): `http://127.0.0.1:8010`
- State file: `orchestrator_state.json`

### Run the orchestrator

From the repo root:

```bash
python -m Src.orchestrator.main
```

Note:
- Uvicorn may log `http://0.0.0.0:PORT` (bind-all). In a browser, use `http://127.0.0.1:PORT/` or `http://localhost:PORT/`.

Environment variables:
- `SENTINELFLOW_ORCH_PORT` (default `8010`)

### `GET /api/orchestrator/info`

Returns the stable identity of the orchestrator.

Response:

```json
{ "orchestratorUuid": "6b7c5a7f-..." }
```

### Commission / Decommission clusters

The orchestrator stores clusters by their UUID (the cluster server's `serverUuid`) and assigns a human label.

Notes:
- The orchestrator treats `clusterUuid` and `serverUuid` as the same identifier.

#### `POST /api/orchestrator/clusters/commission`

Registers (or updates) a cluster by UUID.

Request:

```json
{
  "clusterUuid": "6b7c5a7f-...",
  "label": "Cluster A",
  "baseUrl": "http://10.0.0.10:8000"
}
```

Response:

```json
{
  "ok": true,
  "cluster": {
    "uuid": "6b7c5a7f-...",
    "label": "Cluster A",
    "baseUrl": "http://10.0.0.10:8000",
    "commissionedAtUnix": 1730000000.0,
    "decommissionedAtUnix": null
  }
}
```

Errors:
- `400` if `label` is empty or invalid

#### `POST /api/orchestrator/clusters/commission_from_url`

Registers (or updates) a cluster by providing only its network address. The orchestrator will call the cluster's `GET /api/server/info` to discover the UUID automatically.

Request:

```json
{
  "baseUrl": "10.0.0.10:8000",
  "label": "Cluster A (optional)"
}
```

Notes:
- `baseUrl` may be `IP:port` or a full URL like `http://IP:port`.
- If `label` is omitted, the orchestrator defaults it to `host:port`.

Response:

```json
{
  "ok": true,
  "cluster": { "uuid": "6b7c5a7f-...", "label": "10.0.0.10:8000", "baseUrl": "http://10.0.0.10:8000" },
  "discovered": { "serverUuid": "6b7c5a7f-..." }
}
```

### Server identity (proxy)

These endpoints proxy cluster identity calls.

#### `GET /api/orchestrator/clusters/{clusterUuid}/server/info`

Response:

```json
{ "serverUuid": "6b7c5a7f-..." }
```

#### `POST /api/orchestrator/clusters/{clusterUuid}/server/reset_uuid`

Requests the cluster to generate a new server UUID and updates the orchestrator record.

Response:

```json
{
  "ok": true,
  "cluster": { "uuid": "...", "serverUuid": "...", "label": "...", "baseUrl": "http://..." },
  "reset": { "ok": true, "serverUuid": "..." }
}
```

Notes:
- This proxies the cluster endpoint `POST /api/server/reset_uuid`.
- If multiple clusters share the same `baseUrl`, the orchestrator updates all of them to the new `serverUuid`.
- The cluster record UUID is updated to match the new server UUID.

### App control (launch / attach)

The orchestrator can proxy “app” control calls to a specific cluster (launching or attaching the target program window on that cluster machine).

These map directly to the cluster server endpoints:
- `POST {baseUrl}/api/app/launch`
- `POST {baseUrl}/api/app/attach`
- `POST {baseUrl}/api/app/close`
- `POST {baseUrl}/api/app/detach`

#### `POST /api/orchestrator/clusters/{clusterUuid}/app/launch`

Request (cluster format, wrapped):

```json
{ "body": { "app_path": "C:/Path/To/App.exe", "left": 0, "top": 0, "width": 640, "height": 480 } }
```

#### `POST /api/orchestrator/clusters/{clusterUuid}/app/attach`

Request (cluster format, wrapped):

```json
{ "body": { "window_title": "Exact Window Title", "left": 0, "top": 0, "width": 640, "height": 480 } }
```

#### `POST /api/orchestrator/clusters/{clusterUuid}/app/close`

Response:

```json
{ "ok": true }
```

#### `POST /api/orchestrator/clusters/{clusterUuid}/app/detach`

Detaches from the attached window without terminating the process.

Response:

```json
{ "ok": true }
```

### App defaults (query path / program name)

Fetch the cluster's saved defaults for app launch path and window title.

Maps directly to the cluster server endpoint:
- `GET {baseUrl}/api/app/defaults`

#### `GET /api/orchestrator/clusters/{clusterUuid}/app/defaults`

Response:

```json
{ "defaultAppPath": "C:/Path/To/App.exe", "defaultWindowTitle": "Exact Window Title" }
```

### Capture control (start / stop)

Start/stop the cluster's capture worker.

These map directly to the cluster server endpoints:
- `POST {baseUrl}/api/capture/start`
- `POST {baseUrl}/api/capture/stop`

#### `POST /api/orchestrator/clusters/{clusterUuid}/capture/start`

Request (cluster format, wrapped):

```json
{ "body": { "intervalSeconds": 1.0 } }
```

#### `POST /api/orchestrator/clusters/{clusterUuid}/capture/stop`

Response:

```json
{ "ok": true }
```

#### `POST /api/orchestrator/clusters/{clusterUuid}/decommission`

Marks a cluster as decommissioned (soft-delete).

Response:

```json
{ "ok": true, "cluster": { "uuid": "...", "decommissionedAtUnix": 1730000100.0 } }
```

Errors:
- `404` if the cluster UUID is unknown

#### `POST /api/orchestrator/clusters/{clusterUuid}/remove`

Hard-delete a cluster record from the orchestrator registry.

Response:

```json
{ "ok": true }
```

Errors:
- `404` if the cluster UUID is unknown

### Query clusters

#### `GET /api/orchestrator/clusters?includeDecommissioned=false&refreshServerUuid=true`

Lists commissioned clusters.

Query params:
- `refreshServerUuid` (bool, default `true`): call each cluster's `/api/server/info` and sync stored UUIDs (may update `clusterUuid`).

Response:

```json
{
  "clusters": [
    {
      "uuid": "6b7c5a7f-...",
      "label": "Cluster A",
      "baseUrl": "http://10.0.0.10:8000",
      "commissionedAtUnix": 1730000000.0,
      "decommissionedAtUnix": null
    }
  ]
}
```

#### `GET /api/orchestrator/clusters/{clusterUuid}`

Fetch a single cluster record.

Response:

```json
{ "cluster": { "uuid": "6b7c5a7f-...", "label": "Cluster A" } }
```

Errors:
- `404` if the cluster UUID is unknown

### Manage a cluster's Actions / Conditions / Triggers

The orchestrator can proxy management calls to a specific cluster server using that cluster's registered `baseUrl`.

Notes:
- These endpoints require the cluster to have `baseUrl` set.
- Errors from the cluster are surfaced as `502` from the orchestrator (with the cluster's error message in `detail`).

#### Actions

- `GET /api/orchestrator/clusters/{clusterUuid}/actions` → proxies `GET {baseUrl}/api/actions`
- `POST /api/orchestrator/clusters/{clusterUuid}/actions/upsert`
- `POST /api/orchestrator/clusters/{clusterUuid}/actions/remove_uuid`
- `POST /api/orchestrator/clusters/{clusterUuid}/actions/move`
- `POST /api/orchestrator/clusters/{clusterUuid}/actions/run`

For the POST endpoints, send the cluster request JSON inside a wrapper object:

```json
{ "body": { "uuid": null, "name": "My Action", "steps": [] } }
```

#### Conditions

- `GET /api/orchestrator/clusters/{clusterUuid}/conditions`
- `GET /api/orchestrator/clusters/{clusterUuid}/conditions/status`
- `POST /api/orchestrator/clusters/{clusterUuid}/conditions`
- `POST /api/orchestrator/clusters/{clusterUuid}/conditions/set_from_live`
- `POST /api/orchestrator/clusters/{clusterUuid}/conditions/move`
- `POST /api/orchestrator/clusters/{clusterUuid}/conditions/remove_uuid`

POST body wrapper example:

```json
{ "body": { "name": "HP", "type": "ProgressBar", "roi": { "xNormalized": 0.1, "yNormalized": 0.2, "widthNormalized": 0.3, "heightNormalized": 0.05 } } }
```

#### Triggers

- `GET /api/orchestrator/clusters/{clusterUuid}/triggers`
- `GET /api/orchestrator/clusters/{clusterUuid}/triggers/status`
- `POST /api/orchestrator/clusters/{clusterUuid}/triggers/upsert`
- `POST /api/orchestrator/clusters/{clusterUuid}/triggers/remove_uuid`
- `POST /api/orchestrator/clusters/{clusterUuid}/triggers/move`
- `POST /api/orchestrator/clusters/{clusterUuid}/triggers/set_enabled`

POST body wrapper example:

```json
{ "body": { "uuid": null, "name": "Auto Heal", "enabled": true, "retriggerMs": 2000, "criteriaMode": "All", "triggerCiterias": [], "action": "00000000-0000-0000-0000-000000000000" } }
```

### Orchestrator state (persistence)

#### `GET /api/orchestrator/state/export`

Exports orchestrator state (including orchestrator UUID and cluster records).

#### `POST /api/orchestrator/state/import`

Imports orchestrator state.

Request:

```json
{ "state": { "version": 1, "orchestratorUuid": "...", "clusters": [] } }
```

#### `POST /api/orchestrator/state/reload`

Reloads `orchestrator_state.json` from disk.

## State (Persistence / Cluster Orchestration)

State is stored in `state.json` (written atomically as `state.json.tmp` then replaced).

Location rules:
- In development: project root.
- In PyInstaller packaged builds: prefers the folder next to the EXE **if writable**; otherwise falls back to a per-user folder (e.g. `%LOCALAPPDATA%/SentinelFlow`).
- Override with environment variable `SENTINELFLOW_STATE_DIR`.

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
  "app": {
    "defaultAppPath": "C:/Path/To/App.exe",
    "defaultWindowTitle": "My Game"
  },
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

### `GET /api/state/path`

Returns the resolved absolute path the node uses for `state.json`.

Response:

```json
{ "path": "C:/.../state.json" }
```

## App Window Management

These configure which application window is being captured/controlled.

### `GET /api/app/defaults`

Returns persisted operator defaults (stored in `state.json`).

Response:

```json
{
  "defaultAppPath": "C:/Path/To/App.exe",
  "defaultWindowTitle": "My Game",
  "defaultWindowLeft": 0,
  "defaultWindowTop": 0,
  "defaultWindowWidth": 640,
  "defaultWindowHeight": 480
}
```

### `POST /api/app/defaults`

Updates persisted operator defaults without launching or attaching.

Request:

```json
{
  "defaultAppPath": "C:/Path/To/App.exe",
  "defaultWindowTitle": "My Game",
  "defaultWindowLeft": 0,
  "defaultWindowTop": 0,
  "defaultWindowWidth": 640,
  "defaultWindowHeight": 480
}
```

Notes:
- `defaultAppPath`, `defaultWindowTitle`, `defaultWindowLeft`, `defaultWindowTop`, `defaultWindowWidth`, and `defaultWindowHeight` are optional; send any subset.
- For convenience, `app_path` and `window_title` are also accepted.

Response:

```json
{
  "ok": true,
  "defaultAppPath": "C:/Path/To/App.exe",
  "defaultWindowTitle": "My Game",
  "defaultWindowLeft": 0,
  "defaultWindowTop": 0,
  "defaultWindowWidth": 640,
  "defaultWindowHeight": 480
}
```

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

Notes:
- On success, the server updates and persists `defaultAppPath` and window geometry defaults.

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

Notes:
- On success, the server updates and persists `defaultWindowTitle` and window geometry defaults.

### `POST /api/app/close`

Closes/detaches the attached application.

Response:

```json
{ "ok": true }
```

### `POST /api/app/detach`

Detaches from the attached window without terminating the process.

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
List order is persisted and can be adjusted via `POST /api/actions/move`.

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

### `POST /api/actions/move`

Moves an action up/down in display order.

Request:

```json
{ "uuid": "...", "direction": "up" }
```

`direction` must be `up` or `down`.

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
List order is persisted and can be adjusted via `POST /api/triggers/move`.

Response:

```json
[
  {
    "uuid": "...",
    "name": "Auto Heal",
    "enabled": true,
    "retriggerMs": 5000,
    "disableOnFire": false,
    "criteriaMode": "All",
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
    "disableOnFire": false,
    "criteriaMode": "All",
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
- `disableOnFire`:
  - `false` (default): stays enabled after firing
  - `true`: auto-disable after a fire
- `criteriaMode`: `All` (default) requires every criteria to pass; `Any` allows any single criteria to pass.

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

### `POST /api/triggers/move`

Moves a trigger up/down in display order.

Request:

```json
{ "uuid": "...", "direction": "up" }
```

`direction` must be `up` or `down`.

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
