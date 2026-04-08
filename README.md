# CopilotBridge

**通过飞书远程控制本地电脑上运行的 GitHub Copilot CLI**

本项目的核心定位：在本地电脑上运行一个飞书机器人，让你可以在任何地方通过飞书私信向本地电脑下发指令，由本地的 GitHub Copilot CLI（或 PowerShell）来执行，并将结果返回到飞书。

> **Use case**: You are away from your desk. You open Feishu on your phone, send a message to this bot, and it executes the command on your local machine – powered by GitHub Copilot CLI – and replies with the result.

---

A local Python Feishu private-chat bot that:

- bridges **Feishu** and **GitHub Copilot CLI** running on your local machine
- receives instructions from Feishu private chat over a long connection (no public IP required)
- routes natural-language requests to local `copilot` for intent resolution and execution
- executes PowerShell commands directly when prefixed with `!`
- sends back command output, files, and screenshots through Feishu
- runs as a Windows tray app by default, with quick model switching from the tray icon

## What this version supports

- Feishu private chat bot
- `im.message.receive_v1`
- Feishu long connection / WebSocket event receiving
- plain text replies
- natural-language command routing via local GitHub Copilot CLI
- direct PowerShell execution (`!` prefix)
- file upload and send-back via Feishu
- optional AI replies when `OPENAI_API_KEY` is configured
- tray-first Windows runtime with persistent Copilot model switching

## What this version does not support yet

- group-chat bot behavior
- rich-card replies
- file/image message parsing

## Project structure

```text
feishu-bot/
  app/
    __init__.py
    bot.py
    copilot_runtime.py
    config.py
    executor.py
    feishu_api.py
    responder.py
    tray.py
  tests/
    __init__.py
    test_bot.py
    test_copilot_runtime.py
  .env.example
  build.ps1
  main.py
  requirements.txt
  run.ps1
```

## Local setup

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Create your local config

```powershell
Copy-Item .env.example .env
```

Then edit `.env` and fill:

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_VERIFY_TOKEN`

If you launch the packaged EXE directly, put the `.env` file next to the EXE or keep it in the project root and start it through `run.ps1`.

If you want AI replies, also fill:

- `OPENAI_API_KEY`
- optionally `OPENAI_BASE_URL`
- optionally `OPENAI_MODEL`

Optionally, configure execution paths:

- `WORK_DIR` – working directory for command execution (default: user home directory)
- `ARTIFACT_DIR` – directory used for screenshots captured by the bot (default: `~/.feishu-bot/artifacts`); other generated files are not automatically stored there
- `COPILOT_MODEL` – model used for local Copilot CLI execution (default: `gpt-5.4`)
- `COPILOT_CLI_PATH` – explicit path to `copilot.exe` if it is not on `PATH`
- `TRAY_ICON_PATH` – optional custom `.ico` path for the tray icon; if empty, the app will auto-detect `favicon.ico` / `favicon (1).ico` in the project root

## Run locally

```powershell
.\run.ps1
```

Or:

```powershell
python main.py
```

The app now starts as a **tray-first background program**. When the packaged EXE runs, it stays in the Windows notification area instead of opening a console window.

## Build a Windows EXE

```powershell
.\build.ps1
```

Or use your own `.ico` during packaging:

```powershell
.\build.ps1 -IconPath C:\path\to\custom.ico
```

After the build finishes, the packaged executable will be in:

```powershell
.\dist\CopilotBridge.exe
```

You can then launch the bot with:

```powershell
.\run.ps1
```

If the EXE exists, `run.ps1` will start it directly in the background; otherwise it falls back to the virtualenv + `main.py` path.

The packaged app writes startup logs to:

```powershell
.\dist\logs\CopilotBridge.log
```

If the EXE seems to flash and disappear, check that log file first. It now records tray startup, chosen icon file, Copilot CLI readiness, and bot startup status.

## What you need to do in Feishu

### 1. Create an enterprise internal app

In Feishu Open Platform:

- create a new app
- choose an internal/self-use style app appropriate for your tenant
- enable the bot capability

### 2. Configure permissions

Grant the message send capability required for bot replies.

If Feishu asks for specific IM permissions, approve the ones needed for bot message sending and message events.

### 3. Configure event subscription

Use **长连接 / Long Connection** mode.

Add the event:

```text
im.message.receive_v1
```

Set the verification token to match `FEISHU_VERIFY_TOKEN` in `.env`.

### 4. Publish the app version

After changing permissions or events in Feishu, publish the app version so the bot can receive real traffic.

### 5. Open a private chat with the bot

Once the app is available in your tenant, start a private chat with the bot and send:

```text
/help
```

or:

```text
ping
```

## Bot behavior

Without AI credentials:

- `/help` shows help
- `ping` returns `pong`
- natural-language requests are routed to local `copilot`
- messages starting with `!` execute local PowerShell directly

With AI credentials configured:

- all normal private text messages are forwarded to the configured OpenAI-compatible chat API

## Execution behavior

This bot now runs in autonomous local execution mode with a Windows tray controller.

- `/help` and `ping` are handled as built-in bot commands
- messages starting with `!` are executed directly as PowerShell on this Windows machine
- broad natural-language requests are sent to local `copilot` for intent understanding and single-action execution
- the tray icon checks `copilot.exe` at startup and keeps the currently selected Copilot model
- right-click the tray icon to switch Copilot models, and the selection is persisted back to `.env`
- installed skills can be triggered from natural language, for example `填写周报`
- local files can be uploaded and sent back through Feishu when you provide a path or ask to send the most recently generated file
- command output, task results, and errors are returned to the Feishu chat with light emoji markers

Examples:

```text
填写周报
打开浏览器并搜索 GitHub Copilot CLI
!Get-Date
发送文件 C:\Users\su600\Desktop\技术分析.pptx
把图片通过飞书发给我
```

## Notes

- This app intentionally does not store Feishu secrets in source control.
- This version uses long connection, so you do **not** need a public callback URL, public IP, `ngrok`, or `cloudflared`.
- If messages are not arriving, first verify:
  - the app version was published
  - the bot capability is enabled
  - `im.message.receive_v1` is subscribed
  - the required permissions were granted
  - `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, and `FEISHU_VERIFY_TOKEN` are correct in `.env`
