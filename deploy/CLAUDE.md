# deploy/ — wine instance launcher

Keep this directory **simple**. It has exactly two scripts a user runs, and a
`modules/` dir of internals. Do not add more entry-point scripts here.

## The only two entry points

- **`bootstrap.sh <PREFIX>`** — first-time setup. Creates a fresh wow64 wine
  prefix with DXVK. Run once per prefix. App-agnostic.
- **`launch.sh -p <PREFIX> [opts]`** — the single runtime entry point. Brings up
  a wine virtual desktop, runs the app(s) inside it, optionally starts a
  per-instance node, supervises in the foreground, and tears **everything** down
  on exit (Ctrl+C). `--help` prints usage (read from its own header).

That's it. `bootstrap` to set up, `launch` to run. Nothing else belongs at the
top of `deploy/`.

## Rules

- **No new top-level scripts.** No probes, no one-off helpers, no alternate
  entry points. Throwaway experiments do not get committed here.
- **New behavior goes in `modules/`** as a sourced unit, wired into `launch.sh` —
  or rides in as a `--node-cmd` payload. It is never run directly.
- `modules/*.sh` are **sourced** by `launch.sh`, never executed standalone. They
  define functions and fill shared globals; no top-level side effects.

## launch.sh flow

```
parse_cli → preflight → derive_name → install_teardown
  → [--net: sudo_init, net_detect_parent, net_create, net_address, NS_RUN=…]
  → build_run_env
  → run_app 1 → wait_for_window → (extra apps, normal mode) → park_workspace
  → start_node
  → wait (supervise; trap tears down on INT/TERM/EXIT)
```

## modules/ map

| module | owns |
|---|---|
| `log.sh` | `log` / `die` |
| `teardown.sh` | `ALL_PIDS`, single idempotent `cleanup`, `install_teardown` (trap) |
| `sudo.sh` | keep-alive sudo for `--net` |
| `netns.sh` | `--net` network namespace + own LAN IP; sets `NS_RUN`, `LEASE_IP` |
| `cli.sh` | `usage` (reads launch.sh header), `parse_cli` → shared globals |
| `preflight.sh` | dependency + prefix checks |
| `desktop.sh` | name derivation, `wait_for_window` (managed-WID resolve), `park_workspace` |
| `apps.sh` | `build_run_env`, `run_app` |
| `node.sh` | `start_node` — per-instance node (inline stub by default) |

## Node

Each instance can carry a node — the process that will capture/control it.
Enable with `--node` (inline stub: identity + heartbeat, no logic) or
`--node-cmd CMD` for the real thing. The command gets the instance via env:
`SF_NAME SF_PREFIX SF_WID SF_RES SF_DISPLAY SF_IP` (+ `DISPLAY/XAUTHORITY/HOME`).
Its PID joins `ALL_PIDS`, so it is supervised and torn down with the instance;
in `--net` mode it runs inside the instance's netns (binds the instance IP).

## Gotchas

- A wine virtual desktop maps **two** X windows with the same title; only the
  WM-managed one carries a numeric `_NET_WM_DESKTOP`. `desktop.sh` resolves that
  one — `search | head -1` can grab the internal child and silently break window
  ops. Reuse `managed_wid` for any new window targeting.
- `set -euo pipefail` everywhere. `NS_RUN` / `LEASE_IP` are predeclared (empty)
  in `netns.sh` so they are safe to expand when `--net` is off.
