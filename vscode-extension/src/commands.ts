/**
 * VS Code commands for Shared Synapse.
 */
import * as vscode from 'vscode';
import type { SynapseClient } from './client';
import { McpBridge } from './mcpBridge';

type ClientGetter = () => SynapseClient | null;
type ClientSetter = (client: SynapseClient | null) => void;
type AsyncHook = () => Promise<void>;

export function registerCommands(
  context: vscode.ExtensionContext,
  getClient: ClientGetter,
  setClient: ClientSetter,
  statusBarItem: vscode.StatusBarItem,
  syncNow: AsyncHook,
  toggleSyncEnabled: AsyncHook,
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

  // Manage Synapses (toggle active set)
  context.subscriptions.push(
    vscode.commands.registerCommand('sharedSynapse.manageSynapses', async () => {
      const client = getClient();
      if (!client) { showNotConnected(); return; }

      try {
        const synapses = await client.listSynapses();
        if (!synapses.length) {
          vscode.window.showInformationMessage('No synapses available on the server.');
          return;
        }

        const picked = await vscode.window.showQuickPick(
          synapses.map((synapse) => ({
            label: synapse.name,
            picked: synapse.active,
            description: synapse.active ? 'active' : 'inactive',
          })),
          {
            canPickMany: true,
            placeHolder: 'Select which synapses should remain active',
          },
        );

        if (!picked) return;

        const selected = new Set(picked.map((item) => item.label));
        const currentlyActive = new Set(synapses.filter((synapse) => synapse.active).map((synapse) => synapse.name));

        const toActivate = synapses
          .map((synapse) => synapse.name)
          .filter((name) => selected.has(name) && !currentlyActive.has(name));
        const toDeactivate = synapses
          .map((synapse) => synapse.name)
          .filter((name) => currentlyActive.has(name) && !selected.has(name) && name !== 'core-brainstem');

        await Promise.all([
          ...toActivate.map((name) => client.activateSynapse(name)),
          ...toDeactivate.map((name) => client.deactivateSynapse(name)),
        ]);

        await syncNow();
        vscode.window.showInformationMessage('Synapse activation updated.');
      } catch (err: unknown) {
        vscode.window.showErrorMessage(`Manage synapses failed: ${String(err)}`);
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
      const url = config.get<string>('dashboardUrl', '').trim()
        || config.get<string>('serverUrl', 'http://localhost:5173');
      vscode.env.openExternal(vscode.Uri.parse(url));
    }),
  );

  // Connect (prompt for server URL + auth method)
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

      const authMode = await vscode.window.showQuickPick(
        [
          { label: 'API Token', value: 'apiToken' },
          { label: 'Username + Password', value: 'credentials' },
        ],
        { placeHolder: 'Select authentication method' },
      );
      if (!authMode) return;

      const { SynapseClient } = await import('./client');
      const tempClient = new SynapseClient(serverUrl, '', '', context.secrets, '');

      if (authMode.value === 'apiToken') {
        const apiToken = await vscode.window.showInputBox({
          prompt: 'Personal API token',
          password: true,
          ignoreFocusOut: true,
        });
        if (!apiToken) return;

        try {
          await tempClient.useApiToken(apiToken);
          await tempClient.listSynapses();
          setClient(tempClient);
          await syncNow();
          vscode.window.showInformationMessage('Connected to Shared Synapse with API token!');
          statusBarItem.text = '$(brain) Synapse';
        } catch (err: unknown) {
          vscode.window.showErrorMessage(`API token authentication failed: ${String(err)}`);
        }
        return;
      }

      const username = await vscode.window.showInputBox({ prompt: 'Username', ignoreFocusOut: true });
      if (!username) return;
      const password = await vscode.window.showInputBox({
        prompt: 'Password',
        password: true,
        ignoreFocusOut: true,
      });
      if (!password) return;

      try {
        await tempClient.login(username, password);
        setClient(tempClient);
        await syncNow();
        vscode.window.showInformationMessage('Connected to Shared Synapse!');
        statusBarItem.text = '$(brain) Synapse';
      } catch (err: unknown) {
        vscode.window.showErrorMessage(`Login failed: ${String(err)}`);
      }
    }),
  );

  // Set or replace API token without changing server URL.
  context.subscriptions.push(
    vscode.commands.registerCommand('sharedSynapse.setApiToken', async () => {
      const config = vscode.workspace.getConfiguration('sharedSynapse');
      const serverUrl = config.get<string>('serverUrl', '').trim();
      if (!serverUrl) {
        vscode.window.showWarningMessage('Set Shared Synapse server URL first with "Connect to Server".');
        return;
      }

      const apiToken = await vscode.window.showInputBox({
        prompt: 'Personal API token',
        password: true,
        ignoreFocusOut: true,
      });
      if (!apiToken) return;

      const { SynapseClient } = await import('./client');
      const tempClient = new SynapseClient(serverUrl, '', '', context.secrets, '');
      try {
        await tempClient.useApiToken(apiToken);
        await tempClient.listSynapses();
        setClient(tempClient);
        await syncNow();
        vscode.window.showInformationMessage('API token saved and connection verified.');
      } catch (err: unknown) {
        vscode.window.showErrorMessage(`Unable to verify API token: ${String(err)}`);
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

  // Sync now
  context.subscriptions.push(
    vscode.commands.registerCommand('sharedSynapse.syncNow', async () => {
      await syncNow();
    }),
  );

  // Toggle background sync
  context.subscriptions.push(
    vscode.commands.registerCommand('sharedSynapse.toggleSync', async () => {
      await toggleSyncEnabled();
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
