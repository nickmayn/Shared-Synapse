/**
 * Shared Synapse VS Code Extension
 * Extension entry point – activation, status bar, auto-connect, settings sync.
 */
import * as vscode from 'vscode';
import { SynapseClient } from './client';
import { registerCommands } from './commands';
import { McpBridge } from './mcpBridge';

let statusBarItem: vscode.StatusBarItem;
let client: SynapseClient | null = null;
let mcpBridge: McpBridge | null = null;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  // Status bar
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.command = 'sharedSynapse.activateSynapse';
  context.subscriptions.push(statusBarItem);
  setStatusBar('disconnected');

  // Build the REST client
  client = await buildClient(context);

  // Register all commands, passing the client factory
  registerCommands(context, () => client, statusBarItem);

  // Auto-connect: verify connectivity and update status bar
  if (vscode.workspace.getConfiguration('sharedSynapse').get<boolean>('autoConnect', true)) {
    await tryConnect(context);
  }

  // Sync workspace extensions if enabled
  if (
    client &&
    vscode.workspace.getConfiguration('sharedSynapse').get<boolean>('syncWorkspaceExtensions', true)
  ) {
    syncWorkspaceExtensions(client).catch(() => {/* best-effort */});
  }
}

export function deactivate(): void {
  mcpBridge?.stop();
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function buildClient(context: vscode.ExtensionContext): Promise<SynapseClient | null> {
  const config = vscode.workspace.getConfiguration('sharedSynapse');
  let serverUrl = config.get<string>('serverUrl', '').trim();

  // Prompt on first launch
  if (!serverUrl) {
    serverUrl = await promptForServerUrl() ?? '';
    if (serverUrl) {
      await config.update('serverUrl', serverUrl, vscode.ConfigurationTarget.Global);
    }
  }

  if (!serverUrl) return null;

  const token = await context.secrets.get('sharedSynapse.accessToken') ?? '';
  const refresh = await context.secrets.get('sharedSynapse.refreshToken') ?? '';
  return new SynapseClient(serverUrl, token, refresh, context.secrets);
}

async function promptForServerUrl(): Promise<string | undefined> {
  return vscode.window.showInputBox({
    prompt: 'Enter the Shared Synapse server URL',
    placeHolder: 'http://localhost:8000',
    ignoreFocusOut: true,
  });
}

async function tryConnect(context: vscode.ExtensionContext): Promise<void> {
  if (!client) return;
  try {
    await client.healthCheck();
    const synapses = await client.listSynapses();
    const active = synapses.filter((s: { active: boolean }) => s.active).map((s: { name: string }) => s.name);
    setStatusBar('connected', active);
  } catch {
    setStatusBar('disconnected');
  }
}

function setStatusBar(state: 'connected' | 'disconnected', activeSynapses: string[] = []): void {
  if (state === 'connected') {
    const synapseLabel = activeSynapses.length > 0 ? ` [${activeSynapses.join(', ')}]` : '';
    statusBarItem.text = `$(brain) Synapse${synapseLabel}`;
    statusBarItem.tooltip = `Shared Synapse – connected${synapseLabel}. Click to activate a synapse.`;
    statusBarItem.backgroundColor = undefined;
  } else {
    statusBarItem.text = '$(brain) Synapse (disconnected)';
    statusBarItem.tooltip = 'Shared Synapse – not connected. Click to set up.';
    statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
  }
  statusBarItem.show();
}

async function syncWorkspaceExtensions(synapseClient: SynapseClient): Promise<void> {
  const extensions = vscode.extensions.all
    .filter((e) => !e.id.startsWith('vscode.'))
    .map((e) => ({ id: e.id, displayName: e.packageJSON?.displayName ?? e.id }));

  const content = JSON.stringify({ installed_extensions: extensions }, null, 2);
  try {
    await synapseClient.addKnowledge(
      'vscode-workspace-extensions',
      'tool',
      content,
      { source: 'vscode_extension', workspace: vscode.workspace.name ?? 'unknown' },
    );
  } catch {
    // best-effort
  }
}
