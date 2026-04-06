from __future__ import annotations

import copy
import ctypes
import json
import logging
import os
import shlex
import socket
import subprocess
import tempfile
import threading
import time
import tkinter as tk
import uuid
import webbrowser
from ctypes import wintypes
from pathlib import Path
from queue import Empty, Queue
from tkinter import TclError, filedialog, messagebox
from urllib import error as urllib_error, request as urllib_request

import customtkinter as ctk
import psutil
try:
    from customtkinter.windows.widgets.core_widget_classes.dropdown_menu import DropdownMenu
    from customtkinter.windows.widgets.scaling import CTkScalingBaseClass, ScalingTracker
except ImportError:  # pragma: no cover - defensive for package layout changes
    DropdownMenu = None
    CTkScalingBaseClass = None
    ScalingTracker = None


APP_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = APP_ROOT / "config"
LOG_DIR = APP_ROOT / "logs"
CONFIG_PATH = CONFIG_DIR / "boot_modes.json"
LOG_PATH = LOG_DIR / "boot_manager.log"

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
STEP_TYPES = ("path", "url")
READINESS_TYPES = ("none", "port", "url")
WINDOW_MATCH_MODES = ("none", "title_contains", "process_name")
EXCLUDED_PROCESS_NAMES = {
    "system",
    "registry",
    "system idle process",
    "svchost.exe",
    "csrss.exe",
    "wininit.exe",
    "services.exe",
    "lsass.exe",
    "smss.exe",
    "fontdrvhost.exe",
    "winlogon.exe",
    "dwm.exe",
    "taskhostw.exe",
    "conhost.exe",
    "searchhost.exe",
    "sihost.exe",
    "ctfmon.exe",
    "runtimebroker.exe",
    "crashpad_handler.exe",
    "systemsettingsbroker.exe",
    "startmenuexperiencehost.exe",
    "shellexperiencehost.exe",
    "textinputhost.exe",
}
EXCLUDED_PROCESS_NAME_PARTS = (
    "updater",
    "update",
    "helper",
    "crash",
    "reporter",
    "telemetry",
    "broker",
    "service",
    "agent",
    "notifier",
    "monitor",
    "elevation_service",
    "webviewhost",
    "daemon",
    "backend",
    "container",
    "worker",
    "relay",
    "installer",
    "setup",
    "nativehost",
    "native-host",
)
BACKGROUND_PROCESS_NAMES = {
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "python.exe",
    "pythonw.exe",
    "wsl.exe",
    "wslhost.exe",
    "wslrelay.exe",
    "wslservice.exe",
    "dllhost.exe",
    "backgroundtaskhost.exe",
    "code helper.exe",
    "msedgewebview2.exe",
    "applicationframehost.exe",
    "crossdeviceresume.exe",
    "crossdeviceservice.exe",
    "widgetservice.exe",
    "widgets.exe",
    "phoneexperiencehost.exe",
    "lockapp.exe",
    "searchindexer.exe",
    "searchprotocolhost.exe",
    "taskmgr.exe",
    "memcompression",
    "vmmemwsl",
    "openconsole.exe",
    "browser_broker.exe",
}
BACKGROUND_PATH_PARTS = (
    "\\windows\\system32\\",
    "\\windows\\syswow64\\",
    "\\windows\\systemapps\\",
    "\\windows\\uus\\",
    "\\windows\\wbem\\",
    "\\appdata\\local\\temp\\",
    "\\.vscode\\extensions\\",
    "\\.codex\\",
    "\\docker\\docker\\resources\\",
    "\\common files\\",
)
EXCLUDED_ARG_SUBSTRINGS = (
    "--background",
    "--no-startup-window",
    "--headless",
    "--startup",
    "--restart",
    "--service",
    "--utility",
    "--monitor-self",
    "--tray",
    "--minimized",
    "--extension-host",
    "--shared-process",
    "--type=",
    "--gpu-process",
    "--renderer",
    "--zygote",
    "--utility-sub-type",
    "--crashpad-handler",
    "--embedded-browser-webview=1",
    "--ms-enable-electron-run-as-node",
    "--node-ipc",
    "--clientprocessid=",
    "--cancellationreceive=",
    "--cancellationpipename",
    "--usenodeipc",
    "--servermode",
    "--stdio",
    "--pipe-in=",
    "--pipe-out=",
    "--launch-hidden",
    "--process-start-args",
    "--name=tray",
    "--startup_mode",
    "--field-trial-handle=",
    "--mojo-platform-channel-handle=",
    "--service-pipe-token=",
    "--renderer-client-id=",
    "--gpu-preferences=",
    "--gpu-launcher=",
    "--disable-gpu-sandbox",
    "--inspect-port=",
    "--remote-debugging-port=",
    "--remote-debugging-pipe",
    "--lang=",
    "--message-loop-type-ui",
    "--database=",
    "--original-process-start-time=",
    "--originalprocesstarttime=",
    "--msedgewebview",
    "registerprocessascomserver",
    "chrome-extension://",
    "nowindow",
    "/background",
    "/embedding",
    "-embedding",
    "/verysilent",
    "/silent",
    "/onboot",
)
EXCLUDED_USER_ACCOUNT_NAMES = {
    "system",
    "local service",
    "network service",
}
BROWSER_HELPER_ARG_PREFIXES = (
    "--type=",
    "--utility-sub-type=",
    "--renderer-client-id=",
    "--service-sandbox-type=",
    "--gpu-preferences=",
    "--crashpad-handler-pid=",
)
EDITOR_HELPER_ARG_PARTS = (
    "tsserver.js",
    "typingsinstaller.js",
    "eslintserver.js",
    "servermain.js",
    "jsonservermain",
    "serverworkermain",
    ".vscode\\extensions\\",
    "\\resources\\app\\extensions\\",
)
LIKELY_USER_APP_NAMES = {
    "brave.exe",
    "chrome.exe",
    "code - insiders.exe",
    "code.exe",
    "cursor.exe",
    "discord.exe",
    "ditto.exe",
    "docker desktop.exe",
    "eartrumpet.exe",
    "everything.exe",
    "explorer.exe",
    "firefox.exe",
    "lm studio.exe",
    "malwarebytes.exe",
    "msedge.exe",
    "nvidia broadcast.exe",
    "obs64.exe",
    "obsidian.exe",
    "onecommander.exe",
    "opera.exe",
    "powertoys.exe",
    "protonvpn.client.exe",
    "quicklook.exe",
    "signal.exe",
    "slack.exe",
    "spotify.exe",
    "steam.exe",
    "systemsettings.exe",
    "tailscale-ipn.exe",
    "telegram.exe",
    "vivaldi.exe",
    "voicemeeter8x64.exe",
    "windows terminal.exe",
    "windowsterminal.exe",
}
WINDOWLESS_USER_APP_NAMES = {
    "discord.exe",
    "ditto.exe",
    "docker desktop.exe",
    "eartrumpet.exe",
    "malwarebytes.exe",
    "powertoys.exe",
    "protonvpn.client.exe",
    "quicklook.exe",
    "signal.exe",
    "slack.exe",
    "spotify.exe",
    "steam.exe",
    "tailscale-ipn.exe",
    "telegram.exe",
    "voicemeeter8x64.exe",
}
WINDOW_REQUIRED_USER_APP_NAMES = {
    "everything.exe",
    "explorer.exe",
    "lm studio.exe",
    "nvidia broadcast.exe",
    "obs64.exe",
    "onecommander.exe",
    "systemsettings.exe",
    "windows terminal.exe",
    "windowsterminal.exe",
}
MULTI_PROCESS_APP_NAMES = {
    "brave.exe",
    "chrome.exe",
    "code - insiders.exe",
    "code.exe",
    "cursor.exe",
    "discord.exe",
    "docker desktop.exe",
    "explorer.exe",
    "firefox.exe",
    "msedge.exe",
    "obsidian.exe",
    "opera.exe",
    "slack.exe",
    "vivaldi.exe",
}
USER_INSTALL_PATH_PARTS = (
    "\\program files\\",
    "\\program files (x86)\\",
    "\\appdata\\local\\programs\\",
    "\\windowsapps\\",
    "\\users\\",
)
MEANINGFUL_LAUNCH_ARG_PREFIXES = (
    "--app=",
    "--file-uri=",
    "--folder-uri=",
    "--incognito",
    "--new-window",
    "--profile=",
    "--profile-directory",
    "--profile-directory=",
    "--reuse-window",
    "--url=",
    "--user-data-dir=",
    "-profile",
)
VISIBLE_WINDOW_TITLE_MAX = 80
SIDEBAR_BUTTON_FG = ("#3B8ED0", "#1F6AA5")
SIDEBAR_BUTTON_HOVER = ("#36719F", "#144870")
SIDEBAR_BUTTON_TEXT = ("#FFFFFF", "#FFFFFF")
SIDEBAR_BUTTON_SELECTED_FG = ("#D8E0EA", "#2F3B4C")
SIDEBAR_BUTTON_SELECTED_HOVER = ("#C8D2DE", "#384456")
SIDEBAR_BUTTON_SELECTED_TEXT = ("#111827", "#FFFFFF")
UI_QUEUE_POLL_MS = 250
DIRTY_MARK_DELAY_MS = 200
PERF_LOG_THRESHOLD_MS = 16.0
PERF_WARN_THRESHOLD_MS = 150.0
READINESS_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_READINESS_TIMEOUT_SECONDS = 60
DEFAULT_PROCESS_READY_TIMEOUT_SECONDS = 30
DEFAULT_WINDOW_SNAP_TIMEOUT_SECONDS = 15
WINDOW_SNAP_POLL_INTERVAL_SECONDS = 0.5
SCAN_PATH_DISPLAY_MAX = 100
SCAN_ARGS_DISPLAY_MAX = 140
STEP_CARD_PADX = 6
STEP_CARD_PADY = 2
STEP_CARD_INNER_PADX = 8
STEP_CARD_TOP_PADY = 5
STEP_ENTRY_HEIGHT = 28
STEP_OPTION_HEIGHT = 30
STEP_BROWSE_WIDTH = 76
LOG_PANEL_HEIGHTS = {
    "Collapsed": 0,
    "Compact": 72,
    "Expanded": 260,
}
STEPS_SCROLL_INCREMENT = 32
SIDEBAR_TOOL_BUTTON_HEIGHT = 24
SIDEBAR_TOOL_FONT = 11
STEP_SEGMENTED_HEIGHT = 26
SIDEBAR_ICON_BUTTON_WIDTH = 26
EDITOR_ACTION_BUTTON_HEIGHT = 28
EDITOR_ACTION_BUTTON_WIDTH = 104
STEP_SUMMARY_BUTTON_WIDTH = 56
STEP_REMOVE_BUTTON_WIDTH = 72
STEP_DRAG_HANDLE_WIDTH = 30

DEFAULT_CONFIG = {
    "version": 1,
    "auto_start_on_launch": False,
    "confirm_step_delete": True,
    "readiness_presets": [],
    "selected_mode_id": "ai-image-generation",
    "modes": [
        {
            "id": "ai-image-generation",
            "name": "AI Image Generation",
            "steps": [
                {
                    "name": "Tailscale",
                    "type": "path",
                    "path": "C:/Program Files/Tailscale/tailscale-ipn.exe",
                    "args": [],
                    "delay_after": 10,
                    "enabled": True,
                },
                {
                    "name": "Docker Desktop",
                    "type": "path",
                    "path": "C:/Program Files/Docker/Docker/Docker Desktop.exe",
                    "args": [],
                    "delay_after": 45,
                    "enabled": True,
                },
                {
                    "name": "RustDesk",
                    "type": "path",
                    "path": "C:/Program Files/RustDesk/RustDesk.exe",
                    "args": [],
                    "delay_after": 15,
                    "enabled": True,
                },
                {
                    "name": "ComfyUI",
                    "type": "path",
                    "path": "C:/AI-Projects/ComfyUI/ComfyUI_windows_portable/run_nvidia_gpu.bat",
                    "args": [],
                    "delay_after": 90,
                    "enabled": True,
                },
                {
                    "name": "Open WebUI",
                    "type": "url",
                    "path": "http://127.0.0.1:3000",
                    "args": [],
                    "delay_after": 5,
                    "enabled": True,
                },
            ],
        },
        {
            "id": "llm-development",
            "name": "LLM Development",
            "steps": [
                {
                    "name": "Tailscale",
                    "type": "path",
                    "path": "C:/Program Files/Tailscale/tailscale-ipn.exe",
                    "args": [],
                    "delay_after": 10,
                    "enabled": True,
                },
                {
                    "name": "Docker Desktop",
                    "type": "path",
                    "path": "C:/Program Files/Docker/Docker/Docker Desktop.exe",
                    "args": [],
                    "delay_after": 45,
                    "enabled": True,
                },
                {
                    "name": "LM Studio",
                    "type": "path",
                    "path": "C:/Users/Michael/AppData/Local/Programs/LM Studio/LM Studio.exe",
                    "args": [],
                    "delay_after": 20,
                    "enabled": False,
                },
                {
                    "name": "VS Code",
                    "type": "path",
                    "path": "C:/Users/Michael/AppData/Local/Programs/Microsoft VS Code/Code.exe",
                    "args": [],
                    "delay_after": 5,
                    "enabled": True,
                },
                {
                    "name": "Open WebUI",
                    "type": "url",
                    "path": "http://127.0.0.1:3000",
                    "args": [],
                    "delay_after": 5,
                    "enabled": True,
                },
            ],
        },
        {
            "id": "autherax-workflow-mode",
            "name": "AutheraX Workflow Mode",
            "steps": [
                {
                    "name": "Tailscale",
                    "type": "path",
                    "path": "C:/Program Files/Tailscale/tailscale-ipn.exe",
                    "args": [],
                    "delay_after": 10,
                    "enabled": True,
                },
                {
                    "name": "Docker Desktop",
                    "type": "path",
                    "path": "C:/Program Files/Docker/Docker/Docker Desktop.exe",
                    "args": [],
                    "delay_after": 45,
                    "enabled": True,
                },
                {
                    "name": "n8n",
                    "type": "url",
                    "path": "http://127.0.0.1:5678",
                    "args": [],
                    "delay_after": 5,
                    "enabled": True,
                },
                {
                    "name": "LiteLLM",
                    "type": "url",
                    "path": "http://127.0.0.1:4000",
                    "args": [],
                    "delay_after": 5,
                    "enabled": True,
                },
                {
                    "name": "Open WebUI",
                    "type": "url",
                    "path": "http://127.0.0.1:3000",
                    "args": [],
                    "delay_after": 5,
                    "enabled": True,
                },
                {
                    "name": "Antigravity IDE",
                    "type": "path",
                    "path": "C:/Users/Michael/AppData/Local/Programs/Antigravity/Antigravity.exe",
                    "args": [],
                    "delay_after": 5,
                    "enabled": False,
                },
            ],
        },
        {
            "id": "normal-work-mode",
            "name": "Normal Work Mode",
            "steps": [
                {
                    "name": "Vivaldi",
                    "type": "path",
                    "path": "C:/Users/Michael/AppData/Local/Vivaldi/Application/vivaldi.exe",
                    "args": [],
                    "delay_after": 3,
                    "enabled": False,
                },
                {
                    "name": "Brave",
                    "type": "path",
                    "path": "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe",
                    "args": [],
                    "delay_after": 3,
                    "enabled": True,
                },
                {
                    "name": "Discord",
                    "type": "path",
                    "path": "%LOCALAPPDATA%/Discord/Update.exe",
                    "args": ["--processStart", "Discord.exe"],
                    "delay_after": 3,
                    "enabled": True,
                },
                {
                    "name": "Obsidian",
                    "type": "path",
                    "path": "%LOCALAPPDATA%/Obsidian/Obsidian.exe",
                    "args": [],
                    "delay_after": 3,
                    "enabled": True,
                },
            ],
        },
        {
            "id": "minimal-mode",
            "name": "Minimal Mode",
            "steps": [
                {
                    "name": "Tailscale",
                    "type": "path",
                    "path": "C:/Program Files/Tailscale/tailscale-ipn.exe",
                    "args": [],
                    "delay_after": 5,
                    "enabled": True,
                }
            ],
        },
    ],
}


class ConfigError(Exception):
    """Raised when the configuration file cannot be loaded or validated."""


class LogQueueHandler(logging.Handler):
    def __init__(self, log_queue: Queue[str]) -> None:
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.log_queue.put(self.format(record))
        except Exception:
            self.handleError(record)


def deep_copy_jsonable(value: object) -> object:
    return json.loads(json.dumps(value))


def ensure_runtime_paths() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def make_default_config() -> dict:
    return deep_copy_jsonable(DEFAULT_CONFIG)  # type: ignore[return-value]


def setup_logger(log_queue: Queue[str]) -> logging.Logger:
    logger = logging.getLogger("ai_workstation_boot_manager")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    if logger.handlers:
        existing_handlers = list(logger.handlers)
        for handler in existing_handlers:
            logger.removeHandler(handler)
            try:
                handler.flush()
            except Exception:
                pass
            try:
                handler.close()
            except Exception:
                pass

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)

    queue_handler = LogQueueHandler(log_queue)
    queue_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(queue_handler)
    return logger


def validate_config(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ConfigError("Top-level JSON value must be an object.")

    version = payload.get("version")
    if version != 1:
        raise ConfigError("Config version must be exactly 1.")

    auto_start_on_launch = payload.get("auto_start_on_launch", False)
    if not isinstance(auto_start_on_launch, bool):
        raise ConfigError("'auto_start_on_launch' must be a boolean.")

    confirm_step_delete = payload.get("confirm_step_delete", True)
    if not isinstance(confirm_step_delete, bool):
        raise ConfigError("'confirm_step_delete' must be a boolean.")

    readiness_presets = payload.get("readiness_presets", [])
    if not isinstance(readiness_presets, list):
        raise ConfigError("'readiness_presets' must be a list.")

    selected_mode_id = payload.get("selected_mode_id")
    if selected_mode_id is not None and not isinstance(selected_mode_id, str):
        raise ConfigError("'selected_mode_id' must be a string when provided.")

    modes = payload.get("modes")
    if not isinstance(modes, list):
        raise ConfigError("'modes' must be a list.")

    validated_modes = []
    seen_ids = set()
    validated_readiness_presets = []
    seen_preset_names = set()
    for preset_index, preset in enumerate(readiness_presets, start=1):
        normalized_preset = normalize_readiness_preset(preset)
        preset_name = normalized_preset["name"]
        if not preset_name:
            raise ConfigError(f"Readiness preset #{preset_index} is missing a valid 'name'.")
        if preset_name.lower() in seen_preset_names:
            raise ConfigError(f"Duplicate readiness preset name '{preset_name}' found.")
        if normalized_preset["type"] == "port":
            try:
                parse_host_port_target(normalized_preset["target"])
            except ValueError as exc:
                raise ConfigError(
                    f"Readiness preset '{preset_name}' has invalid port target: {exc}"
                ) from exc
        if normalized_preset["type"] == "url" and not normalized_preset["target"].startswith(
            ("http://", "https://")
        ):
            raise ConfigError(
                f"Readiness preset '{preset_name}' must use a URL starting with http:// or https://."
            )

        seen_preset_names.add(preset_name.lower())
        validated_readiness_presets.append(normalized_preset)

    for mode_index, mode in enumerate(modes, start=1):
        if not isinstance(mode, dict):
            raise ConfigError(f"Mode #{mode_index} must be an object.")

        mode_id = mode.get("id")
        mode_name = mode.get("name")
        steps = mode.get("steps")

        if not isinstance(mode_id, str) or not mode_id.strip():
            raise ConfigError(f"Mode #{mode_index} is missing a valid 'id'.")
        if mode_id in seen_ids:
            raise ConfigError(f"Duplicate mode id '{mode_id}' found.")
        if not isinstance(mode_name, str) or not mode_name.strip():
            raise ConfigError(f"Mode '{mode_id}' is missing a valid 'name'.")
        if not isinstance(steps, list):
            raise ConfigError(f"Mode '{mode_id}' must contain a 'steps' list.")

        seen_ids.add(mode_id)
        validated_steps = []
        for step_index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                raise ConfigError(f"Step #{step_index} in mode '{mode_id}' must be an object.")

            name = step.get("name")
            step_type = step.get("type")
            path = step.get("path")
            args = step.get("args")
            delay_after = step.get("delay_after")
            enabled = step.get("enabled")
            readiness = normalize_readiness_config(step.get("readiness"))
            process_ready = normalize_process_ready_config(
                step.get("process_ready"),
                str(step_type) if isinstance(step_type, str) else "path",
                str(path) if isinstance(path, str) else "",
            )
            window_snap = normalize_window_snap_config(step.get("window_snap"))

            if not isinstance(name, str) or not name.strip():
                raise ConfigError(
                    f"Step #{step_index} in mode '{mode_id}' is missing a valid 'name'."
                )
            if step_type not in STEP_TYPES:
                raise ConfigError(
                    f"Step '{name}' in mode '{mode_id}' has invalid type '{step_type}'."
                )
            if not isinstance(path, str):
                raise ConfigError(f"Step '{name}' in mode '{mode_id}' has invalid 'path'.")
            if step_type == "url" and not path.startswith(("http://", "https://")):
                raise ConfigError(
                    f"Step '{name}' in mode '{mode_id}' must use a URL starting with http:// or https://."
                )
            if not isinstance(args, list) or any(not isinstance(item, str) for item in args):
                raise ConfigError(f"Step '{name}' in mode '{mode_id}' has invalid 'args'.")
            if not isinstance(delay_after, int) or delay_after < 0:
                raise ConfigError(
                    f"Step '{name}' in mode '{mode_id}' must have a non-negative integer delay."
                )
            if not isinstance(enabled, bool):
                raise ConfigError(f"Step '{name}' in mode '{mode_id}' has invalid 'enabled'.")
            if readiness["type"] == "port":
                try:
                    parse_host_port_target(readiness["target"])
                except ValueError as exc:
                    raise ConfigError(
                        f"Step '{name}' in mode '{mode_id}' has invalid port readiness target: {exc}"
                    ) from exc
            if readiness["type"] == "url" and not readiness["target"].startswith(
                ("http://", "https://")
            ):
                raise ConfigError(
                    f"Step '{name}' in mode '{mode_id}' must use a readiness URL starting with http:// or https://."
                )
            if process_ready["enabled"]:
                if step_type != "path":
                    raise ConfigError(
                        f"Step '{name}' in mode '{mode_id}' can only use process readiness with path steps."
                    )
                if not process_ready["name"]:
                    raise ConfigError(
                        f"Step '{name}' in mode '{mode_id}' must define a process readiness name."
                    )
                if process_ready["timeout_seconds"] <= 0:
                    raise ConfigError(
                        f"Step '{name}' in mode '{mode_id}' must use a positive process readiness timeout."
                    )
                if process_ready["settle_delay_seconds"] < 0:
                    raise ConfigError(
                        f"Step '{name}' in mode '{mode_id}' must use a non-negative process settle delay."
                    )
            if window_snap["window_match_mode"] not in WINDOW_MATCH_MODES:
                raise ConfigError(
                    f"Step '{name}' in mode '{mode_id}' has invalid window match mode."
                )
            if window_snap["snap_enabled"] and window_snap["window_match_mode"] != "none":
                if not window_snap["window_match_value"]:
                    raise ConfigError(
                        f"Step '{name}' in mode '{mode_id}' must define 'window_match_value' when window snapping is enabled."
                    )
                if window_snap["snap_width"] <= 0 or window_snap["snap_height"] <= 0:
                    raise ConfigError(
                        f"Step '{name}' in mode '{mode_id}' must use positive snap width and height."
                    )
                if window_snap["snap_timeout_sec"] <= 0:
                    raise ConfigError(
                        f"Step '{name}' in mode '{mode_id}' must use a positive snap timeout."
                    )

            validated_steps.append(
                {
                    "name": name.strip(),
                    "type": step_type,
                    "path": path,
                    "args": list(args),
                    "delay_after": delay_after,
                    "enabled": enabled,
                    "readiness": readiness,
                    "process_ready": process_ready,
                    "window_snap": window_snap,
                }
            )

        validated_modes.append({"id": mode_id, "name": mode_name.strip(), "steps": validated_steps})

    resolved_selected_mode_id = selected_mode_id
    if validated_modes:
        mode_ids = {mode["id"] for mode in validated_modes}
        if not resolved_selected_mode_id or resolved_selected_mode_id not in mode_ids:
            resolved_selected_mode_id = validated_modes[0]["id"]
    else:
        resolved_selected_mode_id = None

    return {
        "version": 1,
        "auto_start_on_launch": auto_start_on_launch,
        "confirm_step_delete": confirm_step_delete,
        "readiness_presets": validated_readiness_presets,
        "selected_mode_id": resolved_selected_mode_id,
        "modes": validated_modes,
    }


def write_config_atomic(payload: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix="boot_modes_", suffix=".tmp", dir=str(CONFIG_DIR)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        os.replace(temp_path, CONFIG_PATH)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def load_or_create_config() -> dict:
    ensure_runtime_paths()
    if not CONFIG_PATH.exists():
        write_config_atomic(make_default_config())

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON parse error at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    except OSError as exc:
        raise ConfigError(f"Unable to read config file: {exc}") from exc

    return validate_config(payload)


def args_to_text(args: list[str]) -> str:
    return subprocess.list2cmdline(args) if args else ""


def parse_args_text(raw_text: str) -> list[str]:
    text = raw_text.strip()
    if not text:
        return []
    return shlex.split(text, posix=False)


def process_signature(path: str, args: list[str]) -> tuple[str, tuple[str, ...]]:
    return (path, tuple(args))


def truncate_display_text(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def make_default_readiness() -> dict:
    return {
        "type": "none",
        "target": "",
        "timeout_seconds": DEFAULT_READINESS_TIMEOUT_SECONDS,
    }


def normalize_readiness_config(value: object) -> dict:
    readiness = make_default_readiness()
    if not isinstance(value, dict):
        return readiness

    readiness_type = value.get("type", "none")
    target = value.get("target", "")
    timeout_seconds = value.get("timeout_seconds", DEFAULT_READINESS_TIMEOUT_SECONDS)

    if readiness_type in READINESS_TYPES:
        readiness["type"] = readiness_type
    if isinstance(target, str):
        readiness["target"] = target.strip()
    if isinstance(timeout_seconds, int) and timeout_seconds > 0:
        readiness["timeout_seconds"] = timeout_seconds

    return readiness


def normalize_readiness_preset(value: object) -> dict:
    readiness = normalize_readiness_config(value)
    name = ""
    if isinstance(value, dict):
        raw_name = value.get("name", "")
        if isinstance(raw_name, str):
            name = raw_name.strip()

    return {
        "name": name,
        "type": readiness["type"],
        "target": readiness["target"],
        "timeout_seconds": readiness["timeout_seconds"],
    }


def derive_default_process_ready_name(step_type: str, path: str) -> str:
    if step_type != "path":
        return ""

    expanded_path = os.path.expandvars(str(path).strip())
    if not expanded_path:
        return ""

    try:
        return Path(expanded_path).name.strip()
    except (OSError, ValueError):
        return ""


def make_default_process_ready() -> dict:
    return {
        "enabled": False,
        "name": "",
        "timeout_seconds": DEFAULT_PROCESS_READY_TIMEOUT_SECONDS,
        "settle_delay_seconds": 0,
    }


def normalize_process_ready_config(value: object, step_type: str = "path", path: str = "") -> dict:
    process_ready = make_default_process_ready()
    if not isinstance(value, dict):
        process_ready["name"] = derive_default_process_ready_name(step_type, path)
        return process_ready

    if isinstance(value.get("enabled"), bool):
        process_ready["enabled"] = value["enabled"]

    process_name = value.get("name", "")
    if isinstance(process_name, str):
        process_ready["name"] = process_name.strip()

    timeout_seconds = value.get("timeout_seconds", DEFAULT_PROCESS_READY_TIMEOUT_SECONDS)
    if isinstance(timeout_seconds, int) and timeout_seconds > 0:
        process_ready["timeout_seconds"] = timeout_seconds

    settle_delay_seconds = value.get("settle_delay_seconds", 0)
    if isinstance(settle_delay_seconds, int) and settle_delay_seconds >= 0:
        process_ready["settle_delay_seconds"] = settle_delay_seconds

    if not process_ready["name"]:
        process_ready["name"] = derive_default_process_ready_name(step_type, path)
    if process_ready["timeout_seconds"] <= 0:
        process_ready["timeout_seconds"] = DEFAULT_PROCESS_READY_TIMEOUT_SECONDS
    if process_ready["settle_delay_seconds"] < 0:
        process_ready["settle_delay_seconds"] = 0

    return process_ready


def make_default_window_snap() -> dict:
    return {
        "snap_enabled": False,
        "window_match_mode": "none",
        "window_match_value": "",
        "snap_x": 0,
        "snap_y": 0,
        "snap_width": 1280,
        "snap_height": 720,
        "snap_timeout_sec": DEFAULT_WINDOW_SNAP_TIMEOUT_SECONDS,
    }


def normalize_window_snap_config(value: object) -> dict:
    window_snap = make_default_window_snap()
    if not isinstance(value, dict):
        return window_snap

    if isinstance(value.get("snap_enabled"), bool):
        window_snap["snap_enabled"] = value["snap_enabled"]

    match_mode = value.get("window_match_mode", "none")
    if match_mode in WINDOW_MATCH_MODES:
        window_snap["window_match_mode"] = match_mode

    match_value = value.get("window_match_value", "")
    if isinstance(match_value, str):
        window_snap["window_match_value"] = match_value.strip()

    for field in ("snap_x", "snap_y", "snap_width", "snap_height", "snap_timeout_sec"):
        field_value = value.get(field, window_snap[field])
        if isinstance(field_value, int):
            window_snap[field] = field_value

    if window_snap["snap_width"] <= 0:
        window_snap["snap_width"] = 1280
    if window_snap["snap_height"] <= 0:
        window_snap["snap_height"] = 720
    if window_snap["snap_timeout_sec"] <= 0:
        window_snap["snap_timeout_sec"] = DEFAULT_WINDOW_SNAP_TIMEOUT_SECONDS

    return window_snap


def parse_host_port_target(target: str) -> tuple[str, int]:
    text = target.strip()
    if not text:
        raise ValueError("Port readiness target cannot be empty.")

    if ":" not in text:
        raise ValueError("Port readiness target must use host:port format.")

    host, port_text = text.rsplit(":", 1)
    host = host.strip()
    if not host:
        raise ValueError("Port readiness target host cannot be empty.")

    try:
        port = int(port_text.strip())
    except ValueError as exc:
        raise ValueError("Port readiness target port must be an integer.") from exc

    if port <= 0 or port > 65535:
        raise ValueError("Port readiness target port must be between 1 and 65535.")

    return host, port


def is_excluded_service_account(username: str) -> bool:
    normalized_user = username.strip().lower()
    if not normalized_user:
        return False

    account_name = normalized_user.split("\\")[-1]
    if account_name in EXCLUDED_USER_ACCOUNT_NAMES:
        return True
    if account_name.startswith("umfd-") or account_name.startswith("dwm-"):
        return True
    return False


def is_launchable_scan_path(executable_path: str) -> bool:
    normalized_path = executable_path.strip().strip('"')
    if not normalized_path:
        return False
    try:
        return Path(normalized_path).is_absolute()
    except (OSError, ValueError):
        return False


def get_visible_window_titles_by_pid() -> dict[int, list[str]]:
    if os.name != "nt":
        return {}

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    enum_windows_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    get_window_thread_process_id = user32.GetWindowThreadProcessId
    get_window_thread_process_id.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    get_window_thread_process_id.restype = wintypes.DWORD

    is_window_visible = user32.IsWindowVisible
    is_window_visible.argtypes = [wintypes.HWND]
    is_window_visible.restype = wintypes.BOOL

    get_window = user32.GetWindow
    get_window.argtypes = [wintypes.HWND, wintypes.UINT]
    get_window.restype = wintypes.HWND

    get_window_text_length = user32.GetWindowTextLengthW
    get_window_text_length.argtypes = [wintypes.HWND]
    get_window_text_length.restype = ctypes.c_int

    get_window_text = user32.GetWindowTextW
    get_window_text.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    get_window_text.restype = ctypes.c_int

    gw_owner = 4
    visible_titles: dict[int, set[str]] = {}

    def enum_callback(hwnd: wintypes.HWND, _lparam: wintypes.LPARAM) -> bool:
        if not is_window_visible(hwnd):
            return True
        if get_window(hwnd, gw_owner):
            return True

        title_length = get_window_text_length(hwnd)
        if title_length <= 0:
            return True

        title_buffer = ctypes.create_unicode_buffer(title_length + 1)
        get_window_text(hwnd, title_buffer, title_length + 1)
        title = title_buffer.value.strip()
        if not title:
            return True

        pid = wintypes.DWORD()
        get_window_thread_process_id(hwnd, ctypes.byref(pid))
        if pid.value:
            visible_titles.setdefault(pid.value, set()).add(title)
        return True

    user32.EnumWindows(enum_windows_proc(enum_callback), 0)
    return {pid: sorted(titles) for pid, titles in visible_titles.items()}


def enumerate_visible_top_level_windows() -> list[dict]:
    if os.name != "nt":
        return []

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    enum_windows_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    get_window_thread_process_id = user32.GetWindowThreadProcessId
    get_window_thread_process_id.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    get_window_thread_process_id.restype = wintypes.DWORD

    is_window_visible = user32.IsWindowVisible
    is_window_visible.argtypes = [wintypes.HWND]
    is_window_visible.restype = wintypes.BOOL

    is_window_enabled = user32.IsWindowEnabled
    is_window_enabled.argtypes = [wintypes.HWND]
    is_window_enabled.restype = wintypes.BOOL

    is_iconic = user32.IsIconic
    is_iconic.argtypes = [wintypes.HWND]
    is_iconic.restype = wintypes.BOOL

    get_window = user32.GetWindow
    get_window.argtypes = [wintypes.HWND, wintypes.UINT]
    get_window.restype = wintypes.HWND

    get_window_text_length = user32.GetWindowTextLengthW
    get_window_text_length.argtypes = [wintypes.HWND]
    get_window_text_length.restype = ctypes.c_int

    get_window_text = user32.GetWindowTextW
    get_window_text.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    get_window_text.restype = ctypes.c_int

    get_foreground_window = user32.GetForegroundWindow
    get_foreground_window.argtypes = []
    get_foreground_window.restype = wintypes.HWND

    gw_owner = 4
    foreground_hwnd = get_foreground_window()
    pid_name_cache: dict[int, str] = {}
    windows: list[dict] = []

    def enum_callback(hwnd: wintypes.HWND, _lparam: wintypes.LPARAM) -> bool:
        if not is_window_visible(hwnd):
            return True
        if not is_window_enabled(hwnd):
            return True
        if get_window(hwnd, gw_owner):
            return True

        title_length = get_window_text_length(hwnd)
        if title_length <= 0:
            return True

        title_buffer = ctypes.create_unicode_buffer(title_length + 1)
        get_window_text(hwnd, title_buffer, title_length + 1)
        title = title_buffer.value.strip()
        if not title:
            return True

        pid = wintypes.DWORD()
        get_window_thread_process_id(hwnd, ctypes.byref(pid))
        pid_value = int(pid.value)
        if not pid_value:
            return True

        if pid_value not in pid_name_cache:
            try:
                pid_name_cache[pid_value] = psutil.Process(pid_value).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pid_name_cache[pid_value] = ""

        windows.append(
            {
                "hwnd": hwnd,
                "pid": pid_value,
                "title": title,
                "process_name": pid_name_cache[pid_value],
                "is_minimized": bool(is_iconic(hwnd)),
                "is_foreground": bool(hwnd == foreground_hwnd),
            }
        )
        return True

    user32.EnumWindows(enum_windows_proc(enum_callback), 0)
    return windows


def get_window_rect_info(hwnd: int) -> dict | None:
    if os.name != "nt":
        return None

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    monitor_from_window = user32.MonitorFromWindow
    monitor_from_window.argtypes = [wintypes.HWND, wintypes.DWORD]
    monitor_from_window.restype = wintypes.HANDLE

    get_monitor_info = user32.GetMonitorInfoW
    get_monitor_info.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    get_monitor_info.restype = wintypes.BOOL

    get_window_rect = user32.GetWindowRect
    get_window_rect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    get_window_rect.restype = wintypes.BOOL

    rect = wintypes.RECT()
    if not get_window_rect(hwnd, ctypes.byref(rect)):
        return None

    monitor_name = ""
    monitor_default_to_nearest = 2

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32),
        ]

    monitor = monitor_from_window(hwnd, monitor_default_to_nearest)
    if monitor:
        monitor_info = MONITORINFOEXW()
        monitor_info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if get_monitor_info(monitor, ctypes.byref(monitor_info)):
            monitor_name = str(monitor_info.szDevice).strip()

    return {
        "x": int(rect.left),
        "y": int(rect.top),
        "width": max(1, int(rect.right - rect.left)),
        "height": max(1, int(rect.bottom - rect.top)),
        "monitor_name": monitor_name,
    }


def collect_running_process_signatures() -> set[tuple[str, tuple[str, ...]]]:
    signatures: set[tuple[str, tuple[str, ...]]] = set()
    current_pid = os.getpid()

    for process in psutil.process_iter(["pid", "exe", "cmdline"]):
        try:
            process_info = process.info
            process_pid = process_info.get("pid")
            if process_pid == current_pid:
                continue

            executable_path = process_info.get("exe") or ""
            cmdline = process_info.get("cmdline") or []

            if not executable_path and cmdline:
                executable_path = str(cmdline[0])

            if not is_launchable_scan_path(executable_path):
                continue

            args = [str(arg) for arg in cmdline[1:]] if len(cmdline) > 1 else []
            signatures.add(process_signature(executable_path, args))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return signatures


def should_exclude_scanned_process(name: str, executable_path: str) -> bool:
    normalized_name = name.strip().lower()
    executable_name = Path(executable_path).name.lower()

    if normalized_name in EXCLUDED_PROCESS_NAMES or executable_name in EXCLUDED_PROCESS_NAMES:
        return True
    return False


def looks_like_editor_helper_process(
    executable_name: str, normalized_path: str, lowered_args: list[str]
) -> bool:
    joined_args = " ".join(lowered_args)
    if executable_name in {"code.exe", "code - insiders.exe", "cursor.exe"}:
        if any(part in joined_args for part in EDITOR_HELPER_ARG_PARTS):
            return True
        if any(
            token in joined_args
            for token in (
                "--node-ipc",
                "--clientprocessid=",
                "--cancellationreceive=",
                "--cancellationpipename",
                "--usenodeipc",
                "--servermode",
            )
        ):
            return True

    if "\\.vscode\\extensions\\" in normalized_path or "\\.codex\\" in normalized_path:
        return True
    if any(part in joined_args for part in EDITOR_HELPER_ARG_PARTS):
        return True
    return False


def looks_like_service_or_helper_process(
    normalized_name: str, executable_name: str, normalized_path: str, lowered_args: list[str]
) -> bool:
    joined_args = " ".join(lowered_args)

    if any(part in normalized_name for part in EXCLUDED_PROCESS_NAME_PARTS):
        return True
    if any(part in executable_name for part in EXCLUDED_PROCESS_NAME_PARTS):
        return True
    if any(part in normalized_path for part in BACKGROUND_PATH_PARTS):
        return True
    if any(arg.startswith(BROWSER_HELPER_ARG_PREFIXES) for arg in lowered_args):
        return True
    if any(substring in arg for arg in lowered_args for substring in EXCLUDED_ARG_SUBSTRINGS):
        return True
    if "--extension-process" in lowered_args or "--crashpad-handler" in lowered_args:
        return True
    if executable_name == "code.exe" and any(
        arg in lowered_args
        for arg in ("--file-write", "--wait-marker-file", "--unity-launch", "--status")
    ):
        return True
    if looks_like_editor_helper_process(executable_name, normalized_path, lowered_args):
        return True
    if "docker-desktop" in joined_args or "/wslg" in joined_args:
        return True
    if executable_name.endswith(".tmp") or "setup" in executable_name:
        return True
    return False


def looks_like_path_or_url_arg(arg: str) -> bool:
    token = arg.strip().strip('"')
    if not token:
        return False

    lowered_token = token.lower()
    if lowered_token.startswith(("http://", "https://", "file://", "mailto:")):
        return True
    if lowered_token.startswith(("\\\\", ".\\", "..\\", "./", "../")):
        return True
    if len(token) > 2 and token[1] == ":" and token[2] in ("\\", "/"):
        return True
    return False


def has_meaningful_launch_args(args: list[str]) -> bool:
    if not args:
        return False

    lowered_args = [arg.lower() for arg in args]
    for raw_arg, lowered_arg in zip(args, lowered_args):
        if looks_like_path_or_url_arg(raw_arg):
            return True
        if lowered_arg.startswith(MEANINGFUL_LAUNCH_ARG_PREFIXES):
            return True
        if lowered_arg.startswith(("-", "/")):
            continue
        return True
    return False


def is_probably_user_install_path(normalized_path: str) -> bool:
    if any(path_part in normalized_path for path_part in BACKGROUND_PATH_PARTS):
        return False
    return any(path_part in normalized_path for path_part in USER_INSTALL_PATH_PARTS)


def classify_scanned_process(
    name: str,
    executable_path: str,
    args: list[str],
    username: str,
    has_visible_window: bool,
) -> str:
    normalized_name = name.strip().lower()
    executable_name = Path(executable_path).name.lower()
    normalized_path = executable_path.lower()
    lowered_args = [arg.lower() for arg in args]

    if is_excluded_service_account(username):
        return "background"
    if normalized_name in BACKGROUND_PROCESS_NAMES or executable_name in BACKGROUND_PROCESS_NAMES:
        return "background"
    if looks_like_service_or_helper_process(
        normalized_name, executable_name, normalized_path, lowered_args
    ):
        return "background"
    if has_visible_window:
        return "user"
    if executable_name in WINDOWLESS_USER_APP_NAMES:
        return "user"
    if executable_name in WINDOW_REQUIRED_USER_APP_NAMES:
        return "user" if has_meaningful_launch_args(args) else "background"
    if executable_name in MULTI_PROCESS_APP_NAMES:
        return "user" if has_meaningful_launch_args(args) else "background"
    if executable_name in LIKELY_USER_APP_NAMES:
        return "user"
    if is_probably_user_install_path(normalized_path) and has_meaningful_launch_args(args):
        return "user"

    return "background"


def entry_selection_priority(entry: dict) -> tuple[int, int, int, int]:
    return (
        1 if entry["has_visible_window"] else 0,
        1 if has_meaningful_launch_args(entry["args"]) else 0,
        1 if not entry["args"] else 0,
        len(entry.get("window_titles", [])),
    )


def collapse_user_app_entries(entries: list[dict]) -> list[dict]:
    collapsed_entries: list[dict] = []
    grouped_user_entries: dict[str, list[dict]] = {}

    for entry in entries:
        if entry["classification"] != "user":
            collapsed_entries.append(entry)
            continue
        grouped_user_entries.setdefault(entry["path"].lower(), []).append(entry)

    for path_key in sorted(grouped_user_entries):
        group_entries = grouped_user_entries[path_key]
        executable_name = Path(group_entries[0]["path"]).name.lower()
        if executable_name not in MULTI_PROCESS_APP_NAMES or len(group_entries) == 1:
            collapsed_entries.extend(group_entries)
            continue

        ordered_entries = sorted(
            group_entries,
            key=lambda entry: (
                entry_selection_priority(entry),
                entry["display_name"].lower(),
                args_to_text(entry["args"]).lower(),
            ),
            reverse=True,
        )

        retained_entries = [ordered_entries[0]]
        retained_signatures = {tuple(ordered_entries[0]["args"])}

        for entry in ordered_entries[1:]:
            entry_args = tuple(entry["args"])
            if entry_args in retained_signatures:
                continue
            if entry["has_visible_window"] and has_meaningful_launch_args(entry["args"]):
                retained_entries.append(entry)
                retained_signatures.add(entry_args)

        collapsed_entries.extend(retained_entries)

    return collapsed_entries


def derive_import_step_name(process_name: str, executable_path: str) -> str:
    if process_name:
        return process_name[:-4] if process_name.lower().endswith(".exe") else process_name
    return Path(executable_path).stem or executable_path


def apply_customtkinter_stability_patches() -> None:
    if DropdownMenu is None or CTkScalingBaseClass is None or ScalingTracker is None:
        return
    if getattr(ctk, "_aiwbm_stability_patched", False):
        return

    original_dropdown_destroy = DropdownMenu.destroy

    def safe_dropdown_destroy(self) -> None:
        try:
            CTkScalingBaseClass.destroy(self)
        except Exception:
            pass
        original_dropdown_destroy(self)

    def safe_update_scaling_callbacks_for_window(cls, window) -> None:
        callback_list = list(cls.window_widgets_dict.get(window, []))
        stale_callbacks = []
        for set_scaling_callback in callback_list:
            try:
                if not cls.deactivate_automatic_dpi_awareness:
                    set_scaling_callback(
                        cls.window_dpi_scaling_dict[window] * cls.widget_scaling,
                        cls.window_dpi_scaling_dict[window] * cls.window_scaling,
                    )
                else:
                    set_scaling_callback(cls.widget_scaling, cls.window_scaling)
            except Exception:
                stale_callbacks.append(set_scaling_callback)

        if stale_callbacks:
            live_callbacks = cls.window_widgets_dict.get(window, [])
            for callback in stale_callbacks:
                try:
                    live_callbacks.remove(callback)
                except ValueError:
                    continue

    def safe_update_scaling_callbacks_all(cls) -> None:
        for window, callback_list in list(cls.window_widgets_dict.items()):
            if not getattr(window, "winfo_exists", lambda: False)():
                continue

            stale_callbacks = []
            for set_scaling_callback in list(callback_list):
                try:
                    if not cls.deactivate_automatic_dpi_awareness:
                        set_scaling_callback(
                            cls.window_dpi_scaling_dict[window] * cls.widget_scaling,
                            cls.window_dpi_scaling_dict[window] * cls.window_scaling,
                        )
                    else:
                        set_scaling_callback(cls.widget_scaling, cls.window_scaling)
                except Exception:
                    stale_callbacks.append(set_scaling_callback)

            if stale_callbacks:
                live_callbacks = cls.window_widgets_dict.get(window, [])
                for callback in stale_callbacks:
                    try:
                        live_callbacks.remove(callback)
                    except ValueError:
                        continue

    DropdownMenu.destroy = safe_dropdown_destroy
    ScalingTracker.update_scaling_callbacks_for_window = classmethod(
        safe_update_scaling_callbacks_for_window
    )
    ScalingTracker.update_scaling_callbacks_all = classmethod(safe_update_scaling_callbacks_all)
    ctk._aiwbm_stability_patched = True


apply_customtkinter_stability_patches()


class ProcessScanDialog(ctk.CTkToplevel):
    def __init__(self, parent: "BootManagerApp", process_entries: list[dict]) -> None:
        super().__init__(parent)
        self.parent = parent
        self.process_entries = process_entries
        self.selection_vars: dict[tuple[str, tuple[str, ...]], ctk.BooleanVar] = {}
        self.search_var = ctk.StringVar(value="")
        self.show_user_apps_var = ctk.BooleanVar(value=True)
        self.show_background_var = ctk.BooleanVar(value=False)

        self.title("Scan Running Apps")
        self.geometry("1080x720")
        self.minsize(920, 540)
        self.transient(parent)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header,
            text="Import Running Apps",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w")

        subtitle = ctk.CTkLabel(
            header,
            text="Select running apps to append to the current mode. Duplicate exact path+args entries are skipped.",
            text_color=("gray35", "gray70"),
            wraplength=900,
            justify="left",
        )
        subtitle.grid(row=1, column=0, pady=(6, 0), sticky="w")

        filters = ctk.CTkFrame(header, fg_color="transparent")
        filters.grid(row=2, column=0, pady=(14, 0), sticky="ew")
        filters.grid_columnconfigure(0, weight=1)

        search_entry = ctk.CTkEntry(
            filters,
            textvariable=self.search_var,
            placeholder_text="Search name, path, or args",
            height=36,
        )
        search_entry.grid(row=0, column=0, padx=(0, 14), sticky="ew")

        show_user_checkbox = ctk.CTkCheckBox(
            filters,
            text="Show likely user apps",
            variable=self.show_user_apps_var,
        )
        show_user_checkbox.grid(row=0, column=1, padx=(0, 12), sticky="w")

        show_background_checkbox = ctk.CTkCheckBox(
            filters,
            text="Show background/system/helper processes",
            variable=self.show_background_var,
        )
        show_background_checkbox.grid(row=0, column=2, sticky="w")

        self.list_frame = ctk.CTkScrollableFrame(self, corner_radius=12)
        self.list_frame.grid(row=1, column=0, padx=20, pady=(0, 14), sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="e")

        cancel_button = ctk.CTkButton(footer, text="Cancel", width=110, command=self.destroy)
        cancel_button.grid(row=0, column=0, padx=(0, 10))

        import_button = ctk.CTkButton(
            footer, text="Import Selected", width=150, command=self.import_selected
        )
        import_button.grid(row=0, column=1)

        self.search_var.trace_add("write", self.refresh_list)
        self.show_user_apps_var.trace_add("write", self.refresh_list)
        self.show_background_var.trace_add("write", self.refresh_list)

        self.refresh_list()
        self.after(50, self.focus)
        self.grab_set()

    def refresh_list(self, *_args: object) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()

        search_text = self.search_var.get().strip().lower()
        show_user = bool(self.show_user_apps_var.get())
        show_background = bool(self.show_background_var.get())

        visible_entries = []
        for entry in self.process_entries:
            if entry["classification"] == "user" and not show_user:
                continue
            if entry["classification"] == "background" and not show_background:
                continue

            if search_text:
                haystack = " ".join(
                    [
                        entry["display_name"],
                        entry["path"],
                        args_to_text(entry["args"]),
                        " ".join(entry.get("window_titles", [])),
                    ]
                ).lower()
                if search_text not in haystack:
                    continue

            visible_entries.append(entry)

        row_index = 0
        row_index = self.render_group("User Apps", "user", visible_entries, row_index)
        row_index = self.render_group(
            "Background/System/Helper",
            "background",
            visible_entries,
            row_index,
        )

        if row_index == 0:
            empty_label = ctk.CTkLabel(
                self.list_frame,
                text="No scan results match the current filters.",
                text_color=("gray35", "gray70"),
            )
            empty_label.grid(row=0, column=0, padx=12, pady=18, sticky="w")

    def render_group(
        self, title: str, classification: str, visible_entries: list[dict], row_index: int
    ) -> int:
        group_entries = [entry for entry in visible_entries if entry["classification"] == classification]
        if not group_entries:
            return row_index

        group_label = ctk.CTkLabel(
            self.list_frame,
            text=f"{title} ({len(group_entries)})",
            font=ctk.CTkFont(size=17, weight="bold"),
            anchor="w",
        )
        group_label.grid(row=row_index, column=0, padx=12, pady=(8, 6), sticky="ew")
        row_index += 1

        for entry in group_entries:
            signature = entry["signature"]
            selected_var = self.selection_vars.setdefault(signature, ctk.BooleanVar(value=False))

            card = ctk.CTkFrame(self.list_frame, corner_radius=10)
            card.grid(row=row_index, column=0, padx=8, pady=8, sticky="ew")
            card.grid_columnconfigure(1, weight=1)

            checkbox = ctk.CTkCheckBox(card, text="", variable=selected_var, width=24)
            checkbox.grid(row=0, column=0, rowspan=4, padx=(14, 8), pady=14, sticky="n")

            title_label = ctk.CTkLabel(
                card,
                text=entry["display_name"],
                font=ctk.CTkFont(size=16, weight="bold"),
                anchor="w",
            )
            title_label.grid(row=0, column=1, padx=(0, 14), pady=(12, 4), sticky="ew")

            truncated_path = truncate_display_text(entry["path"], SCAN_PATH_DISPLAY_MAX)
            path_label = ctk.CTkLabel(
                card,
                text=f"Path: {truncated_path}",
                justify="left",
                wraplength=840,
                anchor="w",
            )
            path_label.grid(row=1, column=1, padx=(0, 14), pady=2, sticky="ew")

            args_text = args_to_text(entry["args"]) if entry["args"] else "(none)"
            truncated_args = truncate_display_text(args_text, SCAN_ARGS_DISPLAY_MAX)
            args_label = ctk.CTkLabel(
                card,
                text=f"Args: {truncated_args}",
                justify="left",
                wraplength=840,
                anchor="w",
                text_color=("gray30", "gray70"),
            )
            args_label.grid(row=2, column=1, padx=(0, 14), pady=(2, 12), sticky="ew")

            if entry.get("window_titles"):
                window_title = truncate_display_text(
                    entry["window_titles"][0], VISIBLE_WINDOW_TITLE_MAX
                )
                window_label = ctk.CTkLabel(
                    card,
                    text=f"Window: {window_title}",
                    justify="left",
                    wraplength=840,
                    anchor="w",
                    text_color=("gray30", "gray70"),
                )
                window_label.grid(row=3, column=1, padx=(0, 14), pady=(0, 12), sticky="ew")

            row_index += 1

        return row_index

    def import_selected(self) -> None:
        selected_entries = [
            entry
            for entry in self.process_entries
            if self.selection_vars.get(entry["signature"]) and self.selection_vars[entry["signature"]].get()
        ]
        self.parent.import_scanned_processes(selected_entries)
        self.destroy()


class StepDeleteConfirmDialog(ctk.CTkToplevel):
    def __init__(self, parent: "BootManagerApp", step_name: str) -> None:
        super().__init__(parent)
        self.parent = parent
        self.result = False
        self.skip_future_var = ctk.BooleanVar(value=False)

        self.title("Remove Step")
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        container = ctk.CTkFrame(self)
        container.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)

        message = ctk.CTkLabel(
            container,
            text=(
                f"Remove step '{step_name}'?\n\n"
                "This removes it from the selected mode in memory until you save."
            ),
            justify="left",
            anchor="w",
        )
        message.grid(row=0, column=0, padx=12, pady=(12, 10), sticky="w")

        checkbox = ctk.CTkCheckBox(
            container,
            text="Don't ask again for step deletion",
            variable=self.skip_future_var,
        )
        checkbox.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="w")

        button_row = ctk.CTkFrame(container, fg_color="transparent")
        button_row.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="e")

        no_button = ctk.CTkButton(
            button_row,
            text="No",
            width=84,
            height=30,
            command=self.cancel,
        )
        no_button.grid(row=0, column=0, padx=(0, 8))

        yes_button = ctk.CTkButton(
            button_row,
            text="Yes",
            width=84,
            height=30,
            fg_color="#b34141",
            hover_color="#943333",
            command=self.confirm,
        )
        yes_button.grid(row=0, column=1)

        self.after(10, self._activate_dialog)

    def _activate_dialog(self) -> None:
        try:
            self.grab_set()
            self.focus_force()
        except TclError:
            return

    def confirm(self) -> None:
        self.result = True
        self.destroy()

    def cancel(self) -> None:
        self.result = False
        self.destroy()


class ReadinessPresetsDialog(ctk.CTkToplevel):
    def __init__(self, parent: "BootManagerApp") -> None:
        super().__init__(parent)
        self.parent = parent
        self.result = False
        self.presets = [
            copy.deepcopy(normalize_readiness_preset(preset))
            for preset in parent.config_data.get("readiness_presets", [])
        ]
        self.selected_index: int | None = None
        self.updating_fields = False

        self.name_var = ctk.StringVar(value="")
        self.type_var = ctk.StringVar(value="none")
        self.target_var = ctk.StringVar(value="")
        self.timeout_var = ctk.StringVar(value=str(DEFAULT_READINESS_TIMEOUT_SECONDS))

        self.title("Manage Readiness Presets")
        self.transient(parent)
        self.geometry("760x420")
        self.minsize(720, 400)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left_panel = ctk.CTkFrame(self)
        left_panel.grid(row=0, column=0, padx=(14, 8), pady=14, sticky="nsew")
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(1, weight=1)

        presets_title = ctk.CTkLabel(
            left_panel,
            text="Presets",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        presets_title.grid(row=0, column=0, padx=12, pady=(12, 8), sticky="w")

        self.presets_listbox = tk.Listbox(left_panel, exportselection=False, height=12)
        self.presets_listbox.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="nsew")
        self.presets_listbox.bind("<<ListboxSelect>>", self.on_preset_selected)

        left_actions = ctk.CTkFrame(left_panel, fg_color="transparent")
        left_actions.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="ew")

        add_preset_button = ctk.CTkButton(
            left_actions,
            text="Add",
            width=70,
            height=28,
            command=self.add_preset,
        )
        add_preset_button.grid(row=0, column=0, padx=(0, 6))

        delete_preset_button = ctk.CTkButton(
            left_actions,
            text="Delete",
            width=70,
            height=28,
            fg_color="#b34141",
            hover_color="#943333",
            command=self.delete_preset,
        )
        delete_preset_button.grid(row=0, column=1)

        right_panel = ctk.CTkFrame(self)
        right_panel.grid(row=0, column=1, padx=(8, 14), pady=14, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_columnconfigure(1, weight=0)
        right_panel.grid_rowconfigure(7, weight=1)

        fields_title = ctk.CTkLabel(
            right_panel,
            text="Preset Details",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        fields_title.grid(row=0, column=0, columnspan=2, padx=12, pady=(12, 8), sticky="w")

        name_label = ctk.CTkLabel(right_panel, text="Name")
        name_label.grid(row=1, column=0, padx=12, pady=(0, 2), sticky="w")

        name_entry = ctk.CTkEntry(right_panel, textvariable=self.name_var, height=30)
        name_entry.grid(row=2, column=0, columnspan=2, padx=12, pady=(0, 8), sticky="ew")

        type_label = ctk.CTkLabel(right_panel, text="Readiness Type")
        type_label.grid(row=3, column=0, padx=12, pady=(0, 2), sticky="w")

        type_menu = ctk.CTkSegmentedButton(
            right_panel,
            values=list(READINESS_TYPES),
            variable=self.type_var,
            height=28,
            dynamic_resizing=False,
        )
        type_menu.grid(row=4, column=0, columnspan=2, padx=12, pady=(0, 8), sticky="ew")

        target_label = ctk.CTkLabel(right_panel, text="Target")
        target_label.grid(row=5, column=0, padx=12, pady=(0, 2), sticky="w")

        timeout_label = ctk.CTkLabel(right_panel, text="Timeout")
        timeout_label.grid(row=5, column=1, padx=(0, 12), pady=(0, 2), sticky="w")

        self.target_entry = ctk.CTkEntry(right_panel, textvariable=self.target_var, height=30)
        self.target_entry.grid(row=6, column=0, padx=12, pady=(0, 8), sticky="ew")

        timeout_entry = ctk.CTkEntry(
            right_panel,
            textvariable=self.timeout_var,
            width=100,
            height=30,
        )
        timeout_entry.grid(row=6, column=1, padx=(0, 12), pady=(0, 8), sticky="ew")

        self.help_label = ctk.CTkLabel(
            right_panel,
            text="none = delay only | port = host:port accepts TCP | url = HTTP responds",
            wraplength=420,
            justify="left",
            text_color=("gray35", "gray70"),
        )
        self.help_label.grid(row=7, column=0, columnspan=2, padx=12, sticky="nw")

        footer = ctk.CTkFrame(right_panel, fg_color="transparent")
        footer.grid(row=8, column=0, columnspan=2, padx=12, pady=(10, 12), sticky="e")

        cancel_button = ctk.CTkButton(
            footer,
            text="Cancel",
            width=84,
            height=30,
            command=self.cancel,
        )
        cancel_button.grid(row=0, column=0, padx=(0, 8))

        save_button = ctk.CTkButton(
            footer,
            text="Save Presets",
            width=110,
            height=30,
            command=self.save_presets,
        )
        save_button.grid(row=0, column=1)

        self.name_var.trace_add("write", self.on_field_changed)
        self.type_var.trace_add("write", self.on_field_changed)
        self.target_var.trace_add("write", self.on_field_changed)
        self.timeout_var.trace_add("write", self.on_field_changed)
        self.type_var.trace_add("write", self.refresh_help_text)

        self.refresh_listbox()
        if self.presets:
            self.select_preset(0)
        else:
            self.refresh_help_text()
        self.after(10, self._activate_dialog)

    def _activate_dialog(self) -> None:
        try:
            self.grab_set()
            self.focus_force()
        except TclError:
            return

    def refresh_listbox(self) -> None:
        self.presets_listbox.delete(0, "end")
        for preset in self.presets:
            self.presets_listbox.insert("end", preset["name"] or "(unnamed preset)")

    def select_preset(self, index: int | None) -> None:
        self.updating_fields = True
        try:
            if index is None or index < 0 or index >= len(self.presets):
                self.selected_index = None
                self.presets_listbox.selection_clear(0, "end")
                self.name_var.set("")
                self.type_var.set("none")
                self.target_var.set("")
                self.timeout_var.set(str(DEFAULT_READINESS_TIMEOUT_SECONDS))
                self.refresh_help_text()
                return

            self.selected_index = index
            preset = self.presets[index]
            self.presets_listbox.selection_clear(0, "end")
            self.presets_listbox.selection_set(index)
            self.presets_listbox.see(index)
            self.name_var.set(preset["name"])
            self.type_var.set(preset["type"])
            self.target_var.set(preset["target"])
            self.timeout_var.set(str(preset["timeout_seconds"]))
            self.refresh_help_text()
        finally:
            self.updating_fields = False

    def on_preset_selected(self, _event: object = None) -> None:
        selection = self.presets_listbox.curselection()
        self.select_preset(selection[0] if selection else None)

    def on_field_changed(self, *_args: object) -> None:
        if self.updating_fields or self.selected_index is None:
            return

        preset = self.presets[self.selected_index]
        preset["name"] = self.name_var.get()
        preset["type"] = self.type_var.get()
        preset["target"] = self.target_var.get()
        preset["timeout_seconds"] = self.timeout_var.get()
        self.refresh_listbox()
        self.presets_listbox.selection_set(self.selected_index)

    def refresh_help_text(self, *_args: object) -> None:
        readiness_type = self.type_var.get()
        if readiness_type == "port":
            self.target_entry.configure(placeholder_text="127.0.0.1:5678")
            self.help_label.configure(text="port = wait until host:port accepts a TCP connection")
        elif readiness_type == "url":
            self.target_entry.configure(placeholder_text="http://127.0.0.1:3000")
            self.help_label.configure(text="url = wait until the URL returns an HTTP 2xx or 3xx response")
        else:
            self.target_entry.configure(placeholder_text="optional target")
            self.help_label.configure(text="none = no readiness check; only delay_after is used")
        self.target_entry.configure(state="normal" if readiness_type != "none" else "disabled")

    def add_preset(self) -> None:
        self.presets.append(
            {
                "name": "New Preset",
                "type": "none",
                "target": "",
                "timeout_seconds": DEFAULT_READINESS_TIMEOUT_SECONDS,
            }
        )
        self.refresh_listbox()
        self.select_preset(len(self.presets) - 1)

    def delete_preset(self) -> None:
        if self.selected_index is None:
            return
        del self.presets[self.selected_index]
        self.refresh_listbox()
        next_index = min(self.selected_index, len(self.presets) - 1)
        self.select_preset(next_index if self.presets else None)

    def save_presets(self) -> None:
        normalized_presets = []
        seen_names = set()
        for preset in self.presets:
            normalized = normalize_readiness_preset(preset)
            if not normalized["name"]:
                messagebox.showerror("Invalid Preset", "Each readiness preset must have a name.")
                return
            lowered_name = normalized["name"].lower()
            if lowered_name in seen_names:
                messagebox.showerror(
                    "Invalid Preset",
                    f"Duplicate readiness preset name '{normalized['name']}'.",
                )
                return
            if normalized["type"] == "port":
                try:
                    parse_host_port_target(normalized["target"])
                except ValueError as exc:
                    messagebox.showerror(
                        "Invalid Preset",
                        f"Preset '{normalized['name']}' has an invalid port target.\n\n{exc}",
                    )
                    return
            if normalized["type"] == "url" and not normalized["target"].startswith(
                ("http://", "https://")
            ):
                messagebox.showerror(
                    "Invalid Preset",
                    f"Preset '{normalized['name']}' must use a URL starting with http:// or https://.",
                )
                return
            seen_names.add(lowered_name)
            normalized_presets.append(normalized)

        self.parent.config_data["readiness_presets"] = normalized_presets
        self.parent.set_dirty(True)
        self.parent.set_status("Readiness presets updated")
        self.result = True
        self.destroy()

    def cancel(self) -> None:
        self.result = False
        self.destroy()


class BootManagerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ensure_runtime_paths()
        self.log_queue: Queue[str] = Queue()
        self.status_queue: Queue[str] = Queue()
        self.logger = setup_logger(self.log_queue)

        self.config_data: dict = {
            "version": 1,
            "auto_start_on_launch": False,
            "confirm_step_delete": True,
            "readiness_presets": [],
            "selected_mode_id": None,
            "modes": [],
        }
        self.config_valid = True
        self.config_error_message = ""
        self.selected_mode_index: int | None = None
        self.step_widgets: list[dict] = []
        self.rendered_step_cards: list[ctk.CTkFrame] = []
        self.expanded_step_index: int | None = None
        self.dragged_step_index: int | None = None
        self.drag_drop_index: int | None = None
        self.drag_highlight_card: ctk.CTkFrame | None = None
        self.drag_indicator: tk.Frame | None = None
        self.mode_buttons: list[ctk.CTkButton] = []
        self.mode_name_var = ctk.StringVar(value="")
        self.auto_start_var = ctk.BooleanVar(value=False)
        self.log_panel_state_var = ctk.StringVar(value="Compact")
        self.status_var = ctk.StringVar(value="Idle")
        self.run_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.is_running = False
        self.is_dirty = False
        self.editor_dirty = False
        self.is_shutting_down = False
        self.suspend_dirty_tracking = False
        self.launch_auto_start_scheduled = False
        self.pending_dirty_after_id: str | None = None
        self.step_title_font = ctk.CTkFont(size=13, weight="bold")
        self.step_meta_font = ctk.CTkFont(size=12)
        self.step_button_font = ctk.CTkFont(size=12)
        self.step_button_bold_font = ctk.CTkFont(size=12, weight="bold")
        self.step_detail_label_font = ctk.CTkFont(size=11, weight="bold")
        self.step_detail_help_font = ctk.CTkFont(size=11)

        self.auto_start_var.trace_add("write", self.on_editor_changed)

        self.title("AI Workstation Boot Manager")
        self.geometry("1440x860")
        self.minsize(1200, 720)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        try:
            self.config_data = load_or_create_config()
        except ConfigError as exc:
            self.config_valid = False
            self.config_error_message = str(exc)
            self.logger.error("Failed to load config: %s", exc)

        self.build_ui()
        self.process_log_queue()
        self.process_status_queue()

        if self.config_valid and self.config_data["modes"]:
            initial_index = self.find_mode_index_by_id(self.config_data.get("selected_mode_id"))
            self.select_mode(initial_index if initial_index is not None else 0, force=True)
            self.logger.info("Loaded %s startup modes from %s", len(self.config_data["modes"]), CONFIG_PATH)
            self.set_status("Idle")
            self.schedule_auto_start_if_enabled()
        elif self.config_valid:
            self.selected_mode_index = None
            self.render_selected_mode()
            self.set_status("No modes available")
        else:
            self.disable_config_actions()
            if self.config_error_message:
                self.set_status("Config load failed")
                self.after(200, self.show_config_error_dialog)

    def build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=224, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(2, weight=1)

        sidebar_title = ctk.CTkLabel(
            self.sidebar,
            text="AI Workstation\nBoot Manager",
            font=ctk.CTkFont(size=22, weight="bold"),
            justify="left",
        )
        sidebar_title.grid(row=0, column=0, padx=18, pady=(18, 8), sticky="w")

        self.mode_management_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.mode_management_frame.grid(row=1, column=0, padx=14, pady=(0, 6), sticky="ew")
        self.mode_management_frame.grid_columnconfigure(0, weight=1)

        mode_management_label = ctk.CTkLabel(
            self.mode_management_frame,
            text="Modes",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        mode_management_label.grid(row=0, column=0, padx=2, pady=(0, 4), sticky="w")

        self.add_mode_button = ctk.CTkButton(
            self.mode_management_frame,
            text="+",
            width=SIDEBAR_ICON_BUTTON_WIDTH,
            height=SIDEBAR_TOOL_BUTTON_HEIGHT,
            font=ctk.CTkFont(size=SIDEBAR_TOOL_FONT),
            command=self.add_mode,
        )
        self.add_mode_button.grid(row=0, column=1, padx=(0, 4), pady=(0, 4), sticky="e")

        self.more_mode_actions_button = ctk.CTkButton(
            self.mode_management_frame,
            text="...",
            width=SIDEBAR_ICON_BUTTON_WIDTH,
            height=SIDEBAR_TOOL_BUTTON_HEIGHT,
            font=ctk.CTkFont(size=SIDEBAR_TOOL_FONT, weight="bold"),
            command=self.open_mode_actions_menu,
        )
        self.more_mode_actions_button.grid(row=0, column=2, pady=(0, 4), sticky="e")

        self.mode_actions_menu = tk.Menu(self, tearoff=False)
        self.mode_actions_menu.add_command(
            label="Duplicate selected mode",
            command=self.duplicate_selected_mode,
        )
        self.mode_actions_menu.add_command(
            label="Move selected mode up",
            command=lambda: self.move_selected_mode(-1),
        )
        self.mode_actions_menu.add_command(
            label="Move selected mode down",
            command=lambda: self.move_selected_mode(1),
        )
        self.mode_actions_menu.add_separator()
        self.mode_actions_menu.add_command(
            label="Delete selected mode",
            command=self.delete_selected_mode,
        )

        self.mode_button_frame = ctk.CTkScrollableFrame(self.sidebar, width=180)
        self.mode_button_frame.grid(row=2, column=0, padx=14, pady=(0, 14), sticky="nsew")
        self.mode_button_frame.grid_columnconfigure(0, weight=1)
        self.tune_scrollable_frame(self.mode_button_frame, yscrollincrement=12)

        self.main_panel = ctk.CTkFrame(self, corner_radius=0)
        self.main_panel.grid(row=0, column=1, sticky="nsew")
        self.main_panel.grid_columnconfigure(0, weight=1)
        self.main_panel.grid_rowconfigure(1, weight=1)
        self.main_panel.grid_rowconfigure(2, weight=0)

        self.editor_header = ctk.CTkFrame(self.main_panel, fg_color="transparent")
        self.editor_header.grid(row=0, column=0, padx=16, pady=(8, 4), sticky="ew")
        self.editor_header.grid_columnconfigure(0, weight=1)

        self.editor_title = ctk.CTkLabel(
            self.editor_header,
            text="Selected Mode",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        self.editor_title.grid(row=0, column=0, sticky="w")

        self.mode_meta_row = ctk.CTkFrame(self.editor_header, fg_color="transparent")
        self.mode_meta_row.grid(row=1, column=0, pady=(4, 0), sticky="ew")
        self.mode_meta_row.grid_columnconfigure(0, weight=1)

        self.mode_name_entry = ctk.CTkEntry(
            self.mode_meta_row,
            textvariable=self.mode_name_var,
            height=30,
            font=ctk.CTkFont(size=14),
        )
        self.mode_name_entry.grid(row=0, column=0, sticky="ew")
        self.bind_text_dirty_tracking(self.mode_name_entry)

        self.auto_start_checkbox = ctk.CTkCheckBox(
            self.mode_meta_row,
            text="Auto-start selected mode on app launch",
            variable=self.auto_start_var,
        )
        self.auto_start_checkbox.grid(row=0, column=1, padx=(10, 0), sticky="e")

        self.editor_toolbar = ctk.CTkFrame(self.editor_header, fg_color="transparent")
        self.editor_toolbar.grid(row=2, column=0, pady=(4, 0), sticky="ew")
        self.editor_toolbar.grid_columnconfigure(1, weight=1)

        self.add_step_button = ctk.CTkButton(
            self.editor_toolbar,
            text="Add Step",
            width=92,
            height=EDITOR_ACTION_BUTTON_HEIGHT,
            command=self.add_step,
        )
        self.add_step_button.grid(row=0, column=0, padx=(0, 10), sticky="w")

        self.status_label = ctk.CTkLabel(
            self.editor_toolbar,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
            text_color=("gray20", "gray85"),
        )
        self.status_label.grid(row=0, column=1, sticky="ew")

        self.action_frame = ctk.CTkFrame(self.editor_toolbar, fg_color="transparent")
        self.action_frame.grid(row=0, column=2, sticky="e")

        self.save_button = ctk.CTkButton(
            self.action_frame,
            text="Save Config",
            width=EDITOR_ACTION_BUTTON_WIDTH,
            height=EDITOR_ACTION_BUTTON_HEIGHT,
            command=self.save_config,
        )
        self.save_button.grid(row=0, column=0, padx=(0, 6))

        self.run_button = ctk.CTkButton(
            self.action_frame,
            text="Run Selected Mode",
            width=126,
            height=EDITOR_ACTION_BUTTON_HEIGHT,
            command=self.run_selected_mode,
        )
        self.run_button.grid(row=0, column=1, padx=(0, 6))

        self.stop_button = ctk.CTkButton(
            self.action_frame,
            text="Stop Sequence",
            width=110,
            height=EDITOR_ACTION_BUTTON_HEIGHT,
            fg_color="#b34141",
            hover_color="#943333",
            state="disabled",
            command=self.stop_sequence,
        )
        self.stop_button.grid(row=0, column=2, padx=(0, 6))

        self.scan_button = ctk.CTkButton(
            self.action_frame,
            text="Scan Running Apps",
            width=132,
            height=EDITOR_ACTION_BUTTON_HEIGHT,
            command=self.open_process_scan_dialog,
        )
        self.scan_button.grid(row=0, column=3)

        self.steps_frame = ctk.CTkScrollableFrame(
            self.main_panel, label_text="Mode Steps", corner_radius=14
        )
        self.steps_frame.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="nsew")
        self.steps_frame.grid_columnconfigure(0, weight=1)
        self.tune_scrollable_frame(self.steps_frame, yscrollincrement=STEPS_SCROLL_INCREMENT)

        self.log_frame = ctk.CTkFrame(self.main_panel)
        self.log_frame.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="nsew")
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_rowconfigure(1, weight=1)

        self.log_header = ctk.CTkFrame(self.log_frame, fg_color="transparent")
        self.log_header.grid(row=0, column=0, padx=16, pady=(12, 8), sticky="ew")
        self.log_header.grid_columnconfigure(0, weight=1)

        log_title = ctk.CTkLabel(
            self.log_header, text="Live Log", font=ctk.CTkFont(size=17, weight="bold")
        )
        log_title.grid(row=0, column=0, sticky="w")

        self.log_size_control = ctk.CTkSegmentedButton(
            self.log_header,
            values=list(LOG_PANEL_HEIGHTS.keys()),
            variable=self.log_panel_state_var,
            command=self.on_log_panel_state_changed,
        )
        self.log_size_control.grid(row=0, column=1, sticky="e")

        self.log_body = ctk.CTkFrame(self.log_frame, fg_color="transparent")
        self.log_body.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="nsew")
        self.log_body.grid_columnconfigure(0, weight=1)
        self.log_body.grid_rowconfigure(0, weight=1)

        self.log_text = ctk.CTkTextbox(
            self.log_body,
            height=LOG_PANEL_HEIGHTS["Compact"],
            wrap="word",
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.configure(state="disabled")

        self.populate_sidebar()
        self.refresh_action_states()
        self.apply_log_panel_state()

        if not self.config_valid:
            self.editor_title.configure(text="Config Load Failed")
            self.mode_name_entry.configure(state="disabled")
            self.auto_start_checkbox.configure(state="disabled")
            self.render_disabled_state()

    def populate_sidebar(self) -> None:
        for child in self.mode_button_frame.winfo_children():
            child.destroy()

        self.mode_buttons.clear()
        if not self.config_data.get("modes"):
            placeholder = ctk.CTkLabel(
                self.mode_button_frame,
                text="No modes available.",
                text_color=("gray35", "gray70"),
            )
            placeholder.grid(row=0, column=0, padx=8, pady=8, sticky="w")
            self.refresh_action_states()
            return

        for index, mode in enumerate(self.config_data["modes"]):
            button = ctk.CTkButton(
                self.mode_button_frame,
                text=mode["name"],
                anchor="w",
                height=38,
                fg_color=SIDEBAR_BUTTON_FG,
                hover_color=SIDEBAR_BUTTON_HOVER,
                text_color=SIDEBAR_BUTTON_TEXT,
                command=lambda idx=index: self.select_mode(idx),
            )
            button.grid(row=index, column=0, padx=6, pady=4, sticky="ew")
            self.mode_buttons.append(button)

        self.refresh_action_states()

    def render_disabled_state(self) -> None:
        for child in self.steps_frame.winfo_children():
            child.destroy()
        message = ctk.CTkLabel(
            self.steps_frame,
            text=(
                "The config file could not be loaded.\n"
                "Fix or restore config/boot_modes.json, then restart the app."
            ),
            justify="left",
            wraplength=900,
        )
        message.grid(row=0, column=0, padx=18, pady=18, sticky="w")

    def show_config_error_dialog(self) -> None:
        messagebox.showerror(
            "Config Load Failed",
            (
                "The boot mode configuration is invalid and has not been modified.\n\n"
                f"{self.config_error_message}\n\n"
                "Run and Save are disabled until the file is fixed and the app is restarted."
            ),
        )

    def find_mode_index_by_id(self, mode_id: object) -> int | None:
        if not isinstance(mode_id, str):
            return None

        for index, mode in enumerate(self.config_data.get("modes", [])):
            if mode["id"] == mode_id:
                return index
        return None

    def generate_mode_id(self) -> str:
        existing_ids = {mode["id"] for mode in self.config_data.get("modes", [])}
        while True:
            candidate = f"mode-{uuid.uuid4().hex[:12]}"
            if candidate not in existing_ids:
                return candidate

    def make_empty_mode(self, name: str) -> dict:
        return {"id": self.generate_mode_id(), "name": name, "steps": []}

    def tune_scrollable_frame(
        self, scrollable_frame: ctk.CTkScrollableFrame, yscrollincrement: int
    ) -> None:
        canvas = getattr(scrollable_frame, "_parent_canvas", None)
        if canvas is None:
            return
        canvas.configure(yscrollincrement=yscrollincrement, highlightthickness=0)

    def on_log_panel_state_changed(self, _value: str) -> None:
        self.apply_log_panel_state()

    def apply_log_panel_state(self) -> None:
        state = self.log_panel_state_var.get()
        desired_height = LOG_PANEL_HEIGHTS.get(state, LOG_PANEL_HEIGHTS["Compact"])
        if desired_height <= 0:
            self.log_body.grid_remove()
            self.log_frame.grid_configure(pady=(0, 6))
        else:
            self.log_body.grid()
            self.log_text.configure(height=desired_height)
            self.log_frame.grid_configure(pady=(0, 10 if state == "Compact" else 16))

    def get_mode_action_states(self) -> dict[str, str]:
        has_selection = self.selected_mode_index is not None
        mode_count = len(self.config_data.get("modes", []))
        config_ready = self.config_valid and not self.is_running

        return {
            "add": "normal" if config_ready else "disabled",
            "duplicate": "normal" if config_ready and has_selection else "disabled",
            "delete": "normal"
            if config_ready and has_selection and mode_count > 1
            else "disabled",
            "move_up": "normal"
            if config_ready and has_selection and self.selected_mode_index > 0
            else "disabled",
            "move_down": "normal"
            if config_ready and has_selection and self.selected_mode_index < mode_count - 1
            else "disabled",
        }

    def refresh_mode_actions_menu(self) -> None:
        action_states = self.get_mode_action_states()
        self.mode_actions_menu.entryconfigure(
            "Duplicate selected mode",
            state=action_states["duplicate"],
        )
        self.mode_actions_menu.entryconfigure(
            "Move selected mode up",
            state=action_states["move_up"],
        )
        self.mode_actions_menu.entryconfigure(
            "Move selected mode down",
            state=action_states["move_down"],
        )
        self.mode_actions_menu.entryconfigure(
            "Delete selected mode",
            state=action_states["delete"],
        )

    def open_mode_actions_menu(self) -> None:
        self.refresh_mode_actions_menu()
        if self.more_mode_actions_button.cget("state") == "disabled":
            return

        x = self.more_mode_actions_button.winfo_rootx()
        y = self.more_mode_actions_button.winfo_rooty() + self.more_mode_actions_button.winfo_height()
        try:
            self.mode_actions_menu.tk_popup(x, y)
        finally:
            self.mode_actions_menu.grab_release()

    def refresh_action_states(self) -> None:
        has_selection = self.selected_mode_index is not None
        config_ready = self.config_valid and not self.is_running
        mode_action_states = self.get_mode_action_states()

        self.add_step_button.configure(
            state="normal" if config_ready and has_selection else "disabled"
        )
        self.save_button.configure(state="normal" if config_ready else "disabled")
        self.run_button.configure(
            state="normal" if config_ready and has_selection else "disabled"
        )
        self.scan_button.configure(
            state="normal" if config_ready and has_selection else "disabled"
        )
        self.stop_button.configure(state="normal" if self.is_running else "disabled")

        self.add_mode_button.configure(state=mode_action_states["add"])
        overflow_state = (
            "normal"
            if any(
                mode_action_states[action] == "normal"
                for action in ("duplicate", "move_up", "move_down", "delete")
            )
            else "disabled"
        )
        self.more_mode_actions_button.configure(state=overflow_state)
        self.refresh_mode_actions_menu()

    def log_perf(self, label: str, started_at: float, details: str = "") -> None:
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        if elapsed_ms < PERF_LOG_THRESHOLD_MS:
            return

        message = f"[perf] {label}: {elapsed_ms:.1f}ms"
        if details:
            message = f"{message} ({details})"

        if elapsed_ms >= PERF_WARN_THRESHOLD_MS:
            self.logger.warning(message)
        else:
            self.logger.info(message)

    def should_sync_editor_state(self) -> bool:
        return self.editor_dirty or self.pending_dirty_after_id is not None

    def sync_selected_mode_if_needed(self, show_dialog: bool, reason: str) -> bool:
        if self.selected_mode_index is None:
            return True
        if not self.should_sync_editor_state():
            return True
        return self.sync_selected_mode_from_widgets(show_dialog=show_dialog, reason=reason)

    def commit_editor_values_if_needed(
        self,
        *,
        show_dialog: bool,
        reason: str,
        success_status: str | None = None,
    ) -> bool:
        commit_needed = self.should_sync_editor_state()
        if not commit_needed:
            return True
        if not self.sync_selected_mode_from_widgets(show_dialog=show_dialog, reason=reason):
            return False
        if success_status:
            self.set_status(success_status)
        return True

    def sync_current_mode_for_sidebar_action(self) -> bool:
        if not self.config_valid or self.is_running:
            return False
        if self.selected_mode_index is None:
            return True
        return self.sync_selected_mode_if_needed(
            show_dialog=True, reason="sidebar_action"
        )

    def select_mode_after_sidebar_change(self, index: int | None) -> None:
        if index is None or not self.config_data.get("modes"):
            self.selected_mode_index = None
            self.config_data["selected_mode_id"] = None
            self.populate_sidebar()
            self.render_selected_mode()
            return

        bounded_index = max(0, min(index, len(self.config_data["modes"]) - 1))
        self.selected_mode_index = bounded_index
        self.config_data["selected_mode_id"] = self.config_data["modes"][bounded_index]["id"]
        self.populate_sidebar()
        self.render_selected_mode()

    def add_mode(self) -> None:
        if not self.sync_current_mode_for_sidebar_action():
            return

        new_mode = self.make_empty_mode("New Mode")
        self.config_data["modes"].append(new_mode)
        self.select_mode_after_sidebar_change(len(self.config_data["modes"]) - 1)
        self.set_dirty(True)
        self.set_status(f"Added mode: {new_mode['name']}")

    def duplicate_selected_mode(self) -> None:
        if self.selected_mode_index is None:
            return
        if not self.sync_current_mode_for_sidebar_action():
            return

        source_mode = self.config_data["modes"][self.selected_mode_index]
        duplicated_mode = {
            "id": self.generate_mode_id(),
            "name": f"{source_mode['name']} Copy",
            "steps": copy.deepcopy(source_mode["steps"]),
        }
        insert_index = self.selected_mode_index + 1
        self.config_data["modes"].insert(insert_index, duplicated_mode)
        self.select_mode_after_sidebar_change(insert_index)
        self.set_dirty(True)
        self.set_status(f"Duplicated mode: {duplicated_mode['name']}")

    def delete_selected_mode(self) -> None:
        if self.selected_mode_index is None:
            return
        if len(self.config_data.get("modes", [])) <= 1:
            messagebox.showinfo(
                "Delete Mode",
                "At least one mode must remain. Add another mode before deleting this one.",
            )
            return
        if not self.sync_current_mode_for_sidebar_action():
            return

        mode = self.config_data["modes"][self.selected_mode_index]
        confirmed = messagebox.askyesno(
            "Delete Mode",
            f"Delete mode '{mode['name']}'?\n\nThis removes it from the in-memory config until you save.",
            icon="warning",
        )
        if not confirmed:
            return

        deleted_index = self.selected_mode_index
        del self.config_data["modes"][deleted_index]
        next_index = min(deleted_index, len(self.config_data["modes"]) - 1)
        self.select_mode_after_sidebar_change(next_index)
        self.set_dirty(True)
        self.set_status(f"Deleted mode: {mode['name']}")

    def move_selected_mode(self, direction: int) -> None:
        if self.selected_mode_index is None:
            return
        if direction not in (-1, 1):
            return
        if not self.sync_current_mode_for_sidebar_action():
            return

        current_index = self.selected_mode_index
        target_index = current_index + direction
        if target_index < 0 or target_index >= len(self.config_data.get("modes", [])):
            return

        modes = self.config_data["modes"]
        moved_mode_name = modes[current_index]["name"]
        modes[current_index], modes[target_index] = modes[target_index], modes[current_index]
        self.select_mode_after_sidebar_change(target_index)
        self.set_dirty(True)
        self.set_status(f"Moved mode: {moved_mode_name}")

    def browse_for_step_path(self, path_var: ctk.StringVar) -> None:
        selected_path = filedialog.askopenfilename(
            parent=self,
            title="Select executable or script",
            filetypes=[
                ("Apps and scripts", "*.exe *.bat *.cmd *.ps1 *.py"),
                ("All files", "*.*"),
            ],
        )
        if not selected_path:
            return

        path_var.set(selected_path.replace("\\", "/"))
        self.set_dirty(True)

    def apply_readiness_preset(
        self,
        readiness_type_var: ctk.StringVar,
        readiness_target_var: ctk.StringVar,
        readiness_timeout_var: ctk.StringVar,
        preset: dict,
    ) -> None:
        readiness_type_var.set(str(preset["type"]))
        readiness_target_var.set(str(preset["target"]))
        readiness_timeout_var.set(str(preset["timeout_seconds"]))
        self.set_dirty(True)
        self.editor_dirty = True

    def open_readiness_preset_menu(
        self,
        anchor_widget: ctk.CTkButton,
        readiness_type_var: ctk.StringVar,
        readiness_target_var: ctk.StringVar,
        readiness_timeout_var: ctk.StringVar,
    ) -> None:
        presets = self.config_data.get("readiness_presets", [])
        menu = tk.Menu(self, tearoff=False)
        if presets:
            for preset in presets:
                menu.add_command(
                    label=preset["name"],
                    command=lambda value=copy.deepcopy(preset): self.apply_readiness_preset(
                        readiness_type_var,
                        readiness_target_var,
                        readiness_timeout_var,
                        value,
                    ),
                )
        else:
            menu.add_command(label="No presets saved", state="disabled")

        x = anchor_widget.winfo_rootx()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def open_readiness_presets_dialog(self) -> None:
        dialog = ReadinessPresetsDialog(self)
        self.wait_window(dialog)

    def make_empty_step(self) -> dict:
        return {
            "name": "New Step",
            "type": "path",
            "path": "",
            "args": [],
            "delay_after": 0,
            "enabled": True,
            "readiness": make_default_readiness(),
            "process_ready": make_default_process_ready(),
            "window_snap": make_default_window_snap(),
        }

    def sync_current_mode_for_step_action(self) -> bool:
        if not self.config_valid or self.is_running:
            return False
        if self.selected_mode_index is None:
            return False
        return self.sync_selected_mode_if_needed(show_dialog=True, reason="step_action")

    def add_step(self) -> None:
        if not self.sync_current_mode_for_step_action():
            return

        mode = self.config_data["modes"][self.selected_mode_index]
        mode["steps"].append(self.make_empty_step())
        self.expanded_step_index = len(mode["steps"]) - 1
        self.render_selected_mode()
        self.set_dirty(True)
        self.set_status(f"Added step to mode: {mode['name']}")

    def duplicate_step(self, step_index: int) -> None:
        if not self.sync_current_mode_for_step_action():
            return

        mode = self.config_data["modes"][self.selected_mode_index]
        if step_index < 0 or step_index >= len(mode["steps"]):
            return

        duplicate = copy.deepcopy(mode["steps"][step_index])
        insert_index = step_index + 1
        mode["steps"].insert(insert_index, duplicate)
        self.expanded_step_index = insert_index
        self.render_selected_mode()
        self.set_dirty(True)
        self.set_status(f"Duplicated step: {duplicate['name']}")

    def confirm_step_delete(self, step_name: str) -> bool:
        if not self.config_data.get("confirm_step_delete", True):
            return True

        dialog = StepDeleteConfirmDialog(self, step_name)
        self.wait_window(dialog)
        if dialog.skip_future_var.get():
            self.config_data["confirm_step_delete"] = False
            self.set_dirty(True)
        return dialog.result

    def delete_step(self, step_index: int) -> None:
        if not self.sync_current_mode_for_step_action():
            return

        mode = self.config_data["modes"][self.selected_mode_index]
        if step_index < 0 or step_index >= len(mode["steps"]):
            return

        step = mode["steps"][step_index]
        confirmed = self.confirm_step_delete(step["name"])
        if not confirmed:
            return

        del mode["steps"][step_index]
        if self.expanded_step_index == step_index:
            self.expanded_step_index = None
        elif self.expanded_step_index is not None and step_index < self.expanded_step_index:
            self.expanded_step_index -= 1
        self.render_selected_mode()
        self.set_dirty(True)
        self.set_status(f"Deleted step: {step['name']}")

    def move_step(self, step_index: int, direction: int) -> None:
        if direction not in (-1, 1):
            return
        if not self.sync_current_mode_for_step_action():
            return

        mode = self.config_data["modes"][self.selected_mode_index]
        target_index = step_index + direction
        if step_index < 0 or target_index < 0 or target_index >= len(mode["steps"]):
            return

        mode["steps"][step_index], mode["steps"][target_index] = (
            mode["steps"][target_index],
            mode["steps"][step_index],
        )
        if self.expanded_step_index == step_index:
            self.expanded_step_index = target_index
        elif self.expanded_step_index == target_index:
            self.expanded_step_index = step_index
        self.render_selected_mode()
        self.set_dirty(True)
        self.set_status(f"Moved step: {mode['steps'][target_index]['name']}")

    def begin_step_drag(self, step_index: int, _event: object = None) -> None:
        if self.selected_mode_index is None or self.is_running or not self.config_valid:
            return
        if step_index < 0 or step_index >= len(self.rendered_step_cards):
            return

        self.clear_step_drag_feedback()
        self.dragged_step_index = step_index
        self.drag_drop_index = step_index
        self.show_step_drag_feedback()

    def handle_step_drag_motion(self, event: object = None) -> None:
        if self.dragged_step_index is None:
            return
        if event is None or not hasattr(event, "y_root"):
            return

        new_drop_index = self.get_step_drop_index(int(event.y_root))
        if new_drop_index == self.drag_drop_index:
            return

        self.drag_drop_index = new_drop_index
        self.show_step_drag_feedback()

    def finish_step_drag(self, _event: object = None) -> None:
        started_at = time.perf_counter()
        if self.dragged_step_index is None:
            return

        dragged_index = self.dragged_step_index
        target_index = (
            self.drag_drop_index if self.drag_drop_index is not None else self.dragged_step_index
        )
        self.clear_step_drag_feedback()

        if target_index is None:
            return
        if not self.sync_selected_mode_if_needed(show_dialog=True, reason="drag_finish"):
            return
        self.reorder_step_to_slot(dragged_index, target_index)
        self.log_perf(
            "finish_step_drag",
            started_at,
            f"from={dragged_index} to={target_index}",
        )

    def clear_step_drag_feedback(self) -> None:
        if self.drag_highlight_card is not None and self.drag_highlight_card.winfo_exists():
            self.drag_highlight_card.configure(border_width=0)
        if self.drag_indicator is not None and self.drag_indicator.winfo_exists():
            self.drag_indicator.place_forget()

        self.dragged_step_index = None
        self.drag_drop_index = None
        self.drag_highlight_card = None
        self.drag_indicator = None

    def show_step_drag_feedback(self) -> None:
        if self.dragged_step_index is None or self.drag_drop_index is None:
            return

        if self.drag_highlight_card is not None and self.drag_highlight_card.winfo_exists():
            self.drag_highlight_card.configure(border_width=0)

        if 0 <= self.dragged_step_index < len(self.rendered_step_cards):
            self.drag_highlight_card = self.rendered_step_cards[self.dragged_step_index]
            if self.drag_highlight_card.winfo_exists():
                self.drag_highlight_card.configure(
                    border_width=2,
                    border_color=("#1F6AA5", "#3B8ED0"),
                )

        self.show_step_insertion_indicator(self.drag_drop_index)

    def show_step_insertion_indicator(self, slot_index: int) -> None:
        if not self.rendered_step_cards:
            return

        if self.drag_indicator is None or not self.drag_indicator.winfo_exists():
            self.drag_indicator = tk.Frame(
                self.steps_frame,
                height=4,
                bg="#2E8B57",
                bd=0,
                highlightthickness=0,
            )

        if slot_index <= 0:
            y_position = self.rendered_step_cards[0].winfo_y()
        elif slot_index >= len(self.rendered_step_cards):
            last_card = self.rendered_step_cards[-1]
            y_position = last_card.winfo_y() + last_card.winfo_height()
        else:
            y_position = self.rendered_step_cards[slot_index].winfo_y()

        self.drag_indicator.place(
            x=STEP_CARD_PADX + 8,
            y=max(0, y_position - 2),
            width=max(40, self.steps_frame.winfo_width() - ((STEP_CARD_PADX + 8) * 2)),
        )
        self.drag_indicator.lift()

    def get_step_drop_index(self, pointer_y: int) -> int:
        if not self.rendered_step_cards:
            return 0

        for index, card in enumerate(self.rendered_step_cards):
            if not card.winfo_exists():
                continue

            top = card.winfo_rooty()
            bottom = top + card.winfo_height()
            midpoint = top + (card.winfo_height() / 2)

            if pointer_y < top:
                return index
            if top <= pointer_y <= midpoint:
                return index
            if midpoint < pointer_y <= bottom:
                return index + 1

        return len(self.rendered_step_cards)

    def reorder_step_to_slot(self, dragged_index: int, target_index: int) -> None:
        started_at = time.perf_counter()
        if self.selected_mode_index is None:
            return

        mode = self.config_data["modes"][self.selected_mode_index]
        steps = mode["steps"]
        if (
            dragged_index < 0
            or dragged_index >= len(steps)
            or target_index < 0
            or target_index > len(steps)
        ):
            return

        insert_index = target_index
        if target_index > dragged_index:
            insert_index -= 1
        if insert_index == dragged_index:
            return

        moved_step = steps.pop(dragged_index)
        steps.insert(insert_index, moved_step)

        if self.expanded_step_index == dragged_index:
            self.expanded_step_index = insert_index
        elif self.expanded_step_index is not None:
            if dragged_index < self.expanded_step_index <= insert_index:
                self.expanded_step_index -= 1
            elif insert_index <= self.expanded_step_index < dragged_index:
                self.expanded_step_index += 1

        self.render_selected_mode()
        self.set_dirty(True)
        self.set_status(f"Reordered step: {moved_step['name']}")
        self.log_perf(
            "reorder_step_to_slot",
            started_at,
            f"from={dragged_index} to_slot={target_index} insert={insert_index}",
        )

    def toggle_step_expanded(self, step_index: int) -> None:
        if self.selected_mode_index is None:
            return

        if self.expanded_step_index == step_index:
            if self.step_widgets and not self.commit_editor_values_if_needed(
                show_dialog=True,
                reason="hide_step",
                success_status="Step changes applied",
            ):
                return
            self.expanded_step_index = None
            self.render_selected_mode()
            return

        if self.step_widgets and not self.commit_editor_values_if_needed(
            show_dialog=False,
            reason="toggle_step",
        ):
            return

        self.expanded_step_index = step_index
        self.render_selected_mode()

    def bind_text_dirty_tracking(self, widget: ctk.CTkEntry) -> None:
        widget.bind("<KeyRelease>", self.schedule_dirty_mark, add="+")
        widget.bind("<FocusOut>", self.mark_dirty_from_event, add="+")
        widget.bind("<Return>", self.mark_dirty_from_event, add="+")

    def schedule_dirty_mark(self, _event: object = None) -> None:
        if self.suspend_dirty_tracking or not self.config_valid:
            return
        if self.pending_dirty_after_id is not None:
            try:
                self.after_cancel(self.pending_dirty_after_id)
            except TclError:
                pass
        self.pending_dirty_after_id = self.after(DIRTY_MARK_DELAY_MS, self.commit_pending_dirty_mark)

    def commit_pending_dirty_mark(self) -> None:
        self.pending_dirty_after_id = None
        if self.suspend_dirty_tracking or not self.config_valid:
            return
        self.is_dirty = True
        self.editor_dirty = True

    def mark_dirty_from_event(self, _event: object = None) -> None:
        if self.suspend_dirty_tracking or not self.config_valid:
            return
        if self.pending_dirty_after_id is not None:
            try:
                self.after_cancel(self.pending_dirty_after_id)
            except TclError:
                pass
            self.pending_dirty_after_id = None
        self.is_dirty = True
        self.editor_dirty = True

    def select_mode(self, index: int, force: bool = False) -> None:
        started_at = time.perf_counter()
        if not self.config_valid:
            return
        self.clear_step_drag_feedback()
        if index < 0 or index >= len(self.config_data.get("modes", [])):
            return
        if not force and self.selected_mode_index == index:
            return
        if (
            not force
            and self.selected_mode_index is not None
            and not self.sync_selected_mode_if_needed(show_dialog=True, reason="mode_switch")
        ):
            return

        selection_changed = self.selected_mode_index != index
        self.selected_mode_index = index
        self.config_data["selected_mode_id"] = self.config_data["modes"][index]["id"]
        if selection_changed:
            self.expanded_step_index = None
        self.render_selected_mode()
        if not self.is_running:
            self.set_status(f"Selected mode: {self.config_data['modes'][index]['name']}")
        if selection_changed and not force:
            self.set_dirty(True)
        self.log_perf("select_mode", started_at, f"index={index}")

    def render_selected_mode(self) -> None:
        started_at = time.perf_counter()
        step_count = 0
        self.suspend_dirty_tracking = True
        for child in self.steps_frame.winfo_children():
            child.destroy()

        self.step_widgets.clear()
        self.rendered_step_cards.clear()
        self.clear_step_drag_feedback()

        if self.selected_mode_index is None:
            self.editor_title.configure(text="Selected Mode")
            self.mode_name_var.set("")
            self.auto_start_var.set(bool(self.config_data.get("auto_start_on_launch", False)))
            self.mode_name_entry.configure(state="disabled")
            self.auto_start_checkbox.configure(state="disabled")
            empty_message = ctk.CTkLabel(
                self.steps_frame,
                text="No mode is selected. Use Add Mode in the sidebar to create one.",
                justify="left",
                text_color=("gray35", "gray70"),
                wraplength=900,
            )
            empty_message.grid(row=0, column=0, padx=18, pady=18, sticky="w")
            self.suspend_dirty_tracking = False
            self.editor_dirty = False
            self.refresh_action_states()
            self.log_perf("render_selected_mode", started_at, "steps=0 selected=none")
            return

        for button_index, button in enumerate(self.mode_buttons):
            if button_index == self.selected_mode_index:
                button.configure(
                    fg_color=SIDEBAR_BUTTON_SELECTED_FG,
                    hover_color=SIDEBAR_BUTTON_SELECTED_HOVER,
                    text_color=SIDEBAR_BUTTON_SELECTED_TEXT,
                )
            else:
                button.configure(
                    fg_color=SIDEBAR_BUTTON_FG,
                    hover_color=SIDEBAR_BUTTON_HOVER,
                    text_color=SIDEBAR_BUTTON_TEXT,
                )

        mode = self.config_data["modes"][self.selected_mode_index]
        step_count = len(mode["steps"])
        if self.expanded_step_index is not None and self.expanded_step_index >= len(mode["steps"]):
            self.expanded_step_index = None
        self.editor_title.configure(text="Selected Mode")
        self.mode_name_entry.configure(state="normal")
        self.auto_start_checkbox.configure(state="normal")
        self.mode_name_var.set(mode["name"])
        self.auto_start_var.set(bool(self.config_data.get("auto_start_on_launch", False)))

        if not mode["steps"]:
            empty_steps_label = ctk.CTkLabel(
                self.steps_frame,
                text="No steps in this mode yet. Use Add Step to build this mode.",
                text_color=("gray35", "gray70"),
            )
            empty_steps_label.grid(row=0, column=0, padx=10, pady=6, sticky="w")

        for step_index, step in enumerate(mode["steps"], start=1):
            card = ctk.CTkFrame(self.steps_frame, corner_radius=8)
            card.grid(
                row=step_index - 1,
                column=0,
                padx=STEP_CARD_PADX,
                pady=STEP_CARD_PADY,
                sticky="ew",
            )
            card.grid_columnconfigure(0, weight=0)
            card.grid_columnconfigure(1, weight=0)
            card.grid_columnconfigure(2, weight=1)
            card.grid_columnconfigure(3, weight=0)
            card.grid_columnconfigure(4, weight=0)
            card.grid_columnconfigure(5, weight=0)

            name_var = ctk.StringVar(value=step["name"])
            type_var = ctk.StringVar(value=step["type"])
            path_var = ctk.StringVar(value=step["path"])
            args_var = ctk.StringVar(value=args_to_text(step["args"]))
            delay_var = ctk.StringVar(value=str(step["delay_after"]))
            enabled_var = ctk.BooleanVar(value=step["enabled"])
            readiness = normalize_readiness_config(step.get("readiness"))
            process_ready = normalize_process_ready_config(
                step.get("process_ready"),
                step["type"],
                step["path"],
            )
            readiness_type_var = ctk.StringVar(value=readiness["type"])
            readiness_target_var = ctk.StringVar(value=readiness["target"])
            readiness_timeout_var = ctk.StringVar(value=str(readiness["timeout_seconds"]))
            process_ready_enabled_var = ctk.BooleanVar(value=process_ready["enabled"])
            process_ready_name_var = ctk.StringVar(value=process_ready["name"])
            process_ready_timeout_var = ctk.StringVar(
                value=str(process_ready["timeout_seconds"])
            )
            process_settle_delay_var = ctk.StringVar(
                value=str(process_ready["settle_delay_seconds"])
            )
            window_snap = normalize_window_snap_config(step.get("window_snap"))
            snap_enabled_var = ctk.BooleanVar(value=window_snap["snap_enabled"])
            snap_match_mode_var = ctk.StringVar(value=window_snap["window_match_mode"])
            snap_match_value_var = ctk.StringVar(value=window_snap["window_match_value"])
            snap_x_var = ctk.StringVar(value=str(window_snap["snap_x"]))
            snap_y_var = ctk.StringVar(value=str(window_snap["snap_y"]))
            snap_width_var = ctk.StringVar(value=str(window_snap["snap_width"]))
            snap_height_var = ctk.StringVar(value=str(window_snap["snap_height"]))
            snap_timeout_var = ctk.StringVar(value=str(window_snap["snap_timeout_sec"]))
            type_var.trace_add("write", self.on_editor_changed)
            enabled_var.trace_add("write", self.on_editor_changed)
            readiness_type_var.trace_add("write", self.on_editor_changed)
            process_ready_enabled_var.trace_add("write", self.on_editor_changed)
            snap_enabled_var.trace_add("write", self.on_editor_changed)
            snap_match_mode_var.trace_add("write", self.on_editor_changed)

            drag_handle = ctk.CTkButton(
                card,
                text="|||",
                width=STEP_DRAG_HANDLE_WIDTH,
                height=STEP_ENTRY_HEIGHT,
                font=self.step_button_bold_font,
                fg_color=("gray78", "gray24"),
                hover_color=("gray70", "gray30"),
                text_color=("gray20", "gray88"),
                cursor="fleur",
                state="normal" if self.config_valid and not self.is_running else "disabled",
            )
            drag_handle.grid(
                row=0,
                column=0,
                padx=(STEP_CARD_INNER_PADX, 4),
                pady=(STEP_CARD_TOP_PADY, 5),
                sticky="w",
            )
            drag_handle.bind(
                "<ButtonPress-1>",
                lambda event, idx=step_index - 1: self.begin_step_drag(idx, event),
                add="+",
            )
            drag_handle.bind("<B1-Motion>", self.handle_step_drag_motion, add="+")
            drag_handle.bind("<ButtonRelease-1>", self.finish_step_drag, add="+")

            summary_number = ctk.CTkLabel(
                card,
                text=f"Step {step_index}",
                font=self.step_title_font,
            )
            summary_number.grid(
                row=0,
                column=1,
                padx=(0, STEP_CARD_INNER_PADX),
                pady=(STEP_CARD_TOP_PADY, 5),
                sticky="w",
            )

            summary_name = ctk.CTkLabel(
                card,
                text=name_var.get() or "(unnamed step)",
                anchor="w",
                font=self.step_title_font,
            )
            summary_name.grid(
                row=0,
                column=2,
                padx=STEP_CARD_INNER_PADX,
                pady=(STEP_CARD_TOP_PADY, 5),
                sticky="ew",
            )

            enabled_text = "Enabled" if enabled_var.get() else "Disabled"
            summary_meta = ctk.CTkLabel(
                card,
                text=f"{type_var.get().upper()}  |  Delay {delay_var.get() or '0'}s  |  {enabled_text}",
                anchor="w",
                font=self.step_meta_font,
            )
            summary_meta.grid(
                row=0,
                column=3,
                padx=STEP_CARD_INNER_PADX,
                pady=(STEP_CARD_TOP_PADY, 5),
                sticky="ew",
            )

            toggle_button = ctk.CTkButton(
                card,
                text="Hide" if self.expanded_step_index == step_index - 1 else "Edit",
                width=STEP_SUMMARY_BUTTON_WIDTH,
                height=STEP_ENTRY_HEIGHT,
                font=self.step_button_font,
                command=lambda idx=step_index - 1: self.toggle_step_expanded(idx),
            )
            toggle_button.grid(
                row=0,
                column=4,
                padx=(0, 6),
                pady=(STEP_CARD_TOP_PADY, 5),
                sticky="e",
            )

            remove_button = ctk.CTkButton(
                card,
                text="Remove",
                width=STEP_REMOVE_BUTTON_WIDTH,
                height=STEP_ENTRY_HEIGHT,
                font=self.step_button_font,
                fg_color="#b34141",
                hover_color="#943333",
                state="normal" if self.config_valid and not self.is_running else "disabled",
                command=lambda idx=step_index - 1: self.delete_step(idx),
            )
            remove_button.grid(
                row=0,
                column=5,
                padx=(0, STEP_CARD_INNER_PADX),
                pady=(STEP_CARD_TOP_PADY, 5),
                sticky="e",
            )

            if self.expanded_step_index == step_index - 1:
                detail_frame = ctk.CTkFrame(card, fg_color="transparent")
                detail_frame.grid(
                    row=1,
                    column=0,
                    columnspan=6,
                    padx=STEP_CARD_INNER_PADX,
                    pady=(0, 6),
                    sticky="ew",
                )
                detail_frame.grid_columnconfigure(0, weight=1)
                detail_frame.grid_columnconfigure(1, weight=0)
                detail_frame.grid_columnconfigure(2, weight=0)
                detail_frame.grid_columnconfigure(3, weight=0)

                detail_name_label = ctk.CTkLabel(
                    detail_frame,
                    text="Name",
                    font=self.step_detail_label_font,
                    text_color=("gray35", "gray70"),
                )
                detail_name_label.grid(row=0, column=0, padx=(0, 8), pady=(0, 2), sticky="w")

                detail_type_label = ctk.CTkLabel(
                    detail_frame,
                    text="Type",
                    font=self.step_detail_label_font,
                    text_color=("gray35", "gray70"),
                )
                detail_type_label.grid(row=0, column=1, padx=(0, 8), pady=(0, 2), sticky="w")

                detail_delay_label = ctk.CTkLabel(
                    detail_frame,
                    text="Delay",
                    font=self.step_detail_label_font,
                    text_color=("gray35", "gray70"),
                )
                detail_delay_label.grid(row=0, column=2, padx=(0, 8), pady=(0, 2), sticky="w")

                detail_enabled_label = ctk.CTkLabel(
                    detail_frame,
                    text="Enabled",
                    font=self.step_detail_label_font,
                    text_color=("gray35", "gray70"),
                )
                detail_enabled_label.grid(row=0, column=3, pady=(0, 2), sticky="w")

                name_entry = ctk.CTkEntry(
                    detail_frame,
                    textvariable=name_var,
                    height=STEP_ENTRY_HEIGHT,
                    placeholder_text="Name",
                )
                name_entry.grid(row=1, column=0, padx=(0, 8), pady=(0, 6), sticky="ew")
                self.bind_text_dirty_tracking(name_entry)

                type_menu = ctk.CTkSegmentedButton(
                    detail_frame,
                    variable=type_var,
                    values=list(STEP_TYPES),
                    height=STEP_SEGMENTED_HEIGHT,
                    font=self.step_button_font,
                    dynamic_resizing=False,
                )
                type_menu.grid(row=1, column=1, padx=(0, 8), pady=(0, 6), sticky="ew")

                delay_entry = ctk.CTkEntry(
                    detail_frame,
                    textvariable=delay_var,
                    width=88,
                    height=STEP_ENTRY_HEIGHT,
                    placeholder_text="Delay (s)",
                )
                delay_entry.grid(row=1, column=2, padx=(0, 8), pady=(0, 6), sticky="ew")
                self.bind_text_dirty_tracking(delay_entry)

                enabled_checkbox = ctk.CTkCheckBox(detail_frame, text="", variable=enabled_var, width=24)
                enabled_checkbox.grid(row=1, column=3, pady=(0, 6), sticky="w")

                path_label = ctk.CTkLabel(
                    detail_frame,
                    text="Path" if type_var.get() == "path" else "URL",
                    font=self.step_detail_label_font,
                    text_color=("gray35", "gray70"),
                )
                path_label.grid(row=2, column=0, columnspan=3, padx=(0, 8), pady=(0, 2), sticky="w")

                path_entry = ctk.CTkEntry(
                    detail_frame,
                    textvariable=path_var,
                    height=STEP_ENTRY_HEIGHT,
                    placeholder_text="Path or URL",
                )
                path_entry.grid(row=3, column=0, columnspan=3, padx=(0, 8), pady=(0, 6), sticky="ew")
                self.bind_text_dirty_tracking(path_entry)

                browse_button = ctk.CTkButton(
                    detail_frame,
                    text="Browse",
                    width=STEP_BROWSE_WIDTH,
                    height=STEP_ENTRY_HEIGHT,
                    font=self.step_button_font,
                    command=lambda value=path_var: self.browse_for_step_path(value),
                )
                browse_button.grid(row=3, column=3, pady=(0, 6), sticky="e")

                args_label = ctk.CTkLabel(
                    detail_frame,
                    text="Args",
                    font=self.step_detail_label_font,
                    text_color=("gray35", "gray70"),
                )
                args_label.grid(row=4, column=0, columnspan=4, pady=(0, 2), sticky="w")

                args_entry = ctk.CTkEntry(
                    detail_frame,
                    textvariable=args_var,
                    height=STEP_ENTRY_HEIGHT,
                    placeholder_text='Example: --profile-directory="Profile 1"',
                )
                args_entry.grid(row=5, column=0, columnspan=4, pady=(0, 2), sticky="ew")
                self.bind_text_dirty_tracking(args_entry)

                args_help = ctk.CTkLabel(
                    detail_frame,
                    text='Example: --profile-directory="Profile 1"',
                    font=self.step_detail_help_font,
                    text_color=("gray35", "gray70"),
                )
                args_help.grid(row=6, column=0, columnspan=4, pady=(0, 2), sticky="w")

                readiness_label = ctk.CTkLabel(
                    detail_frame,
                    text="Readiness",
                    font=self.step_detail_label_font,
                    text_color=("gray35", "gray70"),
                )
                readiness_label.grid(row=7, column=0, padx=(0, 8), pady=(2, 1), sticky="w")

                readiness_target_label = ctk.CTkLabel(
                    detail_frame,
                    text="Target",
                    font=self.step_detail_label_font,
                    text_color=("gray35", "gray70"),
                )
                readiness_target_label.grid(row=7, column=1, columnspan=2, padx=(0, 8), pady=(2, 1), sticky="w")

                readiness_timeout_label = ctk.CTkLabel(
                    detail_frame,
                    text="Timeout",
                    font=self.step_detail_label_font,
                    text_color=("gray35", "gray70"),
                )
                readiness_timeout_label.grid(row=7, column=3, pady=(2, 1), sticky="w")

                readiness_type_menu = ctk.CTkSegmentedButton(
                    detail_frame,
                    variable=readiness_type_var,
                    values=list(READINESS_TYPES),
                    height=STEP_SEGMENTED_HEIGHT,
                    font=self.step_button_font,
                    dynamic_resizing=False,
                )
                readiness_type_menu.grid(row=8, column=0, padx=(0, 8), pady=(0, 4), sticky="ew")

                readiness_target_entry = ctk.CTkEntry(
                    detail_frame,
                    textvariable=readiness_target_var,
                    height=STEP_ENTRY_HEIGHT,
                    placeholder_text="host:port or URL",
                )
                readiness_target_entry.grid(row=8, column=1, columnspan=2, padx=(0, 8), pady=(0, 4), sticky="ew")
                self.bind_text_dirty_tracking(readiness_target_entry)

                readiness_timeout_entry = ctk.CTkEntry(
                    detail_frame,
                    textvariable=readiness_timeout_var,
                    width=96,
                    height=STEP_ENTRY_HEIGHT,
                    placeholder_text="60",
                )
                readiness_timeout_entry.grid(row=8, column=3, pady=(0, 4), sticky="ew")
                self.bind_text_dirty_tracking(readiness_timeout_entry)

                readiness_help = ctk.CTkLabel(
                    detail_frame,
                    text="none = delay only | port = host:port accepts TCP | url = HTTP responds",
                    font=self.step_detail_help_font,
                    text_color=("gray35", "gray70"),
                )
                readiness_help.grid(row=9, column=0, columnspan=4, pady=(0, 2), sticky="w")

                process_ready_header = ctk.CTkFrame(detail_frame, fg_color="transparent")
                process_ready_header.grid(row=10, column=0, columnspan=4, pady=(0, 2), sticky="ew")
                process_ready_header.grid_columnconfigure(1, weight=1)

                process_ready_checkbox = ctk.CTkCheckBox(
                    process_ready_header,
                    text="Process Ready",
                    variable=process_ready_enabled_var,
                )
                process_ready_checkbox.grid(row=0, column=0, padx=(0, 8), sticky="w")

                process_ready_name_entry = ctk.CTkEntry(
                    process_ready_header,
                    textvariable=process_ready_name_var,
                    height=STEP_ENTRY_HEIGHT,
                    placeholder_text="tailscale-ipn.exe",
                )
                process_ready_name_entry.grid(row=0, column=1, padx=(0, 8), sticky="ew")
                self.bind_text_dirty_tracking(process_ready_name_entry)

                process_ready_timeout_entry = ctk.CTkEntry(
                    process_ready_header,
                    textvariable=process_ready_timeout_var,
                    width=74,
                    height=STEP_ENTRY_HEIGHT,
                    placeholder_text="30",
                )
                process_ready_timeout_entry.grid(row=0, column=2, padx=(0, 8), sticky="w")
                self.bind_text_dirty_tracking(process_ready_timeout_entry)

                process_settle_delay_entry = ctk.CTkEntry(
                    process_ready_header,
                    textvariable=process_settle_delay_var,
                    width=74,
                    height=STEP_ENTRY_HEIGHT,
                    placeholder_text="0",
                )
                process_settle_delay_entry.grid(row=0, column=3, sticky="w")
                self.bind_text_dirty_tracking(process_settle_delay_entry)

                process_ready_help = ctk.CTkLabel(
                    detail_frame,
                    text="Optional for tray/background apps: wait for a process name, then optionally settle before the next step.",
                    font=self.step_detail_help_font,
                    text_color=("gray35", "gray70"),
                )
                process_ready_help.grid(row=11, column=0, columnspan=4, pady=(0, 2), sticky="w")

                snap_header = ctk.CTkFrame(detail_frame, fg_color="transparent")
                snap_header.grid(row=12, column=0, columnspan=4, pady=(0, 2), sticky="ew")
                snap_header.grid_columnconfigure(2, weight=1)

                snap_enabled_checkbox = ctk.CTkCheckBox(
                    snap_header,
                    text="Snap Window",
                    variable=snap_enabled_var,
                )
                snap_enabled_checkbox.grid(row=0, column=0, padx=(0, 8), sticky="w")

                snap_match_mode_menu = ctk.CTkSegmentedButton(
                    snap_header,
                    variable=snap_match_mode_var,
                    values=list(WINDOW_MATCH_MODES),
                    width=248,
                    height=24,
                    font=self.step_detail_help_font,
                    dynamic_resizing=False,
                )
                snap_match_mode_menu.grid(row=0, column=1, padx=(0, 8), sticky="w")

                snap_match_value_entry = ctk.CTkEntry(
                    snap_header,
                    textvariable=snap_match_value_var,
                    height=STEP_ENTRY_HEIGHT,
                    placeholder_text="window title text or process name",
                )
                snap_match_value_entry.grid(row=0, column=2, sticky="ew")
                self.bind_text_dirty_tracking(snap_match_value_entry)

                snap_geometry_frame = ctk.CTkFrame(detail_frame, fg_color="transparent")
                snap_geometry_frame.grid(row=13, column=0, columnspan=4, pady=(0, 2), sticky="ew")
                snap_geometry_frame.grid_columnconfigure(1, weight=0)
                snap_geometry_frame.grid_columnconfigure(3, weight=0)
                snap_geometry_frame.grid_columnconfigure(5, weight=0)
                snap_geometry_frame.grid_columnconfigure(7, weight=0)
                snap_geometry_frame.grid_columnconfigure(9, weight=0)
                snap_geometry_frame.grid_columnconfigure(10, weight=1)

                for label_text, column in (("X", 0), ("Y", 2), ("W", 4), ("H", 6), ("Timeout", 8)):
                    label = ctk.CTkLabel(
                        snap_geometry_frame,
                        text=label_text,
                        font=self.step_detail_help_font,
                        text_color=("gray35", "gray70"),
                    )
                    label.grid(row=0, column=column, padx=(0, 4), sticky="w")

                snap_x_entry = ctk.CTkEntry(snap_geometry_frame, textvariable=snap_x_var, width=62, height=STEP_ENTRY_HEIGHT)
                snap_x_entry.grid(row=0, column=1, padx=(0, 8), sticky="w")
                self.bind_text_dirty_tracking(snap_x_entry)

                snap_y_entry = ctk.CTkEntry(snap_geometry_frame, textvariable=snap_y_var, width=62, height=STEP_ENTRY_HEIGHT)
                snap_y_entry.grid(row=0, column=3, padx=(0, 8), sticky="w")
                self.bind_text_dirty_tracking(snap_y_entry)

                snap_width_entry = ctk.CTkEntry(snap_geometry_frame, textvariable=snap_width_var, width=72, height=STEP_ENTRY_HEIGHT)
                snap_width_entry.grid(row=0, column=5, padx=(0, 8), sticky="w")
                self.bind_text_dirty_tracking(snap_width_entry)

                snap_height_entry = ctk.CTkEntry(snap_geometry_frame, textvariable=snap_height_var, width=72, height=STEP_ENTRY_HEIGHT)
                snap_height_entry.grid(row=0, column=7, padx=(0, 8), sticky="w")
                self.bind_text_dirty_tracking(snap_height_entry)

                snap_timeout_entry = ctk.CTkEntry(snap_geometry_frame, textvariable=snap_timeout_var, width=72, height=STEP_ENTRY_HEIGHT)
                snap_timeout_entry.grid(row=0, column=9, padx=(0, 8), sticky="w")
                self.bind_text_dirty_tracking(snap_timeout_entry)

                capture_window_button = ctk.CTkButton(
                    snap_geometry_frame,
                    text="Capture Current Window",
                    width=144,
                    height=24,
                    font=self.step_detail_help_font,
                    state="normal" if self.config_valid and not self.is_running else "disabled",
                    command=lambda name_ref=name_var, step_type_ref=type_var, path_ref=path_var, enabled_ref=snap_enabled_var, mode_ref=snap_match_mode_var, value_ref=snap_match_value_var, x_ref=snap_x_var, y_ref=snap_y_var, w_ref=snap_width_var, h_ref=snap_height_var: self.capture_current_window_for_step(
                        name_ref.get().strip() or "Step",
                        step_type_ref.get(),
                        path_ref,
                        enabled_ref,
                        mode_ref,
                        value_ref,
                        x_ref,
                        y_ref,
                        w_ref,
                        h_ref,
                    ),
                )
                capture_window_button.grid(row=0, column=10, sticky="e")

                snap_help = ctk.CTkLabel(
                    detail_frame,
                    text="Optional: wait for a top-level window and move/resize it after launch.",
                    font=self.step_detail_help_font,
                    text_color=("gray35", "gray70"),
                )
                snap_help.grid(row=14, column=0, columnspan=4, pady=(0, 2), sticky="w")

                action_band = ctk.CTkFrame(detail_frame, fg_color="transparent")
                action_band.grid(row=15, column=0, columnspan=4, pady=(0, 2), sticky="ew")
                action_band.grid_columnconfigure(3, weight=1)

                presets_label = ctk.CTkLabel(
                    action_band,
                    text="Preset",
                    font=self.step_detail_help_font,
                    text_color=("gray35", "gray70"),
                )
                presets_label.grid(row=0, column=0, padx=(0, 6), sticky="w")

                apply_preset_button = ctk.CTkButton(
                    action_band,
                    text="Apply",
                    width=62,
                    height=24,
                    font=self.step_detail_help_font,
                    command=lambda button_ref=None, rt=readiness_type_var, rg=readiness_target_var, to=readiness_timeout_var: None,
                )
                apply_preset_button.configure(
                    command=lambda button_ref=apply_preset_button, rt=readiness_type_var, rg=readiness_target_var, to=readiness_timeout_var: self.open_readiness_preset_menu(
                        button_ref,
                        rt,
                        rg,
                        to,
                    )
                )
                apply_preset_button.grid(row=0, column=1, padx=(0, 6), sticky="w")

                manage_presets_button = ctk.CTkButton(
                    action_band,
                    text="Manage",
                    width=74,
                    height=24,
                    font=self.step_detail_help_font,
                    command=self.open_readiness_presets_dialog,
                )
                manage_presets_button.grid(row=0, column=2, padx=(0, 12), sticky="w")

                duplicate_button = ctk.CTkButton(
                    action_band,
                    text="Duplicate Step",
                    width=108,
                    height=24,
                    font=self.step_button_font,
                    state="normal" if self.config_valid and not self.is_running else "disabled",
                    command=lambda idx=step_index - 1: self.duplicate_step(idx),
                )
                duplicate_button.grid(row=0, column=6, sticky="e")

                move_up_button = ctk.CTkButton(
                    action_band,
                    text="Move Up",
                    width=84,
                    height=24,
                    font=self.step_button_font,
                    state="normal"
                    if self.config_valid and not self.is_running and step_index > 1
                    else "disabled",
                    command=lambda idx=step_index - 1: self.move_step(idx, -1),
                )
                move_up_button.grid(row=0, column=4, padx=(0, 6), sticky="e")

                move_down_button = ctk.CTkButton(
                    action_band,
                    text="Move Down",
                    width=96,
                    height=24,
                    font=self.step_button_font,
                    state="normal"
                    if self.config_valid and not self.is_running and step_index < len(mode["steps"])
                    else "disabled",
                    command=lambda idx=step_index - 1: self.move_step(idx, 1),
                )
                move_down_button.grid(row=0, column=5, padx=(0, 6), sticky="e")

                def refresh_expanded_step_ui(*_args: object) -> None:
                    is_path_step = type_var.get() == "path"
                    readiness_type = readiness_type_var.get()
                    process_ready_enabled = bool(process_ready_enabled_var.get())
                    snap_enabled = bool(snap_enabled_var.get())
                    snap_match_mode = snap_match_mode_var.get()
                    path_label.configure(text="Path" if is_path_step else "URL")
                    browse_button.configure(state="normal" if is_path_step else "disabled")
                    readiness_target_entry.configure(
                        state="normal" if readiness_type != "none" else "disabled"
                    )
                    readiness_timeout_entry.configure(
                        state="normal" if readiness_type != "none" else "disabled"
                    )
                    if readiness_type == "port":
                        readiness_target_label.configure(text="Host:Port")
                        readiness_target_entry.configure(placeholder_text="127.0.0.1:5678")
                        readiness_help.configure(
                            text="port = wait until host:port accepts a TCP connection"
                        )
                    elif readiness_type == "url":
                        readiness_target_label.configure(text="URL")
                        readiness_target_entry.configure(placeholder_text="http://127.0.0.1:3000")
                        readiness_help.configure(
                            text="url = wait until the URL returns an HTTP 2xx or 3xx response"
                        )
                    else:
                        readiness_target_label.configure(text="Target")
                        readiness_target_entry.configure(placeholder_text="host:port or URL")
                        readiness_help.configure(
                            text="none = no readiness check; only delay_after is used"
                        )
                    process_controls_enabled = process_ready_enabled and is_path_step
                    process_ready_checkbox.configure(
                        state="normal" if is_path_step else "disabled"
                    )
                    process_ready_name_entry.configure(
                        state="normal" if process_controls_enabled else "disabled"
                    )
                    process_ready_timeout_entry.configure(
                        state="normal" if process_controls_enabled else "disabled"
                    )
                    process_settle_delay_entry.configure(
                        state="normal" if process_controls_enabled else "disabled"
                    )
                    if is_path_step:
                        process_ready_help.configure(
                            text="Optional for tray/background apps: wait for a process name, then optionally settle before the next step."
                        )
                    else:
                        process_ready_help.configure(
                            text="Process readiness is available for path steps only."
                        )
                    snap_controls_enabled = snap_enabled and snap_match_mode != "none"
                    snap_match_mode_menu.configure(state="normal" if snap_enabled else "disabled")
                    snap_match_value_entry.configure(state="normal" if snap_controls_enabled else "disabled")
                    for entry in (
                        snap_x_entry,
                        snap_y_entry,
                        snap_width_entry,
                        snap_height_entry,
                        snap_timeout_entry,
                    ):
                        entry.configure(state="normal" if snap_controls_enabled else "disabled")
                    capture_window_button.configure(
                        state="normal" if self.config_valid and not self.is_running else "disabled"
                    )
                    if snap_match_mode == "title_contains":
                        snap_match_value_entry.configure(placeholder_text="part of the window title")
                        snap_help.configure(
                            text="title_contains = first visible top-level window whose title contains the text"
                        )
                    elif snap_match_mode == "process_name":
                        snap_match_value_entry.configure(placeholder_text="app.exe")
                        snap_help.configure(
                            text="process_name = first visible top-level window whose process name matches"
                        )
                    else:
                        snap_match_value_entry.configure(placeholder_text="window title text or process name")
                        snap_help.configure(
                            text="Optional: wait for a top-level window and move/resize it after launch."
                        )

                type_var.trace_add("write", refresh_expanded_step_ui)
                readiness_type_var.trace_add("write", refresh_expanded_step_ui)
                process_ready_enabled_var.trace_add("write", refresh_expanded_step_ui)
                snap_enabled_var.trace_add("write", refresh_expanded_step_ui)
                snap_match_mode_var.trace_add("write", refresh_expanded_step_ui)
                refresh_expanded_step_ui()

            self.step_widgets.append(
                {
                    "name_var": name_var,
                    "type_var": type_var,
                    "path_var": path_var,
                    "args_var": args_var,
                    "delay_var": delay_var,
                    "enabled_var": enabled_var,
                    "readiness_type_var": readiness_type_var,
                    "readiness_target_var": readiness_target_var,
                    "readiness_timeout_var": readiness_timeout_var,
                    "process_ready_enabled_var": process_ready_enabled_var,
                    "process_ready_name_var": process_ready_name_var,
                    "process_ready_timeout_var": process_ready_timeout_var,
                    "process_settle_delay_var": process_settle_delay_var,
                    "snap_enabled_var": snap_enabled_var,
                    "snap_match_mode_var": snap_match_mode_var,
                    "snap_match_value_var": snap_match_value_var,
                    "snap_x_var": snap_x_var,
                    "snap_y_var": snap_y_var,
                    "snap_width_var": snap_width_var,
                    "snap_height_var": snap_height_var,
                    "snap_timeout_var": snap_timeout_var,
                }
            )
            self.rendered_step_cards.append(card)
        self.suspend_dirty_tracking = False
        self.editor_dirty = False
        self.refresh_action_states()
        self.log_perf(
            "render_selected_mode",
            started_at,
            f"steps={step_count}",
        )

    def disable_config_actions(self) -> None:
        self.refresh_action_states()

    def set_run_state(self, running: bool) -> None:
        self.is_running = running
        self.refresh_action_states()

    def on_editor_changed(self, *_args: object) -> None:
        if self.suspend_dirty_tracking or not self.config_valid:
            return
        self.is_dirty = True
        self.editor_dirty = True

    def set_dirty(self, is_dirty: bool) -> None:
        if not is_dirty and self.pending_dirty_after_id is not None:
            try:
                self.after_cancel(self.pending_dirty_after_id)
            except TclError:
                pass
            self.pending_dirty_after_id = None
        self.is_dirty = is_dirty
        if not is_dirty:
            self.editor_dirty = False

    def set_status(self, message: str) -> None:
        if self.status_var.get() == message:
            return
        self.status_var.set(message)

    def enqueue_status(self, message: str) -> None:
        self.status_queue.put(message)

    def schedule_auto_start_if_enabled(self) -> None:
        if self.launch_auto_start_scheduled or not self.config_valid:
            return
        if not self.config_data.get("auto_start_on_launch"):
            return
        if self.selected_mode_index is None:
            return

        self.launch_auto_start_scheduled = True
        self.after(250, self.auto_start_selected_mode_after_load)

    def auto_start_selected_mode_after_load(self) -> None:
        if self.is_shutting_down or not self.config_valid:
            return
        self.logger.info("Auto-start enabled. Running selected mode after app launch.")
        self.set_status("Auto-starting selected mode...")
        self.run_selected_mode()

    def open_process_scan_dialog(self) -> None:
        if not self.config_valid or self.selected_mode_index is None:
            return
        if not self.sync_selected_mode_if_needed(show_dialog=True, reason="scan_dialog"):
            return

        process_entries = self.collect_running_process_entries()
        if not process_entries:
            self.set_status("No importable running apps found")
            messagebox.showinfo(
                "Scan Running Apps",
                "No importable running apps were detected with executable path and arguments.",
            )
            return

        self.set_status("Review running apps to import")
        ProcessScanDialog(self, process_entries)

    def collect_running_process_entries(self) -> list[dict]:
        entries: list[dict] = []
        seen_signatures: set[tuple[str, tuple[str, ...]]] = set()
        current_pid = os.getpid()
        visible_window_titles_by_pid = get_visible_window_titles_by_pid()

        for process in psutil.process_iter(["pid", "name", "exe", "cmdline", "username"]):
            try:
                process_info = process.info
                process_pid = process_info.get("pid")
                if process_pid == current_pid:
                    continue

                process_name = process_info.get("name") or ""
                executable_path = process_info.get("exe") or ""
                cmdline = process_info.get("cmdline") or []
                username = process_info.get("username") or ""

                if not executable_path and cmdline:
                    executable_path = str(cmdline[0])

                if not is_launchable_scan_path(executable_path):
                    continue

                args = [str(arg) for arg in cmdline[1:]] if len(cmdline) > 1 else []
                if should_exclude_scanned_process(process_name, executable_path):
                    continue

                window_titles = visible_window_titles_by_pid.get(process_pid or -1, [])
                classification = classify_scanned_process(
                    process_name,
                    executable_path,
                    args,
                    username,
                    bool(window_titles),
                )

                signature = process_signature(executable_path, args)
                if signature in seen_signatures:
                    continue

                seen_signatures.add(signature)
                entries.append(
                    {
                        "display_name": derive_import_step_name(process_name, executable_path),
                        "classification": classification,
                        "path": executable_path,
                        "args": args,
                        "signature": signature,
                        "window_titles": window_titles,
                        "has_visible_window": bool(window_titles),
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        entries = collapse_user_app_entries(entries)
        entries.sort(
            key=lambda entry: (
                0 if entry["classification"] == "user" else 1,
                0 if entry["has_visible_window"] else 1,
                entry["display_name"].lower(),
                entry["path"].lower(),
                entry["args"],
            )
        )
        return entries

    def import_scanned_processes(self, selected_entries: list[dict]) -> None:
        if not selected_entries:
            return
        if self.selected_mode_index is None:
            return

        mode = self.config_data["modes"][self.selected_mode_index]
        existing_signatures = {
            process_signature(step["path"], step["args"])
            for step in mode["steps"]
            if step.get("type") == "path"
        }

        imported_count = 0
        skipped_count = 0
        for entry in selected_entries:
            signature = process_signature(entry["path"], entry["args"])
            if signature in existing_signatures:
                skipped_count += 1
                self.logger.info(
                    "Skipped importing duplicate running app: %s (%s)",
                    entry["display_name"],
                    args_to_text(entry["args"]) or "no args",
                )
                continue

            mode["steps"].append(
                {
                    "name": entry["display_name"],
                    "type": "path",
                    "path": entry["path"],
                    "args": list(entry["args"]),
                    "delay_after": 0,
                    "enabled": True,
                    "readiness": make_default_readiness(),
                    "process_ready": make_default_process_ready(),
                    "window_snap": make_default_window_snap(),
                }
            )
            existing_signatures.add(signature)
            imported_count += 1
            self.logger.info(
                "Imported running app into mode '%s': %s",
                mode["name"],
                entry["display_name"],
            )

        if imported_count == 0:
            self.set_status("No new running apps imported")
            messagebox.showinfo(
                "Scan Running Apps",
                "No new steps were imported. Selected entries already exist in the current mode.",
            )
            return

        self.render_selected_mode()
        self.set_dirty(True)

        summary = f"Imported {imported_count} running app"
        if imported_count != 1:
            summary += "s"
        if skipped_count:
            summary += f". Skipped {skipped_count} duplicate"
            if skipped_count != 1:
                summary += "s"
        self.set_status(f"Imported {imported_count} running app{'s' if imported_count != 1 else ''}")
        messagebox.showinfo("Scan Running Apps", summary + ".")

    def process_log_queue(self) -> None:
        try:
            pending_messages: list[str] = []
            while True:
                message = self.log_queue.get_nowait()
                pending_messages.append(message)
        except Empty:
            if pending_messages:
                self.log_text.configure(state="normal")
                self.log_text.insert("end", "\n".join(pending_messages) + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        finally:
            if not self.is_shutting_down:
                try:
                    if self.winfo_exists():
                        self.after(UI_QUEUE_POLL_MS, self.process_log_queue)
                except TclError:
                    pass

    def process_status_queue(self) -> None:
        try:
            latest_status: str | None = None
            while True:
                latest_status = self.status_queue.get_nowait()
        except Empty:
            if latest_status is not None:
                self.set_status(latest_status)
        finally:
            if not self.is_shutting_down:
                try:
                    if self.winfo_exists():
                        self.after(UI_QUEUE_POLL_MS, self.process_status_queue)
                except TclError:
                    pass

    def sync_selected_mode_from_widgets(self, show_dialog: bool, reason: str = "manual") -> bool:
        started_at = time.perf_counter()
        result = False
        step_count = len(self.step_widgets)
        commit_requested = self.should_sync_editor_state()
        try:
            if self.selected_mode_index is None:
                result = True
                return True

            if self.pending_dirty_after_id is not None:
                try:
                    self.after_cancel(self.pending_dirty_after_id)
                except TclError:
                    pass
                self.pending_dirty_after_id = None

            mode = self.config_data["modes"][self.selected_mode_index]
            mode_name = self.mode_name_var.get().strip()
            if not mode_name:
                if show_dialog:
                    messagebox.showerror("Invalid Mode Name", "Mode name cannot be empty.")
                return False

            updated_steps = []
            for index, widget in enumerate(self.step_widgets, start=1):
                step_name = widget["name_var"].get().strip()
                step_type = widget["type_var"].get().strip()
                path = widget["path_var"].get().strip()
                args_text = widget["args_var"].get()
                delay_text = widget["delay_var"].get()
                enabled = bool(widget["enabled_var"].get())
                readiness_type = widget["readiness_type_var"].get().strip()
                readiness_target = widget["readiness_target_var"].get().strip()
                readiness_timeout_text = widget["readiness_timeout_var"].get().strip()
                process_ready_enabled = bool(widget["process_ready_enabled_var"].get())
                process_ready_name = widget["process_ready_name_var"].get().strip()
                process_ready_timeout_text = widget["process_ready_timeout_var"].get().strip()
                process_settle_delay_text = widget["process_settle_delay_var"].get().strip()
                if step_type != "path":
                    process_ready_enabled = False
                    widget["process_ready_enabled_var"].set(False)
                snap_enabled = bool(widget["snap_enabled_var"].get())
                snap_match_mode = widget["snap_match_mode_var"].get().strip()
                snap_match_value = widget["snap_match_value_var"].get().strip()
                snap_x_text = widget["snap_x_var"].get().strip()
                snap_y_text = widget["snap_y_var"].get().strip()
                snap_width_text = widget["snap_width_var"].get().strip()
                snap_height_text = widget["snap_height_var"].get().strip()
                snap_timeout_text = widget["snap_timeout_var"].get().strip()

                if not step_name:
                    if show_dialog:
                        messagebox.showerror(
                            "Invalid Step Name", f"Step {index} must have a non-empty name."
                        )
                    return False

                if step_type not in STEP_TYPES:
                    if show_dialog:
                        messagebox.showerror(
                            "Invalid Step Type", f"Step '{step_name}' has an unsupported type."
                        )
                    return False
                if readiness_type not in READINESS_TYPES:
                    if show_dialog:
                        messagebox.showerror(
                            "Invalid Readiness Type",
                            f"Step '{step_name}' has an unsupported readiness type.",
                        )
                    return False
                if snap_match_mode not in WINDOW_MATCH_MODES:
                    if show_dialog:
                        messagebox.showerror(
                            "Invalid Window Match Mode",
                            f"Step '{step_name}' has an unsupported window match mode.",
                        )
                    return False

                try:
                    parsed_args = parse_args_text(args_text)
                except ValueError as exc:
                    self.logger.error("Invalid args for step '%s': %s", step_name, exc)
                    if show_dialog:
                        messagebox.showerror(
                            "Invalid Args",
                            (
                                f"Step '{step_name}' has invalid arguments.\n\n"
                                f"Input:\n{args_text or '(empty)'}\n\n"
                                f"Problem: {exc}\n\n"
                                'Use balanced quotes for values with spaces.\n'
                                'Example: --profile-directory="Profile 1"'
                            ),
                        )
                    return False

                normalized_delay = self.normalize_delay(delay_text, step_name)
                widget["delay_var"].set(str(normalized_delay))
                normalized_readiness_timeout = self.normalize_timeout(
                    readiness_timeout_text,
                    f"{step_name} readiness",
                )
                widget["readiness_timeout_var"].set(str(normalized_readiness_timeout))
                if process_ready_enabled and not process_ready_name:
                    process_ready_name = derive_default_process_ready_name(step_type, path)
                normalized_process_ready_timeout = self.normalize_positive_int(
                    process_ready_timeout_text,
                    DEFAULT_PROCESS_READY_TIMEOUT_SECONDS,
                    f"{step_name} process readiness timeout",
                )
                normalized_process_settle_delay = self.normalize_non_negative_int(
                    process_settle_delay_text,
                    0,
                    f"{step_name} process settle delay",
                )
                widget["process_ready_name_var"].set(process_ready_name)
                widget["process_ready_timeout_var"].set(str(normalized_process_ready_timeout))
                widget["process_settle_delay_var"].set(str(normalized_process_settle_delay))
                normalized_snap_x = self.normalize_signed_int(snap_x_text, 0)
                normalized_snap_y = self.normalize_signed_int(snap_y_text, 0)
                normalized_snap_width = self.normalize_positive_int(
                    snap_width_text,
                    1280,
                    f"{step_name} snap width",
                )
                normalized_snap_height = self.normalize_positive_int(
                    snap_height_text,
                    720,
                    f"{step_name} snap height",
                )
                normalized_snap_timeout = self.normalize_positive_int(
                    snap_timeout_text,
                    DEFAULT_WINDOW_SNAP_TIMEOUT_SECONDS,
                    f"{step_name} snap timeout",
                )
                widget["snap_x_var"].set(str(normalized_snap_x))
                widget["snap_y_var"].set(str(normalized_snap_y))
                widget["snap_width_var"].set(str(normalized_snap_width))
                widget["snap_height_var"].set(str(normalized_snap_height))
                widget["snap_timeout_var"].set(str(normalized_snap_timeout))

                if readiness_type == "port":
                    try:
                        parse_host_port_target(readiness_target)
                    except ValueError as exc:
                        if show_dialog:
                            messagebox.showerror(
                                "Invalid Port Readiness",
                                f"Step '{step_name}' has an invalid port readiness target.\n\n{exc}",
                            )
                        return False
                elif readiness_type == "url":
                    if not readiness_target.startswith(("http://", "https://")):
                        if show_dialog:
                            messagebox.showerror(
                                "Invalid URL Readiness",
                                (
                                    f"Step '{step_name}' must use a readiness URL starting with "
                                    "http:// or https://."
                                ),
                            )
                        return False
                if process_ready_enabled:
                    if step_type != "path":
                        if show_dialog:
                            messagebox.showerror(
                                "Invalid Process Readiness",
                                f"Step '{step_name}' can only use process readiness with path steps.",
                            )
                        return False
                    if not process_ready_name:
                        if show_dialog:
                            messagebox.showerror(
                                "Invalid Process Readiness",
                                f"Step '{step_name}' must define a process name for tray/background readiness.",
                            )
                        return False
                if snap_enabled and snap_match_mode != "none" and not snap_match_value:
                    if show_dialog:
                        messagebox.showerror(
                            "Invalid Window Match Value",
                            f"Step '{step_name}' must define a window match value when snapping is enabled.",
                        )
                    return False

                updated_steps.append(
                    {
                        "name": step_name,
                        "type": step_type,
                        "path": path,
                        "args": parsed_args,
                        "delay_after": normalized_delay,
                        "enabled": enabled,
                        "readiness": {
                            "type": readiness_type,
                            "target": readiness_target if readiness_type != "none" else "",
                            "timeout_seconds": normalized_readiness_timeout,
                        },
                        "process_ready": {
                            "enabled": process_ready_enabled,
                            "name": process_ready_name if process_ready_enabled else "",
                            "timeout_seconds": normalized_process_ready_timeout,
                            "settle_delay_seconds": normalized_process_settle_delay,
                        },
                        "window_snap": {
                            "snap_enabled": snap_enabled,
                            "window_match_mode": snap_match_mode,
                            "window_match_value": snap_match_value
                            if snap_enabled and snap_match_mode != "none"
                            else "",
                            "snap_x": normalized_snap_x,
                            "snap_y": normalized_snap_y,
                            "snap_width": normalized_snap_width,
                            "snap_height": normalized_snap_height,
                            "snap_timeout_sec": normalized_snap_timeout,
                        },
                    }
                )

            mode["name"] = mode_name
            mode["steps"] = updated_steps
            self.config_data["auto_start_on_launch"] = bool(self.auto_start_var.get())
            self.config_data["selected_mode_id"] = mode["id"]
            if self.selected_mode_index < len(self.mode_buttons):
                self.mode_buttons[self.selected_mode_index].configure(text=mode_name)
            if commit_requested:
                self.is_dirty = True
            self.editor_dirty = False
            result = True
            return True
        finally:
            self.log_perf(
                "sync_selected_mode_from_widgets",
                started_at,
                f"reason={reason} steps={step_count} result={'ok' if result else 'blocked'}",
            )

    def normalize_delay(self, raw_value: str, step_name: str) -> int:
        text = str(raw_value).strip()
        if not text:
            self.logger.warning("Normalized delay for step '%s' to 0", step_name)
            return 0

        try:
            value = int(text)
        except ValueError:
            self.logger.warning("Normalized delay for step '%s' to 0", step_name)
            return 0

        if value < 0:
            self.logger.warning("Normalized delay for step '%s' to 0", step_name)
            return 0

        return value

    def normalize_timeout(self, raw_value: str, label: str) -> int:
        text = str(raw_value).strip()
        if not text:
            self.logger.warning("Normalized timeout for %s to %s", label, DEFAULT_READINESS_TIMEOUT_SECONDS)
            return DEFAULT_READINESS_TIMEOUT_SECONDS

        try:
            value = int(text)
        except ValueError:
            self.logger.warning("Normalized timeout for %s to %s", label, DEFAULT_READINESS_TIMEOUT_SECONDS)
            return DEFAULT_READINESS_TIMEOUT_SECONDS

        if value <= 0:
            self.logger.warning("Normalized timeout for %s to %s", label, DEFAULT_READINESS_TIMEOUT_SECONDS)
            return DEFAULT_READINESS_TIMEOUT_SECONDS

        return value

    def normalize_positive_int(self, raw_value: str, fallback: int, label: str) -> int:
        text = str(raw_value).strip()
        if not text:
            self.logger.warning("Normalized %s to %s", label, fallback)
            return fallback

        try:
            value = int(text)
        except ValueError:
            self.logger.warning("Normalized %s to %s", label, fallback)
            return fallback

        if value <= 0:
            self.logger.warning("Normalized %s to %s", label, fallback)
            return fallback

        return value

    def normalize_non_negative_int(self, raw_value: str, fallback: int, label: str) -> int:
        text = str(raw_value).strip()
        if not text:
            self.logger.warning("Normalized %s to %s", label, fallback)
            return fallback

        try:
            value = int(text)
        except ValueError:
            self.logger.warning("Normalized %s to %s", label, fallback)
            return fallback

        if value < 0:
            self.logger.warning("Normalized %s to %s", label, fallback)
            return fallback

        return value

    def normalize_signed_int(self, raw_value: str, fallback: int) -> int:
        text = str(raw_value).strip()
        if not text:
            return fallback

        try:
            return int(text)
        except ValueError:
            return fallback

    def save_config(self) -> bool:
        if not self.config_valid:
            return False
        if not self.sync_selected_mode_from_widgets(show_dialog=True, reason="save_config"):
            return False

        try:
            validated_payload = validate_config(copy.deepcopy(self.config_data))
            write_config_atomic(validated_payload)
        except ConfigError as exc:
            self.logger.error("Config validation failed during save: %s", exc)
            messagebox.showerror("Save Failed", f"Config validation failed.\n\n{exc}")
            return False
        except OSError as exc:
            self.logger.error("Config write failed: %s", exc)
            messagebox.showerror("Save Failed", f"Could not write config.\n\n{exc}")
            return False

        self.config_data = validated_payload
        self.set_dirty(False)
        self.logger.info("Saved config to %s", CONFIG_PATH)
        self.set_status("Config saved")
        return True

    def run_selected_mode(self) -> None:
        if not self.config_valid or self.is_running or self.selected_mode_index is None:
            return
        if not self.sync_selected_mode_if_needed(show_dialog=True, reason="run_selected_mode"):
            return

        mode_snapshot = copy.deepcopy(self.config_data["modes"][self.selected_mode_index])
        self.stop_event.clear()
        self.set_run_state(True)
        self.set_status(f"Running mode: {mode_snapshot['name']}")

        self.run_thread = threading.Thread(
            target=self._run_mode_worker, args=(mode_snapshot,), daemon=True
        )
        self.run_thread.start()

    def stop_sequence(self) -> None:
        if not self.is_running:
            return
        self.stop_event.set()
        self.logger.warning("Stop requested for the active boot sequence.")
        self.set_status("Stop requested...")

    def _run_mode_worker(self, mode: dict) -> None:
        try:
            self.logger.info("Starting mode: %s", mode["name"])
            self.enqueue_status(f"Starting mode: {mode['name']}")
            stop_requested = False

            for step in mode["steps"]:
                if self.stop_event.is_set():
                    self.logger.warning("Stopped before step '%s' could start.", step["name"])
                    self.enqueue_status(f"Stopped before step: {step['name']}")
                    stop_requested = True
                    break

                if not step["enabled"]:
                    self.logger.info("Skipped disabled step: %s", step["name"])
                    continue

                launch_result = self.launch_step(step)
                if not launch_result["launched"]:
                    continue

                process_ready_succeeded = self.wait_for_step_process_ready(step, launch_result)
                if not process_ready_succeeded and self.stop_event.is_set():
                    stop_requested = True
                    break

                self.wait_for_window_snap(step, launch_result)

                readiness_succeeded = self.wait_for_step_readiness(step)
                if not readiness_succeeded and self.stop_event.is_set():
                    stop_requested = True
                    break

                delay_after = step["delay_after"]
                if delay_after <= 0:
                    continue

                self.logger.info("Waiting %s seconds after step: %s", delay_after, step["name"])
                for remaining in range(delay_after, 0, -1):
                    self.enqueue_status(f"Waiting: {remaining}s after {step['name']}")
                    if self.stop_event.is_set():
                        self.logger.warning(
                            "Stop detected during delay countdown after step '%s'.", step["name"]
                        )
                        self.enqueue_status(f"Stop detected during wait after {step['name']}")
                        stop_requested = True
                        break
                    time.sleep(1)

                if stop_requested:
                    break

            if stop_requested:
                self.logger.warning("Boot sequence stopped before completion.")
                self.enqueue_status("Stopped")
            else:
                self.logger.info("Boot sequence complete.")
                self.enqueue_status("Boot sequence complete")
        except Exception as exc:
            self.logger.exception("Unhandled error while running boot mode: %s", exc)
            self.enqueue_status("Run failed")
        finally:
            if not self.is_shutting_down:
                try:
                    if self.winfo_exists():
                        self.after(
                            0,
                            lambda: self.set_run_state(False),
                        )
                except TclError:
                    pass

    def wait_for_step_readiness(self, step: dict) -> bool:
        readiness = normalize_readiness_config(step.get("readiness"))
        readiness_type = readiness["type"]
        if readiness_type == "none":
            return True

        target = readiness["target"]
        timeout_seconds = readiness["timeout_seconds"]
        if not target:
            self.logger.warning(
                "Readiness for step '%s' is enabled but has no target. Skipping readiness wait.",
                step["name"],
            )
            return True

        self.logger.info(
            "Waiting for %s readiness for step '%s': %s (timeout: %ss)",
            readiness_type,
            step["name"],
            target,
            timeout_seconds,
        )
        start_time = time.perf_counter()
        next_log_elapsed = 0

        while True:
            if self.stop_event.is_set():
                self.logger.warning(
                    "Stop detected while waiting for readiness on step '%s'.",
                    step["name"],
                )
                self.enqueue_status(f"Stopped during readiness wait: {step['name']}")
                return False

            ready = False
            if readiness_type == "port":
                ready = self.check_port_readiness(target)
            elif readiness_type == "url":
                ready = self.check_url_readiness(target)

            if ready:
                elapsed = int(time.perf_counter() - start_time)
                self.logger.info(
                    "Readiness check passed for step '%s' after %ss.",
                    step["name"],
                    elapsed,
                )
                self.enqueue_status(f"Ready: {step['name']}")
                return True

            elapsed_seconds = time.perf_counter() - start_time
            if elapsed_seconds >= timeout_seconds:
                self.logger.warning(
                    "Readiness timeout for step '%s' after %ss (%s: %s). Continuing.",
                    step["name"],
                    timeout_seconds,
                    readiness_type,
                    target,
                )
                self.enqueue_status(f"Readiness timeout: {step['name']}")
                return False

            elapsed_int = int(elapsed_seconds)
            remaining = max(0, timeout_seconds - elapsed_int)
            self.enqueue_status(
                f"Waiting for {readiness_type}: {step['name']} ({remaining}s left)"
            )
            if elapsed_int >= next_log_elapsed:
                self.logger.info(
                    "Still waiting for %s readiness for step '%s' (%ss elapsed, target: %s)",
                    readiness_type,
                    step["name"],
                    elapsed_int,
                    target,
                )
                next_log_elapsed = elapsed_int + 5

            time.sleep(READINESS_POLL_INTERVAL_SECONDS)

    def wait_for_step_process_ready(self, step: dict, launch_result: dict) -> bool:
        process_ready = normalize_process_ready_config(
            step.get("process_ready"),
            step.get("type", "path"),
            step.get("path", ""),
        )
        if not process_ready["enabled"]:
            return True

        target_name = str(process_ready["name"]).strip()
        if not target_name:
            self.logger.warning(
                "Process readiness for step '%s' is enabled but has no process name. Skipping wait.",
                step["name"],
            )
            return True

        timeout_seconds = int(process_ready["timeout_seconds"])
        settle_delay_seconds = int(process_ready["settle_delay_seconds"])
        launched_pid = launch_result.get("pid")
        normalized_target_basename = Path(target_name).name.lower()
        normalized_target_stem = Path(normalized_target_basename).stem.lower()

        self.logger.info(
            "Waiting for process readiness for step '%s': %s (timeout: %ss, settle: %ss)",
            step["name"],
            target_name,
            timeout_seconds,
            settle_delay_seconds,
        )
        self.enqueue_status(f"Waiting for process: {step['name']}")

        started_at = time.perf_counter()
        next_log_elapsed = 0
        matched_process: dict | None = None
        while True:
            if self.stop_event.is_set():
                self.logger.warning(
                    "Stop detected while waiting for process readiness on step '%s'.",
                    step["name"],
                )
                self.enqueue_status(f"Stopped during process wait: {step['name']}")
                return False

            matched_process = self.find_running_process_by_name(
                normalized_target_basename,
                normalized_target_stem,
                launched_pid,
            )
            if matched_process is not None:
                self.logger.info(
                    "Process readiness passed for step '%s': %s (pid %s).",
                    step["name"],
                    matched_process["name"],
                    matched_process["pid"],
                )
                if settle_delay_seconds <= 0:
                    self.enqueue_status(f"Process ready: {step['name']}")
                    return True

                self.logger.info(
                    "Settling process for step '%s' for %ss before continuing.",
                    step["name"],
                    settle_delay_seconds,
                )
                for remaining in range(settle_delay_seconds, 0, -1):
                    if self.stop_event.is_set():
                        self.logger.warning(
                            "Stop detected during process settle delay for step '%s'.",
                            step["name"],
                        )
                        self.enqueue_status(f"Stopped during settle: {step['name']}")
                        return False
                    self.enqueue_status(
                        f"Settling process: {step['name']} ({remaining}s left)"
                    )
                    time.sleep(1)

                self.enqueue_status(f"Process ready: {step['name']}")
                return True

            elapsed_seconds = time.perf_counter() - started_at
            if elapsed_seconds >= timeout_seconds:
                self.logger.warning(
                    "Process readiness timeout for step '%s' after %ss while waiting for %s. Continuing.",
                    step["name"],
                    timeout_seconds,
                    target_name,
                )
                self.enqueue_status(f"Process wait timeout: {step['name']}")
                return False

            elapsed_int = int(elapsed_seconds)
            remaining = max(0, timeout_seconds - elapsed_int)
            self.enqueue_status(
                f"Waiting for process: {step['name']} ({remaining}s left)"
            )
            if elapsed_int >= next_log_elapsed:
                self.logger.info(
                    "Still waiting for process readiness for step '%s' (%ss elapsed, target: %s)",
                    step["name"],
                    elapsed_int,
                    target_name,
                )
                next_log_elapsed = elapsed_int + 3

            time.sleep(WINDOW_SNAP_POLL_INTERVAL_SECONDS)

    def find_running_process_by_name(
        self,
        target_basename: str,
        target_stem: str,
        launched_pid: int | None,
    ) -> dict | None:
        matches: list[dict] = []
        for process in psutil.process_iter(["pid", "name", "exe"]):
            try:
                process_info = process.info
                process_name = str(process_info.get("name") or "").strip()
                process_exe = str(process_info.get("exe") or "").strip()
                if not process_name and process_exe:
                    process_name = Path(process_exe).name
                if not process_name:
                    continue

                process_basename = Path(process_name).name.lower()
                process_stem = Path(process_basename).stem.lower()
                if process_basename != target_basename and process_stem != target_stem:
                    continue

                matches.append(
                    {
                        "pid": int(process_info.get("pid") or 0),
                        "name": process_name,
                        "exe": process_exe,
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if not matches:
            return None

        matches.sort(
            key=lambda process_info: (
                0 if launched_pid and process_info["pid"] == launched_pid else 1,
                process_info["name"].lower(),
                process_info["pid"],
            )
        )
        return matches[0]

    def check_port_readiness(self, target: str) -> bool:
        try:
            host, port = parse_host_port_target(target)
        except ValueError:
            return False

        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            return False

    def check_url_readiness(self, target: str) -> bool:
        request = urllib_request.Request(target, method="GET")
        try:
            with urllib_request.urlopen(request, timeout=2.0) as response:
                status_code = getattr(response, "status", response.getcode())
                return 200 <= int(status_code) < 400
        except urllib_error.HTTPError as exc:
            return 200 <= int(exc.code) < 400
        except (urllib_error.URLError, ValueError, OSError):
            return False

    def wait_for_window_snap(self, step: dict, launch_result: dict) -> bool:
        window_snap = normalize_window_snap_config(step.get("window_snap"))
        if not window_snap["snap_enabled"] or window_snap["window_match_mode"] == "none":
            return True

        timeout_seconds = window_snap["snap_timeout_sec"]
        self.logger.info(
            "Waiting to snap window for step '%s' using %s '%s' (timeout: %ss)",
            step["name"],
            window_snap["window_match_mode"],
            window_snap["window_match_value"],
            timeout_seconds,
        )
        self.enqueue_status(f"Waiting for window: {step['name']}")

        started_at = time.perf_counter()
        next_log_elapsed = 0
        while True:
            if self.stop_event.is_set():
                self.logger.warning(
                    "Stop detected while waiting to snap window for step '%s'.",
                    step["name"],
                )
                return False

            window_candidates = self.find_matching_windows(
                window_snap,
                launch_result.get("pid"),
            )
            if window_candidates:
                selected_window = window_candidates[0]
                if len(window_candidates) > 1:
                    self.logger.info(
                        "Multiple windows matched for step '%s'. Using '%s' (pid %s).",
                        step["name"],
                        selected_window["title"],
                        selected_window["pid"],
                    )
                snap_success = self.apply_window_snap(selected_window["hwnd"], window_snap)
                if snap_success:
                    self.logger.info(
                        "Snapped window for step '%s' to x=%s y=%s w=%s h=%s.",
                        step["name"],
                        window_snap["snap_x"],
                        window_snap["snap_y"],
                        window_snap["snap_width"],
                        window_snap["snap_height"],
                    )
                    self.enqueue_status(f"Snapped window: {step['name']}")
                    return True

                self.logger.error("Failed to snap window for step '%s'.", step["name"])
                return False

            elapsed_seconds = time.perf_counter() - started_at
            if elapsed_seconds >= timeout_seconds:
                self.logger.warning(
                    "Window snap timeout for step '%s' after %ss.",
                    step["name"],
                    timeout_seconds,
                )
                self.enqueue_status(f"Window snap timeout: {step['name']}")
                return False

            elapsed_int = int(elapsed_seconds)
            remaining = max(0, timeout_seconds - elapsed_int)
            self.enqueue_status(f"Waiting for window: {step['name']} ({remaining}s left)")
            if elapsed_int >= next_log_elapsed:
                self.logger.info(
                    "Still waiting to snap window for step '%s' (%ss elapsed, mode=%s, value=%s)",
                    step["name"],
                    elapsed_int,
                    window_snap["window_match_mode"],
                    window_snap["window_match_value"],
                )
                next_log_elapsed = elapsed_int + 3

            time.sleep(WINDOW_SNAP_POLL_INTERVAL_SECONDS)

    def find_matching_windows(self, window_snap: dict, launched_pid: int | None) -> list[dict]:
        windows = enumerate_visible_top_level_windows()
        match_mode = window_snap["window_match_mode"]
        match_value = window_snap["window_match_value"].strip().lower()
        if not match_value or match_mode == "none":
            return []

        matches = []
        for window in windows:
            title = str(window["title"]).lower()
            process_name = str(window["process_name"]).lower()
            matches_window = False

            if match_mode == "title_contains":
                matches_window = match_value in title
            elif match_mode == "process_name":
                process_basename = Path(process_name).name.lower()
                process_stem = Path(process_basename).stem.lower()
                value_stem = Path(match_value).stem.lower()
                matches_window = process_basename == match_value or process_stem == value_stem

            if matches_window:
                rect_info = get_window_rect_info(window["hwnd"])
                area = 0
                if rect_info is not None:
                    area = int(rect_info["width"]) * int(rect_info["height"])
                    window = {**window, **rect_info}
                else:
                    window = {**window}
                window["area"] = area
                matches.append(window)

        return sorted(
            matches,
            key=lambda window: (
                0 if launched_pid and window["pid"] == launched_pid else 1,
                0 if window.get("is_foreground") else 1,
                0 if not window["is_minimized"] else 1,
                -int(window.get("area", 0)),
                -len(str(window["title"])),
                str(window["title"]).lower(),
            ),
        )

    def apply_window_snap(self, hwnd: int, window_snap: dict) -> bool:
        if os.name != "nt":
            return False

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        show_window = user32.ShowWindow
        show_window.argtypes = [wintypes.HWND, ctypes.c_int]
        show_window.restype = wintypes.BOOL

        move_window = user32.MoveWindow
        move_window.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.BOOL,
        ]
        move_window.restype = wintypes.BOOL

        sw_restore = 9
        show_window(hwnd, sw_restore)
        return bool(
            move_window(
                hwnd,
                int(window_snap["snap_x"]),
                int(window_snap["snap_y"]),
                int(window_snap["snap_width"]),
                int(window_snap["snap_height"]),
                True,
            )
        )

    def capture_current_window_for_step(
        self,
        step_name: str,
        step_type: str,
        path_var: ctk.StringVar,
        snap_enabled_var: ctk.BooleanVar,
        snap_match_mode_var: ctk.StringVar,
        snap_match_value_var: ctk.StringVar,
        snap_x_var: ctk.StringVar,
        snap_y_var: ctk.StringVar,
        snap_width_var: ctk.StringVar,
        snap_height_var: ctk.StringVar,
    ) -> None:
        current_mode = snap_match_mode_var.get().strip()
        current_value = snap_match_value_var.get().strip()
        derived_match = False

        if current_mode in WINDOW_MATCH_MODES and current_mode != "none" and current_value:
            window_snap = {
                "snap_enabled": True,
                "window_match_mode": current_mode,
                "window_match_value": current_value,
            }
        else:
            derived_mode = "none"
            derived_value = ""
            if step_type == "path":
                expanded_path = os.path.expandvars(path_var.get().strip())
                if expanded_path:
                    derived_value = Path(expanded_path).name.strip()
                    if derived_value:
                        derived_mode = "process_name"
            if derived_mode == "none" and step_name.strip():
                derived_mode = "title_contains"
                derived_value = step_name.strip()

            if derived_mode == "none" or not derived_value:
                messagebox.showinfo(
                    "Capture Current Window",
                    (
                        "No window match rule is configured for this step yet.\n\n"
                        "Set a snap match mode and value first, or use a path step so the app can infer the process name."
                    ),
                )
                return

            window_snap = {
                "snap_enabled": True,
                "window_match_mode": derived_mode,
                "window_match_value": derived_value,
            }
            derived_match = True

        window_candidates = self.find_matching_windows(window_snap, launched_pid=None)
        if not window_candidates:
            self.logger.info(
                "Capture current window found no matching top-level window for step '%s' using %s '%s'.",
                step_name,
                window_snap["window_match_mode"],
                window_snap["window_match_value"],
            )
            messagebox.showinfo(
                "Capture Current Window",
                (
                    f"No matching running top-level window was found for step '{step_name}'.\n\n"
                    "Open the app window first, or adjust the snap match mode/value."
                ),
            )
            return

        selected_window = window_candidates[0]
        if len(window_candidates) > 1:
            self.logger.info(
                "Capture current window matched %s windows for step '%s'. Using '%s' (pid %s).",
                len(window_candidates),
                step_name,
                selected_window["title"],
                selected_window["pid"],
            )

        rect_info = get_window_rect_info(selected_window["hwnd"])
        if rect_info is None:
            messagebox.showerror(
                "Capture Current Window",
                f"Could not read the current window bounds for step '{step_name}'.",
            )
            return

        snap_enabled_var.set(True)
        snap_x_var.set(str(rect_info["x"]))
        snap_y_var.set(str(rect_info["y"]))
        snap_width_var.set(str(rect_info["width"]))
        snap_height_var.set(str(rect_info["height"]))
        if derived_match or snap_match_mode_var.get() == "none" or not snap_match_value_var.get().strip():
            snap_match_mode_var.set(str(window_snap["window_match_mode"]))
            snap_match_value_var.set(str(window_snap["window_match_value"]))

        self.set_dirty(True)
        self.editor_dirty = True

        monitor_suffix = (
            f" on {rect_info['monitor_name']}" if rect_info.get("monitor_name") else ""
        )
        self.logger.info(
            "Captured window bounds for step '%s' from '%s' [%s]%s: x=%s y=%s w=%s h=%s.",
            step_name,
            selected_window["title"],
            selected_window["process_name"],
            monitor_suffix,
            rect_info["x"],
            rect_info["y"],
            rect_info["width"],
            rect_info["height"],
        )
        self.set_status(f"Captured window: {step_name}")

    def launch_step(self, step: dict) -> dict:
        name = step["name"]
        step_type = step["type"]
        path = step["path"]
        args = step["args"]
        launch_result = {"launched": False, "pid": None}

        self.logger.info("Starting step: %s", name)
        self.enqueue_status(f"Starting step: {name}")

        if step_type == "url":
            try:
                opened = webbrowser.open(path)
            except Exception as exc:
                self.logger.error("Failed to launch %s: %s", name, exc)
                return launch_result

            if not opened:
                self.logger.error("Failed to launch %s: browser refused URL %s", name, path)
                return launch_result
            launch_result["launched"] = True
            return launch_result

        expanded_path = os.path.expandvars(path)
        if not expanded_path or not Path(expanded_path).exists():
            self.logger.error("Failed to launch %s: path not found (%s)", name, path)
            return launch_result

        running_signature = process_signature(expanded_path, args)
        if running_signature in collect_running_process_signatures():
            self.logger.info("Skipped step '%s': already running", name)
            self.enqueue_status(f"Skipped step: {name} (already running)")
            return launch_result

        suffix = Path(expanded_path).suffix.lower()
        command = [expanded_path, *args]
        if suffix in {".bat", ".cmd"}:
            command = ["cmd.exe", "/c", expanded_path, *args]

        try:
            process = subprocess.Popen(command)
        except Exception as exc:
            self.logger.error("Failed to launch %s: %s", name, exc)
            return launch_result

        launch_result["launched"] = True
        launch_result["pid"] = process.pid
        return launch_result

    def on_close(self) -> None:
        if self.is_running:
            should_close = messagebox.askokcancel(
                "Sequence Running",
                (
                    "A startup sequence is still running.\n\n"
                    "Closing now will stop the sequence and exit the app.\n\n"
                    "Do you want to continue?"
                ),
            )
            if not should_close:
                return

        if self.is_dirty:
            save_choice = messagebox.askyesnocancel(
                "Unsaved Changes",
                (
                    "You have unsaved changes.\n\n"
                    "Yes: Save changes before closing\n"
                    "No: Discard changes and close\n"
                    "Cancel: Keep the app open"
                ),
            )
            if save_choice is None:
                return
            if save_choice:
                if not self.save_config():
                    return
            else:
                self.set_dirty(False)

        self.is_shutting_down = True
        self.stop_event.set()
        self.destroy()


def main() -> None:
    app = BootManagerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
