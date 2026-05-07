/**
 * Activity Bar sidebar view for Shared Synapse controls and status.
 */
import * as os from 'os';
import * as path from 'path';
import * as vscode from 'vscode';

type ConnectionState = 'connected' | 'disconnected';

interface ConfigurationState {
  serverUrl: string;
  dashboardUrl: string;
  apiToken?: string;
  localBackendPath: string;
  localSyncPath: string;
  autoConnect: boolean;
  syncWorkspaceExtensions: boolean;
  syncEnabled: boolean;
  pullResourcesToWorkspace: boolean;
  serverCheckIntervalSeconds: number;
}

interface SidebarCallbacks {
  getConfigurationState: () => ConfigurationState;
  getRuntimeState: () => {
    state: ConnectionState;
    activeSynapses: string[];
    syncEnabled: boolean;
    localSyncSummary: string;
    config: ConfigurationState;
  };
  onSaveSettings: (next: ConfigurationState) => Promise<void>;
}

export class SharedSynapseSidebarProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'sharedSynapse.sidebar';

  private view: vscode.WebviewView | null = null;
  private connectionState: ConnectionState = 'disconnected';
  private activeSynapses: string[] = [];
  private syncEnabled = true;
  private localSyncSummary = '';
  private configState: ConfigurationState | null = null;

  constructor(
    private readonly extensionUri: vscode.Uri,
    private readonly callbacks: SidebarCallbacks,
  ) {}

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    const runtimeState = this.callbacks.getRuntimeState();
    this.connectionState = runtimeState.state;
    this.activeSynapses = [...runtimeState.activeSynapses];
    this.syncEnabled = runtimeState.syncEnabled;
    this.localSyncSummary = runtimeState.localSyncSummary;
    this.configState = runtimeState.config;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this.extensionUri],
    };

    webviewView.webview.html = this.getHtml(webviewView.webview);
    this.postState();

    webviewView.webview.onDidReceiveMessage(async (message: {
      command?: string;
      type?: string;
      settings?: ConfigurationState;
    }) => {
      if (message.command) {
        await vscode.commands.executeCommand(message.command);
        return;
      }
      if (message.type === 'saveSettings' && message.settings) {
        await this.callbacks.onSaveSettings(message.settings);
      }
      if (message.type === 'togglePower') {
        await vscode.commands.executeCommand('sharedSynapse.toggleConnection');
      }
      if (message.type === 'openRulesFolder') {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (workspaceRoot) {
          const config = this.configState ?? this.callbacks.getConfigurationState();
          const folderUri = vscode.Uri.joinPath(
            vscode.Uri.file(workspaceRoot),
            config.localSyncPath || '.agents',
            'instructions',
          );
          await vscode.commands.executeCommand('revealFileInOS', folderUri);
        } else {
          vscode.window.showWarningMessage('No workspace folder is open.');
        }
      }
      if (message.type === 'openGlobalRulesFolder') {
        const globalCursorRules = vscode.Uri.file(
          path.join(os.homedir(), '.cursor', 'rules'),
        );
        await vscode.commands.executeCommand('revealFileInOS', globalCursorRules);
      }
    });
  }

  update(
    state: ConnectionState,
    activeSynapses: string[],
    syncEnabled: boolean,
    localSyncSummary: string,
    configState: ConfigurationState,
  ): void {
    this.connectionState = state;
    this.activeSynapses = [...activeSynapses];
    this.syncEnabled = syncEnabled;
    this.localSyncSummary = localSyncSummary;
    this.configState = configState;
    this.postState();
  }

  private postState(): void {
    if (!this.view) return;
    const config = this.configState ?? this.callbacks.getConfigurationState();
    this.view.webview.postMessage({
      type: 'state',
      state: this.connectionState,
      activeSynapses: this.activeSynapses,
      syncEnabled: this.syncEnabled,
      localSyncSummary: this.localSyncSummary,
      config,
    });
  }

  private getHtml(webview: vscode.Webview): string {
    const nonce = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const csp = [
      "default-src 'none'",
      `style-src ${webview.cspSource} 'unsafe-inline'`,
      `script-src 'nonce-${nonce}'`,
    ].join('; ');

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="${csp}" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Shared Synapse</title>
  <style>
    :root { color-scheme: light dark; }
    body {
      margin: 0;
      padding: 10px;
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
      color: var(--vscode-foreground);
      background: var(--vscode-sideBar-background);
      display: grid;
      gap: 8px;
    }
    .card {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 6px;
      padding: 10px 12px;
      background: color-mix(in srgb, var(--vscode-editor-background) 85%, transparent);
      display: grid;
      gap: 5px;
    }
    .status-row {
      display: flex;
      align-items: center;
      gap: 7px;
    }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
      background: var(--vscode-testing-iconFailed);
    }
    .dot.connected { background: var(--vscode-testing-iconPassed); }
    .status-label {
      font-weight: 600;
      font-size: 13px;
    }
    .meta-row {
      display: flex;
      gap: 6px;
      align-items: baseline;
      flex-wrap: wrap;
    }
    .meta-key {
      font-size: 10px;
      color: var(--vscode-descriptionForeground);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      font-weight: 600;
      white-space: nowrap;
    }
    .meta-val {
      font-size: 11px;
      color: var(--vscode-foreground);
      word-break: break-word;
    }
    .meta-val.muted { color: var(--vscode-descriptionForeground); }
    .divider {
      height: 1px;
      background: var(--vscode-panel-border);
      margin: 2px 0;
    }
    .sync-summary {
      font-size: 11px;
      color: var(--vscode-descriptionForeground);
      line-height: 1.45;
      word-break: break-word;
    }
    .actions { display: grid; gap: 5px; }
    .actions-row { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; }
    .actions-row.cols-3 { grid-template-columns: 1fr 1fr 1fr; }
    button {
      border: 1px solid var(--vscode-button-border, transparent);
      border-radius: 4px;
      min-height: 26px;
      padding: 0 10px;
      color: var(--vscode-button-foreground);
      background: var(--vscode-button-background);
      cursor: pointer;
      text-align: center;
      font-size: 11px;
      font-family: var(--vscode-font-family);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    button.secondary {
      color: var(--vscode-button-secondaryForeground);
      background: var(--vscode-button-secondaryBackground);
    }
    button.full { grid-column: 1 / -1; }
    button:hover { filter: brightness(1.1); }
    .field { display: grid; gap: 3px; }
    .field label { font-size: 11px; color: var(--vscode-descriptionForeground); }
    .field input[type="text"],
    .field input[type="password"],
    .field input[type="number"] {
      width: 100%;
      box-sizing: border-box;
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border, var(--vscode-panel-border));
      border-radius: 3px;
      padding: 3px 6px;
      font-family: var(--vscode-font-family);
      font-size: 12px;
    }
    .field input[type="checkbox"] { accent-color: var(--vscode-focusBorder); margin: 0; }
    .check-row { display: flex; align-items: center; gap: 6px; font-size: 12px; }
    details summary {
      cursor: pointer;
      font-size: 10px;
      color: var(--vscode-descriptionForeground);
      text-transform: uppercase;
      letter-spacing: 0.07em;
      font-weight: 600;
      list-style: none;
      display: flex;
      align-items: center;
      gap: 4px;
    }
    details summary::before { content: '▶'; font-size: 9px; transition: transform 0.15s; }
    details[open] summary::before { transform: rotate(90deg); }
    details .settings-body { margin-top: 8px; display: grid; gap: 8px; }
  </style>
</head>
<body>

  <!-- Unified status card -->
  <div class="card">
    <div class="status-row">
      <div id="statusDot" class="dot"></div>
      <div id="statusLabel" class="status-label">Disconnected</div>
    </div>
    <div class="divider"></div>
    <div class="meta-row">
      <span class="meta-key">Active</span>
      <span id="activeSynapses" class="meta-val muted">none</span>
    </div>
    <div class="meta-row">
      <span class="meta-key">Sync</span>
      <span id="syncStatus" class="meta-val muted">On</span>
    </div>
    <div class="meta-row">
      <span class="meta-key">Last</span>
      <span id="lastSync" class="meta-val muted">Not yet run</span>
    </div>
    <div id="syncSummary" class="sync-summary" style="display:none"></div>
  </div>

  <!-- Actions -->
  <div class="actions">
    <button class="full" id="powerBtn">Turn On</button>
    <div class="actions-row">
      <button class="secondary" data-command="sharedSynapse.syncNow">Sync Now</button>
      <button class="secondary" data-command="sharedSynapse.manageSynapses">Synapses</button>
    </div>
    <div class="actions-row">
      <button class="secondary" data-command="sharedSynapse.toggleSync">Toggle Sync</button>
      <button class="secondary" data-command="sharedSynapse.connect">Connect Wizard</button>
    </div>
    <div class="actions-row cols-3">
      <button class="secondary" id="openRulesBtn">Open Rules</button>
      <button class="secondary" id="openGlobalRulesBtn">Global Rules</button>
      <button class="secondary" data-command="sharedSynapse.openDashboard">Dashboard</button>
    </div>
  </div>

  <!-- Settings (collapsible) -->
  <div class="card">
    <details>
      <summary>Settings</summary>
      <div class="settings-body">
        <div class="field">
          <label for="serverUrl">Server URL</label>
          <input id="serverUrl" type="text" placeholder="http://localhost:8000" />
        </div>
        <div class="field">
          <label for="dashboardUrl">Dashboard URL</label>
          <input id="dashboardUrl" type="text" placeholder="http://localhost:5173" />
        </div>
        <div class="field">
          <label for="apiToken">API Token</label>
          <input id="apiToken" type="password" placeholder="Enter or replace token" />
        </div>
        <div class="field">
          <label for="localSyncPath">Agent Sync Directory</label>
          <input id="localSyncPath" type="text" placeholder=".agents" />
        </div>
        <div class="field">
          <label for="intervalSeconds">Poll Interval (seconds)</label>
          <input id="intervalSeconds" type="number" min="15" step="15" />
        </div>
        <div class="check-row">
          <input id="pullResources" type="checkbox" />
          <label for="pullResources">Pull resources to workspace</label>
        </div>
        <div class="check-row">
          <input id="autoConnect" type="checkbox" />
          <label for="autoConnect">Auto-connect on startup</label>
        </div>
        <div class="check-row">
          <input id="syncExtensions" type="checkbox" />
          <label for="syncExtensions">Sync installed extensions</label>
        </div>
        <button id="saveSettingsBtn">Save Settings</button>
      </div>
    </details>
  </div>

  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    let currentConfig = {};
    let lastSyncedAt = null;

    for (const button of document.querySelectorAll('button[data-command]')) {
      button.addEventListener('click', () => {
        vscode.postMessage({ command: button.getAttribute('data-command') });
      });
    }

    document.getElementById('powerBtn').addEventListener('click', () => {
      vscode.postMessage({ type: 'togglePower' });
    });

    document.getElementById('openRulesBtn').addEventListener('click', () => {
      vscode.postMessage({ type: 'openRulesFolder' });
    });

    document.getElementById('openGlobalRulesBtn').addEventListener('click', () => {
      vscode.postMessage({ type: 'openGlobalRulesFolder' });
    });

    document.getElementById('saveSettingsBtn').addEventListener('click', () => {
      vscode.postMessage({
        type: 'saveSettings',
        settings: {
          ...currentConfig,
          serverUrl: document.getElementById('serverUrl').value.trim(),
          dashboardUrl: document.getElementById('dashboardUrl').value.trim(),
          apiToken: document.getElementById('apiToken').value.trim(),
          localSyncPath: document.getElementById('localSyncPath').value.trim() || '.agents',
          serverCheckIntervalSeconds: Number(document.getElementById('intervalSeconds').value) || 60,
          pullResourcesToWorkspace: document.getElementById('pullResources').checked,
          autoConnect: document.getElementById('autoConnect').checked,
          syncWorkspaceExtensions: document.getElementById('syncExtensions').checked,
        },
      });
    });

    function formatTime(iso) {
      try {
        return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
      } catch { return iso; }
    }

    function applyConfig(cfg) {
      currentConfig = cfg;
      document.getElementById('serverUrl').value = cfg.serverUrl || '';
      document.getElementById('dashboardUrl').value = cfg.dashboardUrl || '';
      document.getElementById('apiToken').value = '';
      document.getElementById('localSyncPath').value = cfg.localSyncPath || '.agents';
      document.getElementById('intervalSeconds').value = cfg.serverCheckIntervalSeconds || 60;
      document.getElementById('pullResources').checked = cfg.pullResourcesToWorkspace !== false;
      document.getElementById('autoConnect').checked = cfg.autoConnect !== false;
      document.getElementById('syncExtensions').checked = cfg.syncWorkspaceExtensions !== false;
    }

    window.addEventListener('message', (event) => {
      const msg = event.data;
      if (!msg || msg.type !== 'state') return;

      const isConnected = msg.state === 'connected';

      document.getElementById('statusDot').className = 'dot' + (isConnected ? ' connected' : '');
      document.getElementById('statusLabel').textContent = isConnected ? 'Connected' : 'Disconnected';
      document.getElementById('powerBtn').textContent = isConnected ? 'Turn Off' : 'Turn On';

      const list = Array.isArray(msg.activeSynapses) ? msg.activeSynapses : [];
      const activesEl = document.getElementById('activeSynapses');
      activesEl.textContent = list.length ? list.join(', ') : 'none';
      activesEl.className = 'meta-val' + (list.length ? '' : ' muted');

      document.getElementById('syncStatus').textContent = msg.syncEnabled ? 'On' : 'Off';

      const summaryEl = document.getElementById('syncSummary');
      const lastEl = document.getElementById('lastSync');
      if (msg.localSyncSummary && msg.localSyncSummary !== 'Local sync has not run yet.') {
        if (!lastSyncedAt) lastSyncedAt = new Date().toISOString();
        lastEl.textContent = formatTime(lastSyncedAt);
        lastEl.className = 'meta-val';
        summaryEl.textContent = msg.localSyncSummary;
        summaryEl.style.display = '';
      } else {
        lastEl.textContent = 'Not yet run';
        lastEl.className = 'meta-val muted';
        summaryEl.style.display = 'none';
      }

      if (msg.config) applyConfig(msg.config);
    });
  </script>
</body>
</html>`;
  }
}
