# EarnApp Bot Context

This file defines the domain language and architectural boundaries for EarnApp Bot. Engineering skills should read it before proposing issues, diagnosing bugs, designing tests, or changing architecture.

## Project Identity

EarnApp Bot is a multi-device controller for EarnApp. It lets an admin control EarnApp on local, SSH, and ADB devices through two interfaces:

- Telegram bot: the primary operational interface.
- Web UI: a Flask interface for dashboard and API-style device control.

The project is in a staged refactor. The current direction is a shared core package used by both adapters, while preserving the old entry points and JSON runtime files.

## Core Glossary

- **Device**: a named target that can be controlled. Device names are the stable identifiers used across runtime JSON, schedules, auto-restart policies, logs, Telegram callbacks, and Web UI routes.
- **Device type**: one of `local`, `ssh`, or `adb`.
- **Local device**: runs commands on the same host as the bot, usually with `/usr/bin` as the default path.
- **SSH device**: remote Linux host accessed through host, port, username, and password.
- **ADB device**: Android or Android-like target accessed through `adb connect host:port`.
- **EarnApp status**: user-facing app status inferred from command output. Common states are `Running`, `Stopped`, `Not installed`, and `Unknown`.
- **Device health**: connectivity health for the device itself, expressed as `online` or `offline`. This is separate from EarnApp status.
- **Runtime JSON**: shared operational state stored in JSON files. Do not call this a database.
- **Use-case**: shared workflow function in `earnapp.core.use_cases` called by adapters and workers.
- **Executor**: command execution boundary for local, SSH, and ADB operations.
- **Worker**: background loop for monitoring, interval auto-restart, or time-based schedule execution.
- **Activity log**: operational history for actions and outcomes.

## Runtime JSON

The runtime source of truth is file-based JSON. The default runtime directory is the project root; it can be overridden with `EARNAPP_DATA_DIR`.

Both Telegram bot and Web UI must use the same runtime data directory. If they do not, their state will diverge.

Canonical runtime files:

- `config.json`: bot token and Telegram admin ID.
- `devices.json`: device registry, keyed by device name.
- `schedules.json`: time-based schedule registry, keyed by task ID.
- `auto_restart.json`: interval auto-restart policies, keyed by device name.
- `activity_log.json`: list of activity log entries.

Runtime JSON files are operational artifacts and should not be committed.

## Runtime Shapes

`devices.json` is a map of device name to device config:

- `local`: `type`, `path`
- `ssh`: `type`, `host`, `port`, `user`, `password`
- `adb`: `type`, `host`, `port`

`schedules.json` is a map of task ID to schedule entry:

- `device`
- `action`
- `time`
- `days`
- `enabled`
- `timezone`

`auto_restart.json` is a map of device name to policy:

- `enabled`
- `interval_hours`
- `delay_seconds`
- `last_run`

`activity_log.json` is a list of entries:

- `timestamp`
- `device`
- `action`
- `result`
- `type`
- `user`

Keep these legacy JSON shapes compatible unless the user explicitly asks for a migration.

## Architecture Vocabulary

The intended architecture separates core application logic from UI adapters.

- `earnapp.core.runtime`: resolves runtime data paths and `EARNAPP_DATA_DIR`.
- `earnapp.core.storage`: the `JsonStorage` seam for reading and writing runtime JSON with defaults, atomic writes, and lightweight locking.
- `earnapp.core.models`: lightweight domain models for legacy JSON shapes.
- `earnapp.core.executors`: local, SSH, and ADB command execution seam.
- `earnapp.core.use_cases`: shared workflows for device operations, schedules, auto-restart, health checks, and activity logs.
- `earnapp.core.workers`: background monitoring, auto-restart, and time schedule loops.
- `earnapp_bot.py`: current Telegram adapter and legacy-compatible entry point.
- `webui/app.py`: current Flask adapter exposing `/api/*`.

The refactor is not fully complete. Web UI is already thin around core use-cases. The Telegram entry point still contains substantial UI state and legacy handler code.

## Adapter Boundaries

Adapters should parse input, call use-cases, and format output. They should not own core workflow ordering.

Intended rules:

- Telegram handlers should not read or write runtime JSON directly.
- Web routes should not read or write runtime JSON directly.
- Adapters should not call `subprocess`, Paramiko, or raw `adb` directly.
- Shared behavior should live in use-cases or workers, not duplicated in both interfaces.

Some legacy exceptions still exist during the staged refactor. Preserve old behavior and entry points while moving logic toward the shared core.

## Device Operation Semantics

For `local` and `ssh` devices:

- Start uses `earnapp start`.
- Stop uses `earnapp stop`.
- Status primarily uses `earnapp status`, then falls back to process inspection.
- Show ID uses `earnapp showid`.

For `adb` devices:

- Start uses `am start -n com.brd.earnrewards/.ConsentActivity`.
- Stop uses `am force-stop com.brd.earnrewards`.
- Status uses `pidof com.brd.earnrewards`, then package existence checks.
- Show ID uses `settings get secure android_id`.

Restart semantics are intentionally ordered as stop, wait, then start. Do not silently change restart into a single command.

## Scheduling and Automation

There are two scheduling concepts:

- **Time-based schedule**: runs `start`, `stop`, or `restart` at a configured `HH:MM` on selected weekdays.
- **Auto restart**: interval-based restart policy per device.

Schedule rules:

- Schedule task IDs are derived as `{device}_{time}_{action}`.
- `days` uses Python weekday integers: `0=Monday` through `6=Sunday`.
- `timezone` currently defaults to `UTC`, but worker execution uses the local runtime clock through `datetime.fromtimestamp(...)`; timezone handling is shallow.

Auto-restart rules:

- Valid interval range is `0.5` to `168` hours.
- Default delay between stop and start is 5 seconds.
- Worker execution pattern is stop, wait, start.

## Activity Logging

Meaningful start, stop, and restart operations append an activity log entry. Log `type` values distinguish the source of the action:

- `manual`: user-initiated action from Telegram or Web UI.
- `auto`: interval auto-restart worker action.
- `scheduled`: time-based schedule worker action.

Worker actions should use `user` value `system`. Activity logs are capped to the latest 1000 entries by the core storage/use-case path.

## Sync Model

Telegram bot and Web UI share runtime JSON through `JsonStorage`.

The sync model is file-based and eventually consistent:

- Bot handlers refresh runtime state before many read and mutate flows.
- Auto-restart and time-schedule workers reload `auto_restart.json` and `schedules.json` on each loop.
- `JsonStorage` uses atomic replacement and lightweight lock files to reduce corruption risk.
- If Bot and Web UI update the same key at nearly the same time, last write can still win.

Do not describe this as transactional sync or real-time database consistency.

## Security and Operations

- Telegram access is admin-only through `admin_telegram_id` and should fail closed if the configured admin ID is invalid.
- Web UI has built-in Basic Auth for `/` and `/api/*`; it fails closed with `503` if `WEBUI_AUTH_PASSWORD` or `webui_auth_password` is missing.
- Web UI unsafe API requests require `X-CSRF-Token`. The bundled frontend reads the token from the rendered page and sends it on mutating requests.
- Web UI binds to `127.0.0.1` by default. Production deployments should expose it only through a controlled reverse proxy, VPN, or firewall rule.
- CORS is disabled by default and should only be enabled with explicit `WEBUI_CORS_ORIGINS` values.
- `devices.json` may contain SSH passwords and must be treated as sensitive local runtime data.
- Background automation only runs while the Python bot process is alive. Systemd is the recommended deployment mode.
- Full runtime tests need real dependencies and valid local config; static compile checks do not prove Telegram polling, Flask serving, SSH, or ADB behavior.

## Refactor Constraints

Preserve these constraints unless the user explicitly changes direction:

- Do not rewrite from scratch.
- Do not migrate to microservices.
- Do not migrate runtime JSON to a database before the storage seam is stable.
- Do not redesign the Web UI as part of backend/core refactors.
- Keep legacy entry points working: `earnapp_bot.py` and `webui/app.py`.
- Keep old Telegram callback/menu behavior compatible during incremental refactors.
- Keep Web UI API response shapes compatible with the existing frontend.

## Terms To Use

Use these terms consistently:

- device registry
- schedule registry
- auto-restart policy
- activity log
- runtime JSON
- shared state
- storage seam
- executor seam
- use-case layer
- Telegram adapter
- Web adapter
- background worker

## Terms To Avoid

Avoid these framings unless the code actually changes:

- database, when referring to runtime JSON
- device ID, when you mean device name
- SSH-only device model, because local and ADB are first-class types
- real-time sync or transactional consistency, because current sync is file-based
- completed hexagonal architecture, because the refactor is still staged
- frontend redesign, when the task is backend/core refactor

## Related Docs

- `docs/ARCHITECTURE.md`: target architecture and module boundaries.
- `docs/REFACTOR_PLAN.md`: staged refactor plan and constraints.
- `PROJECT_STRUCTURE.md`: current file layout and deployment notes.
- `webui/SYNC_INFO.md`: Bot and Web UI shared-state behavior.
