# AutoDirector Copilot Electron Client

## Status

Current baseline:

- default runtime uses the real server-backed session bridge
- explicit mock fallback is still available for local debugging and recovery
- legacy WPF remains the migration baseline that must continue to start

## Directory Layout

```text
client-electron/
|-- electron/
|   |-- main.js
|   |-- preload.js
|   |-- session_bridge.js
|   |-- sniffer.js
|   `-- mock.js
|-- renderer/
|   |-- capsule.html
|   |-- capsule.js
|   |-- overlay.html
|   |-- overlay.js
|   `-- styles.css
|-- package.json
`-- README.md
```

## Requirements

- Node.js 18+
- local server available at `ws://127.0.0.1:8000/ws`, or set `COPILOT_WS_URL`

## Install

```powershell
cd D:\software\AutoDirectorCopilot\project\client-electron
npm install
```

## Run

Default real-session mode:

```powershell
cd D:\software\AutoDirectorCopilot\project\client-electron
npm start
```

Optional explicit mock fallback:

```powershell
cd D:\software\AutoDirectorCopilot\project\client-electron
$env:ELECTRON_SESSION_MODE = "mock"
npm start
```

Equivalent CLI switch:

```powershell
npm start -- --mock-session
```

## Manual Check

Default real-session mode:

1. Start the local server first.
2. Launch the Electron client.
3. Enter a goal and click `开始引导`.
4. Confirm the capsule receives a real planned step list and guidance from the server.
5. Use `下一步` to continue the loop.
6. Use `已完成` to end the guide explicitly when the task is done.

Shortcut behavior:

- `F9` is optional.
- It can pre-capture the current target window, but start no longer depends on `F9`.

## Known Limits

- Overlay highlight precision is not yet the final grounded Executor solution.
- Mock mode is intentionally still present, but it is no longer the default runtime path.
- Full Planner / Executor separation is still future roadmap work.

## Compatibility

- `project/client` remains the legacy WPF baseline.
- `project/server` remains the active migration server.
- This Electron client now exercises the real `v1` session bridge by default while legacy compatibility remains on the server side.
