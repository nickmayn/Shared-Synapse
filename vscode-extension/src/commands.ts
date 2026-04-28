/**
 * VS Code commands for Shared Synapse.
 */
import * as vscode from 'vscode';
import type { SynapseClient } from './client';
import { McpBridge } from './mcpBridge';

type ClientGetter = () => SynapseClient | null;

export function registerCommands(
  context: vscode.ExtensionContext,
  getClient: ClientGetter,
  statusBarItem: vscode.StatusBarItem,
): void {
  // Search Knowledge
  context.subscriptions.push(
    vscode.commands.registerCommand('sharedSynapse.searchKnowledge', async () => {
      const client = getClient();
      if (!client) { showNotConnected(); return; }

      const query = await vscode.window.showInputBox({
        prompt: 'Search Shared Synapse knowledge',
        placeHolder: 'e.g. how does authentication work',
      });
      if (!query) return;

      try {
        const data = await client.searchKnowledge(query);
        const results = data.results ?? [];
        if (!results.length) {
          vscode.window.showInformationMessage('No results found.');
          return;
        }
        const items = results.map((r) => ({
          label: r.document_id,
          description: `score: ${r.score.toFixed(3)}`,
          detail: r.chunk_content?.substring(0, 120),
        }));
        const picked = await vscode.window.showQuickPick(items, {
          matchOnDescription: true,
          matchOnDetail: true,
          placeHolder: 'Select a result to copy to clipboard',
        });
        if (picked) {
          const full = results.find((r) => r.document_id === picked.label);
          if (full) await vscode.env.clipboard.writeText(full.chunk_content);
        }
      } catch (err: unknown) {
        vscode.window.showErrorMessage(`Search failed: ${String(err)}`);
      }
    }),
  );

  // Activate Synapse
  context.subscriptions.push(
    vscode.commands.registerCommand('sharedSynapse.activateSynapse', async () => {
      const client = getClient();
      if (!client) { showNotConnected(); return; }

      try {
        const synapses = await client.listSynapses();
        const optional = synapses.filter((s) => !s.active);
        if (!optional.length) {
          vscode.window.showInformationMessage('All available synapses are already active.');
          return;
        }
        const picked = await vscode.window.showQuickPick(
          optional.map((s) => s.name),
          { placeHolder: 'Select a synapse to activate' },
        );
        if (!picked) return;
        await client.activateSynapse(picked);
        vscode.window.showInformationMessage(`Synapse '${picked}' activated.`);
        statusBarItem.text = `$(brain) Synapse [${picked}]`;
      } catch (err: unknown) {
        vscode.window.showErrorMessage(`Activate failed: ${String(err)}`);
      }
    }),
  );

  // Push Selection to Knowledge
  context.subscriptions.push(
    vscode.commands.registerCommand('sharedSynapse.pushSelection', async () => {
      const client = getClient();
      if (!client) { showNotConnected(); return; }

      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage('No active editor.');
        return;
      }
      const selection = editor.document.getText(editor.selection);
      if (!selection.trim()) {
        vscode.window.showWarningMessage('No text selected.');
        return;
      }

      const docId = await vscode.window.showInputBox({
        prompt: 'Knowledge ID (unique identifier)',
        value: `vscode-${Date.now()}`,
      });
      if (!docId) return;

      const docType = await vscode.window.showQuickPick(
        ['concept', 'rule', 'skill', 'decision', 'tool', 'document'],
        { placeHolder: 'Select knowledge type' },
      );
      if (!docType) return;

      try {
        const lang = editor.document.languageId;
        await client.addKnowledge(docId, docType, selection, {
          source: 'vscode_selection',
          language: lang,
          file: editor.document.fileName,
        });
        vscode.window.showInformationMessage(`Pushed to knowledge as '${docId}' (${docType}).`);
      } catch (err: unknown) {
        vscode.window.showErrorMessage(`Push failed: ${String(err)}`);
      }
    }),
  );

  // Open Dashboard
  context.subscriptions.push(
    vscode.commands.registerCommand('sharedSynapse.openDashboard', () => {
      const config = vscode.workspace.getConfiguration('sharedSynapse');
      const url = config.get<string>('serverUrl', 'http://localhost:5173');
      // Open in the default browser
      vscode.env.openExternal(vscode.Uri.parse(url));
    }),
  );

  // Connect (prompt for server URL + credentials)
  context.subscriptions.push(
    vscode.commands.registerCommand('sharedSynapse.connect', async () => {
      const config = vscode.workspace.getConfiguration('sharedSynapse');
      const serverUrl = await vscode.window.showInputBox({
        prompt: 'Shared Synapse server URL',
        value: config.get<string>('serverUrl', 'http://localhost:8000'),
        ignoreFocusOut: true,
      });
      if (!serverUrl) return;
      await config.update('serverUrl', serverUrl, vscode.ConfigurationTarget.Global);

      const username = await vscode.window.showInputBox({ prompt: 'Username', ignoreFocusOut: true });
      if (!username) return;
      const password = await vscode.window.showInputBox({
        prompt: 'Password',
        password: true,
        ignoreFocusOut: true,
      });
      if (!password) return;

      const { SynapseClient } = await import('./client');
      const tempClient = new SynapseClient(serverUrl, '', '', context.secrets);
      try {
        await tempClient.login(username, password);
        vscode.window.showInformationMessage('Connected to Shared Synapse!');
        statusBarItem.text = '$(brain) Synapse';
      } catch (err: unknown) {
        vscode.window.showErrorMessage(`Login failed: ${String(err)}`);
      }
    }),
  );

  // Start Local MCP Agent
  context.subscriptions.push(
    vscode.commands.registerCommand('sharedSynapse.startLocalAgent', async () => {
      const config = vscode.workspace.getConfiguration('sharedSynapse');
      let backendPath = config.get<string>('localBackendPath', '').trim();
      if (!backendPath) {
        backendPath = await vscode.window.showInputBox({
          prompt: 'Path to Shared Synapse backend directory',
          placeHolder: '/path/to/Shared-Synapse/backend',
          ignoreFocusOut: true,
        }) ?? '';
        if (!backendPath) return;
        await config.update('localBackendPath', backendPath, vscode.ConfigurationTarget.Global);
      }

      const bridge = new McpBridge(backendPath);
      bridge.start();
      vscode.window.showInformationMessage('Local Shared Synapse MCP agent started.');
    }),
  );
}

function showNotConnected(): void {
  vscode.window.showWarningMessage(
    'Shared Synapse is not connected. Run "Shared Synapse: Connect to Server" first.',
    'Connect',
  ).then((choice) => {
    if (choice === 'Connect') {
      vscode.commands.executeCommand('sharedSynapse.connect');
    }
  });
}
