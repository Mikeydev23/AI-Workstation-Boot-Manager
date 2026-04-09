# AI Workstation Boot Manager

AI Workstation Boot Manager is a Windows startup manager for AI workstation workflows, built with Python and `CustomTkinter`.

It helps you launch workstation tools in a controlled order instead of relying on Windows to start everything at once. The app supports workflow-specific startup modes, per-step delays, readiness checks, process-based readiness, and optional window snapping for selected apps.

## Features

- Startup modes for different workstation workflows
- Ordered launch steps with per-step delay control
- Step enable or disable toggles
- `path` and `url` launch targets
- Readiness settings for services or processes
- Optional process-ready checks before continuing
- Optional window snapping after launch
- Editable JSON-backed configuration through the GUI
- Live in-app logging during runs

## Project Layout

```text
AI-Workstation-Boot-Manager/
├── app.py
├── requirements.txt
├── README.md
├── how-to-run.md
├── .gitignore
├── config/
│   └── boot_modes.example.json
└── legacy/
    ├── ai_workstation_boot_manager.ps1
    └── ReadMe.txt
```

Notes:

- `config/boot_modes.example.json` is the tracked public example configuration.
- `config/boot_modes.json` is a local runtime file created by each user and is intentionally ignored by Git.
- Runtime logs may be generated locally under `logs/`, but log files are not tracked in the repository.

## Install

From the repository root:

```bash
pip install -r requirements.txt
```

## Setup / Configuration

1. Copy `config/boot_modes.example.json`.
2. Rename the copy to `config/boot_modes.json`.
3. Edit `config/boot_modes.json` so each application path, batch file path, URL, delay, and optional window placement matches your machine.
4. Run the app:

```bash
python app.py
```

`config/boot_modes.example.json` is safe to commit. `config/boot_modes.json` is your personal local configuration and should stay untracked.

## Configuration Model

The app uses a JSON config with a stable top-level structure for startup modes and steps. The tracked example file demonstrates the expected schema without including personal machine paths.

Representative step fields include:

- `name`
- `type`
- `path`
- `args`
- `delay_after`
- `enabled`
- `readiness`
- `process_ready`
- `window_snap`

Supported workflow examples include:

- AI Image Generation
- LLM Development
- Automation Workflow Mode
- Normal Work Mode
- Minimal Mode

## Editing Behavior

The GUI supports direct mode and config editing:

- Add, duplicate, delete, and reorder modes
- Edit mode names and existing step fields
- Enable or disable individual steps
- Import running applications into the selected mode
- Save changes manually when ready

Changes remain in memory until you click `Save Config`.

## Startup Behavior

- The app opens to the GUI by default.
- The selected mode can be run manually.
- Optional auto-start can run the selected mode after the app finishes loading.
- Each enabled step launches in order using the configured delay, readiness settings, and optional window snapping rules.

## Logging

The app writes runtime events to the live GUI log panel. Local file logging may also be used during runtime, but generated logs are local artifacts rather than repository content.

## Open Source / Contribution

Issues and pull requests are welcome.

The project is still evolving, and contributions that improve startup reliability, configuration handling, portability, and user experience are especially useful.

## Support

If you find this project useful, consider starring the repository.

If you want to support the project beyond that, optional support or donation links can be added later, but there is no expectation to do so.

## Legacy Reference

The `legacy/` folder contains the original PowerShell-based version for reference. It is useful for historical context and migration comparison, but `app.py` is the active entry point for the current application.
