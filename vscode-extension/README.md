<div align="center">
  <img src="media/brain-icon.png" alt="Shared Synapse" width="80" />
  <h1>Shared Synapse</h1>
  <p>Connect VS Code to your team's Shared Synapse second brain — pull active skills, rules, and tools directly into your workspace.</p>
</div>

---

## Features

- **Pull-to-local sync** — Active synapse resources (skills, rules, tools) are written to your workspace folder on every sync, making the server the single source of truth for the whole team.
- **Activity Bar panel** — Dedicated sidebar with connection status, last sync summary, quick-action buttons, and an inline settings editor.
- **API token auth** — Generate personal API tokens from the web UI and paste them into the extension for secure, password-free authentication.
- **Background polling** — Automatically detects server-side synapse changes and prompts you to pull the latest.
- **MCP bridge** — Optionally run a local MCP stdio agent backed by your Shared Synapse server.

## Getting Started

### 1. Install

Build the VSIX and install it:

```bash
cd vscode-extension
npm install
npm run package     # produces shared-synapse-*.vsix
```

Then in VS Code: **Extensions → ··· → Install from VSIX…**

### 2. Connect

Open the **Shared Synapse** panel in the Activity Bar and click **Connect to Server**.  
Enter your server URL (e.g. `http://localhost:8000`) and choose an authentication method:

| Method | How |
|---|---|
| Username + Password | Standard login — tokens stored in VS Code SecretStorage |
| API Token | Generate one at **Settings → API Tokens** in the web UI, then click **Set API Token** in the sidebar |

### 3. Sync

Click **Sync Now** to immediately pull all resources from active synapses into your workspace under `.shared-synapse/` (configurable).  
Background polling runs every 60 seconds by default and notifies you when server state changes.

## Local Sync Directory

After sync, your workspace will contain:

```
.shared-synapse/
  skills/   ← Markdown files with YAML front-matter
  rules/    ← Markdown files with YAML front-matter
  tools/    ← JSON tool definitions
  manifest.json
```

Each file carries `id`, `name`, `description`, and `source: "shared-synapse-sync"` in its front-matter.  
Stale files (resources no longer in active synapses) are removed automatically.

## Settings

| Setting | Default | Description |
|---|---|---|
| `sharedSynapse.serverUrl` | — | Base URL of the Shared Synapse API |
| `sharedSynapse.localSyncPath` | `.shared-synapse` | Workspace-relative directory for synced resources |
| `sharedSynapse.pullResourcesToWorkspace` | `true` | Write active resources to disk on every sync |
| `sharedSynapse.syncEnabled` | `true` | Enable background polling |
| `sharedSynapse.serverCheckIntervalSeconds` | `60` | Poll interval (minimum 15 s) |
| `sharedSynapse.autoConnect` | `true` | Connect on VS Code startup |
| `sharedSynapse.syncWorkspaceExtensions` | `true` | Push installed extension list to knowledge store |

Settings can be edited in the sidebar panel (Settings section, collapsible) or in **File → Preferences → Settings**.

## Building from Source

Requires Node 18+.

```bash
cd vscode-extension
npm install
npm run compile   # type-check only
npm run package   # full VSIX build
```
