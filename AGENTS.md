# AGENTS.md

## Project Rules

This repository is a public project. Do NOT introduce sensitive or machine-specific data.

### 🚫 Forbidden
- Do NOT use or copy values from config/boot_modes.json
- Do NOT include absolute local paths (e.g., C:\Users\..., C:\AI-Projects\...)
- Do NOT include usernames or personal folder names
- Do NOT include API keys, tokens, or secrets
- Do NOT modify files unrelated to the task

### ✅ Allowed
- Use config/boot_modes.example.json as the public template
- Use generic paths like:
  - C:/Program Files/App/app.exe
  - C:/Path/To/Your/App.exe
- Keep all changes portable and system-agnostic

### 📌 File Rules
- config/boot_modes.json is local-only and must never be committed
- config/boot_modes.example.json is the only public config file

### ⚠️ Behavior
- If a task requires private/local data → STOP and ask instead of guessing
- Do not update README.md unless explicitly requested
- Do not add new files unless necessary

### 🧪 Commit Rules
- Make small, focused commits
- Use clear commit messages
- Avoid unrelated changes