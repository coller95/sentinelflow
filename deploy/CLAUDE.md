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
parse_cli → resolve_app_profile → preflight → derive_name → resolve_own_prefix → install_teardown
  → [--xvfb: start_xserver → exports per-instance DISPLAY for everything below]
  → [--net: sudo_init, net_detect_parent, net_create, net_address, NS_RUN=…]
  → build_run_env
  → run_app 1 → wait_for_window → (extra apps, normal mode) → park_workspace
  → start_node
  → supervise (sweep + wait -n: FIRST member death ends the instance; trap tears down on INT/TERM/EXIT)
```

Supervision is no longer a bare `wait -n`: launch.sh sweeps `ALL_PIDS` for
already-dead members before and after every wait, working around the bash < 5.3
bug where `wait -n` skips pids that died before the call. First member death
still ends the instance (now printing the dying member's pid, `>> member pid=N
died — ending instance.`), Ctrl+C behavior is unchanged, and the liveness check
counts a present `/proc` entry as alive so `--net`'s root-owned sudo front-ends
(which EPERM on `kill -0`) are not misread as dead.

`--net` teardown now actually reaps the instance: `cleanup` routes the
`ALL_PIDS` kill through `sudo -n` (the root-owned `NS_RUN` sudo/runuser
front-ends used to EPERM a plain user kill), and `net_destroy` sweeps any
processes still inside the namespace (TERM, 1s grace, KILL via `ip netns pids`)
before `ip netns del`, so the ns is no longer left pinned and the
ipvlan/macvlan address is really released. All teardown sudo is non-interactive
(`-n`): if the keep-alive session lapsed, cleanup degrades to a no-op instead
of hanging on a hidden prompt.

## Prefix isolation (`--own-prefix`)

launch.sh has opt-in per-instance prefix isolation: `--own-prefix` runs the
instance in its OWN WINEPREFIX at `~/.local/state/sentinelflow/<name>/wineprefix`
(beside the node's state dir; wine initializes it on first boot — preflight
prints an INFO line when it's new), and `--wineprefix DIR` puts it elsewhere
(implies `--own-prefix`). The shared `PREFIX` global is repointed by
`resolve_own_prefix` (`preflight.sh`, called from launch.sh right after
`derive_name` — before the teardown trap goes live, so an early die() can
never hand `wineserver -k` the shared prefix), so `run_app`, the node's
`SF_PREFIX` and teardown's `wineserver -k` all follow —
stopping one instance no longer kills wine apps of other launches sharing the
bootstrapped `-p` prefix. Default (no flag) behavior is unchanged: all launches
with the same `-p` still share that prefix and its wineserver.

## modules/ map

| module | owns |
|---|---|
| `log.sh` | `log` / `die` |
| `teardown.sh` | `ALL_PIDS`, single idempotent `cleanup`, `install_teardown` (trap) |
| `sudo.sh` | keep-alive sudo for `--net` |
| `netns.sh` | `--net` network namespace + own LAN IP; sets `NS_RUN`, `LEASE_IP` |
| `xserver.sh` | `--xvfb` per-instance headless X server; exports `DISPLAY` |
| `cli.sh` | `usage` (reads launch.sh header), `parse_cli` → shared globals |
| `profiles.sh` | `resolve_app_profile` — load `deploy/apps/<name>.app` launch profile |
| `preflight.sh` | dependency + prefix checks, `resolve_own_prefix` (`--own-prefix`) |
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

In `--net` mode the node's environment is rebuilt from scratch through the
runuser scrub; `node.sh` forwards `SF_ORCH_URL` and `SENTINELFLOW_PORT` into
the node alongside the `SF_*` identity vars — but only when set and non-empty,
so unset and empty stay indistinguishable to payload guards like RunNode.sh's
`${SF_ORCH_URL:-}`. Default and `--xvfb` modes are unaffected (the node already
inherits these from the launcher environment).

The real node is the SentinelFlow cluster server, ridden in as a payload:

```
./deploy/launch.sh -p ~/.wineGame1 -c 1 --xvfb --node-cmd Scripts/RunNode.sh
```

`Scripts/RunNode.sh` isolates per instance (state+serverUuid under
`~/.local/state/sentinelflow/<name>/`, free port, auto-attach to this
instance's wine desktop by title) and can auto-commission into a running
orchestrator via `SF_ORCH_URL`. Caveat: a same-host orchestrator is still
unreachable from inside a macvlan/ipvlan netns (no hairpin), so `SF_ORCH_URL`
only commissions across hosts in `--net` mode. Prefer `--xvfb` for node
instances: the capture/input paths in `Src/infrastructure/os/linux_handler.py`
are exact there (own display, no WM fullscreen surprises, focus grabs are free).

## App profiles (deploy/apps/)

`-a <name>` is app-agnostic: if `deploy/apps/<name>.app` exists it is sourced
(`profiles.sh:resolve_app_profile`, called right after `parse_cli`) to set the
launch globals; otherwise the `-a` value passes through unchanged (a real wine
path or builtin like `notepad`). A new app is a **drop-in file** — no core edit.

A profile is a sourced KEY=VAL file. Keys it may set:

| key | meaning |
|---|---|
| `APP` | wine exe path to launch |
| `APP_ARGS` | extra args (word-split; unquoted at the call site) |
| `NO_DESKTOP` | `1` = run the app directly (own window), not in a wine virtual desktop |
| `WIN_TITLE` | window title to wait-for / attach / seed to the node |
| `HOLD_PROC` | engine process to babysit when the launcher front-end detaches |
| `PROFILE_COUNT` | default instance count (an explicit `-c` overrides) |

`deploy/apps/war3.app` (Warcraft III) is the first profile; `wc3.app` symlinks
to it. The `apps/` dir is sourced DATA, not an entry-point script — it does not
violate the "no new top-level scripts" rule.

## Gotchas

- A wine virtual desktop maps **two** X windows with the same title; only the
  WM-managed one carries a numeric `_NET_WM_DESKTOP`. `desktop.sh` resolves that
  one — `search | head -1` can grab the internal child and silently break window
  ops. Reuse `managed_wid` for any new window targeting. `-1` (sticky) counts as
  managed; on a WM-less display (`--xvfb`) nothing ever does, so `wait_for_window`
  takes the first title match there.
- On a desktop WM (seen with GNOME) wine can flip the desktop window to
  override-redirect fullscreen at screen size — capture then carries dead
  padding and normalized clicks miss. `--xvfb` avoids the whole class.
- `set -euo pipefail` everywhere. `NS_RUN` / `LEASE_IP` are predeclared (empty)
  in `netns.sh` so they are safe to expand when `--net` is off.
