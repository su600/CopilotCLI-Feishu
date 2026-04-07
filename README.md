# Feishu Bot

A local Python Feishu private-chat bot that:

- receives Feishu events over long connection
- handles private text messages
- replies back to the sender
- optionally uses an OpenAI-compatible API for smart replies

## What this version supports

- Feishu private chat bot
- `im.message.receive_v1`
- Feishu long connection / WebSocket event receiving
- plain text replies
- optional AI replies when `OPENAI_API_KEY` is configured

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
    config.py
    executor.py
    feishu_api.py
    responder.py
  tests/
    __init__.py
    test_bot.py
  .env.example
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

If you want AI replies, also fill:

- `OPENAI_API_KEY`
- optionally `OPENAI_BASE_URL`
- optionally `OPENAI_MODEL`

Optionally, configure execution paths:

- `WORK_DIR` – working directory for command execution (default: user home directory)
- `ARTIFACT_DIR` – directory where generated artifacts are stored (default: `~/.feishu-bot/artifacts`)

## Run locally

```powershell
.\run.ps1
```

Or:

```powershell
python main.py
```

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

This bot now runs in autonomous local execution mode.

- `/help` and `ping` are handled as built-in bot commands
- messages starting with `!` are executed directly as PowerShell on this Windows machine
- broad natural-language requests are sent to local `copilot` for intent understanding and single-action execution
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
