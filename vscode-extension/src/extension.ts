/**
 * Shared Synapse VS Code Extension
 * Extension entry point – activation, status bar, auto-connect, settings sync.
 */
import * as vscode from 'vscode';
import { promises as fs } from 'fs';
import * as os from 'os';
import * as path from 'path';
import { SynapseClient } from './client';
import { registerCommands } from './commands';
import { McpBridge } from './mcpBridge';
import { SharedSynapseSidebarProvider } from './sidebarView';

let statusBarItem: vscode.StatusBarItem;
let client: SynapseClient | null = null;
let mcpBridge: McpBridge | null = null;
let serverPollTimer: NodeJS.Timeout | null = null;
let lastServerSnapshot: string | null = null;
let lastPromptedSnapshot: string | null = null;
let connectionState: 'connected' | 'disconnected' = 'disconnected';
let currentActiveSynapses: string[] = [];
let sidebarProvider: SharedSynapseSidebarProvider | null = null;
let lastLocalSyncSummary = 'Local sync has not run yet.';
let extensionContext: vscode.ExtensionContext | null = null;

const BACKUP_STATE_KEY = 'sharedSynapse.fileBackups';

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  extensionContext = context;
  sidebarProvider = new SharedSynapseSidebarProvider(context.extensionUri, {
    getConfigurationState,
    getRuntimeState: () => ({
      state: connectionState,
      activeSynapses: currentActiveSynapses,
      syncEnabled: vscode.workspace.getConfiguration('sharedSynapse').get<boolean>('syncEnabled', true),
      localSyncSummary: lastLocalSyncSummary,
      config: getConfigurationState(),
    }),
    onSaveSettings: async (nextSettings) => {
      const config = vscode.workspace.getConfiguration('sharedSynapse');
      const current = getConfigurationState();
      const merged = {
        ...current,
        ...nextSettings,
      };
      const rawApiToken = (nextSettings as { apiToken?: string }).apiToken ?? '';
      const apiToken = rawApiToken.trim();

      await config.update('serverUrl', merged.serverUrl, vscode.ConfigurationTarget.Global);
      await config.update('dashboardUrl', merged.dashboardUrl, vscode.ConfigurationTarget.Global);
      await config.update('localBackendPath', merged.localBackendPath, vscode.ConfigurationTarget.Global);
      await config.update('localSyncPath', merged.localSyncPath, vscode.ConfigurationTarget.Global);
      await config.update('autoConnect', merged.autoConnect, vscode.ConfigurationTarget.Global);
      await config.update('syncWorkspaceExtensions', merged.syncWorkspaceExtensions, vscode.ConfigurationTarget.Global);
      await config.update('syncEnabled', merged.syncEnabled, vscode.ConfigurationTarget.Global);
      await config.update('pullResourcesToWorkspace', merged.pullResourcesToWorkspace, vscode.ConfigurationTarget.Global);
      await config.update('serverCheckIntervalSeconds', merged.serverCheckIntervalSeconds, vscode.ConfigurationTarget.Global);

      if (apiToken) {
        await context.secrets.store('sharedSynapse.apiToken', apiToken);
        await context.secrets.delete('sharedSynapse.accessToken');
        await context.secrets.delete('sharedSynapse.refreshToken');
      }

      const shouldRebuildClient = merged.serverUrl !== current.serverUrl || Boolean(apiToken);
      if (shouldRebuildClient) {
        client = await buildClient(context);
      }

      startServerPolling(context);
      setStatusBar(connectionState, currentActiveSynapses);
      vscode.window.showInformationMessage('Shared Synapse settings saved.');
    },
  });
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(SharedSynapseSidebarProvider.viewType, sidebarProvider),
  );

  // Status bar
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.command = 'sharedSynapse.activateSynapse';
  context.subscriptions.push(statusBarItem);
  setStatusBar('disconnected');

  // Build the REST client
  client = await buildClient(context);

  // Register all commands, passing the client factory
  registerCommands(
    context,
    () => client,
    (nextClient) => {
      client = nextClient;
    },
    statusBarItem,
    async () => {
      await syncFromServer('manual');
      startServerPolling(context);
    },
    async () => {
      await toggleSyncEnabled();
      startServerPolling(context);
    },
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('sharedSynapse.toggleConnection', async () => {
      if (connectionState === 'connected') {
        stopServerPolling();
        setStatusBar('disconnected');
        vscode.window.showInformationMessage('Shared Synapse turned off.');
        return;
      }

      if (!client) {
        client = await buildClient(context);
      }
      if (!client) {
        vscode.window.showWarningMessage('Set Server URL and API token in Shared Synapse Settings, then save.');
        return;
      }

      await syncFromServer('manual');
      startServerPolling(context);
    }),
  );

  // Auto-connect: verify connectivity and update status bar
  if (vscode.workspace.getConfiguration('sharedSynapse').get<boolean>('autoConnect', true)) {
    await tryConnect();
  }

  // Reflect sync mode in status bar even before first successful sync.
  setStatusBar(connectionState, currentActiveSynapses);

  // Sync workspace extensions if enabled
  if (
    client &&
    vscode.workspace.getConfiguration('sharedSynapse').get<boolean>('syncWorkspaceExtensions', true)
  ) {
    syncWorkspaceExtensions(client).catch(() => {/* best-effort */});
  }

  startServerPolling(context);

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (
        event.affectsConfiguration('sharedSynapse.serverUrl') ||
        event.affectsConfiguration('sharedSynapse.dashboardUrl') ||
        event.affectsConfiguration('sharedSynapse.localBackendPath') ||
        event.affectsConfiguration('sharedSynapse.localSyncPath') ||
        event.affectsConfiguration('sharedSynapse.autoConnect') ||
        event.affectsConfiguration('sharedSynapse.syncWorkspaceExtensions') ||
        event.affectsConfiguration('sharedSynapse.syncEnabled') ||
        event.affectsConfiguration('sharedSynapse.pullResourcesToWorkspace') ||
        event.affectsConfiguration('sharedSynapse.serverCheckIntervalSeconds')
      ) {
        startServerPolling(context);
        setStatusBar(connectionState, currentActiveSynapses);
      }
    }),
  );
}

export function deactivate(): void {
  stopServerPolling();
  mcpBridge?.stop();
  if (extensionContext) {
    restoreBackedUpFiles(extensionContext).catch(() => {});
  }
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
  const apiToken = await context.secrets.get('sharedSynapse.apiToken') ?? '';
  return new SynapseClient(serverUrl, token, refresh, context.secrets, apiToken);
}

async function promptForServerUrl(): Promise<string | undefined> {
  return vscode.window.showInputBox({
    prompt: 'Enter the Shared Synapse server URL',
    placeHolder: 'http://localhost:8000',
    ignoreFocusOut: true,
  });
}

async function tryConnect(): Promise<void> {
  if (!client) return;
  try {
    await syncFromServer('silent');
  } catch {
    setStatusBar('disconnected');
  }
}

function getSynapseSnapshot(synapses: { name: string; active: boolean }[]): string {
  return JSON.stringify(
    [...synapses]
      .sort((left, right) => left.name.localeCompare(right.name))
      .map((synapse) => ({ name: synapse.name, active: synapse.active })),
  );
}

async function syncFromServer(mode: 'manual' | 'silent'): Promise<void> {
  if (!client) return;
  try {
    await client.healthCheck();
    const synapses = await client.listSynapses();
    const active = synapses.filter((synapse) => synapse.active).map((synapse) => synapse.name);
    if (vscode.workspace.getConfiguration('sharedSynapse').get<boolean>('pullResourcesToWorkspace', true)) {
      await syncActiveResourcesToWorkspace(client, active);
    }
    setStatusBar('connected', active);

    const snapshot = getSynapseSnapshot(synapses);
    lastServerSnapshot = snapshot;
    lastPromptedSnapshot = null;

    if (vscode.workspace.getConfiguration('sharedSynapse').get<boolean>('syncWorkspaceExtensions', true)) {
      await syncWorkspaceExtensions(client);
    }

    if (mode === 'manual') {
      vscode.window.showInformationMessage('Shared Synapse synchronized with server state.');
    }
  } catch {
    setStatusBar('disconnected');
    if (mode === 'manual') {
      vscode.window.showWarningMessage('Shared Synapse sync failed. Check server connectivity and credentials.');
    }
  }
}

function stopServerPolling(): void {
  if (serverPollTimer) {
    clearInterval(serverPollTimer);
    serverPollTimer = null;
  }
}

function startServerPolling(context: vscode.ExtensionContext): void {
  stopServerPolling();
  if (!client) return;

  const config = vscode.workspace.getConfiguration('sharedSynapse');
  const syncEnabled = config.get<boolean>('syncEnabled', true);
  if (!syncEnabled) return;

  const intervalSeconds = Math.max(15, config.get<number>('serverCheckIntervalSeconds', 60));
  serverPollTimer = setInterval(() => {
    void checkForServerChanges(context);
  }, intervalSeconds * 1000);
}

async function checkForServerChanges(context: vscode.ExtensionContext): Promise<void> {
  if (!client) return;
  try {
    await client.healthCheck();
    const synapses = await client.listSynapses();
    const snapshot = getSynapseSnapshot(synapses);

    if (lastServerSnapshot === null) {
      lastServerSnapshot = snapshot;
      return;
    }

    if (snapshot === lastServerSnapshot) {
      return;
    }

    if (snapshot === lastPromptedSnapshot) {
      return;
    }

    lastPromptedSnapshot = snapshot;
    const choice = await vscode.window.showInformationMessage(
      'Shared Synapse server state changed. Sync now?',
      'Sync Now',
      'Later',
    );

    if (choice === 'Sync Now') {
      await syncFromServer('silent');
      startServerPolling(context);
    }
  } catch {
    setStatusBar('disconnected');
  }
}

async function toggleSyncEnabled(): Promise<void> {
  const config = vscode.workspace.getConfiguration('sharedSynapse');
  const current = config.get<boolean>('syncEnabled', true);
  const next = !current;
  await config.update('syncEnabled', next, vscode.ConfigurationTarget.Global);
  setStatusBar(connectionState, currentActiveSynapses);
  vscode.window.showInformationMessage(`Shared Synapse background sync ${next ? 'enabled' : 'disabled'}.`);
}

function getConfigurationState(): {
  serverUrl: string;
  dashboardUrl: string;
  localBackendPath: string;
  localSyncPath: string;
  autoConnect: boolean;
  syncWorkspaceExtensions: boolean;
  syncEnabled: boolean;
  pullResourcesToWorkspace: boolean;
  serverCheckIntervalSeconds: number;
} {
  const config = vscode.workspace.getConfiguration('sharedSynapse');
  return {
    serverUrl: config.get<string>('serverUrl', ''),
    dashboardUrl: config.get<string>('dashboardUrl', ''),
    localBackendPath: config.get<string>('localBackendPath', ''),
    localSyncPath: config.get<string>('localSyncPath', '.agents'),
    autoConnect: config.get<boolean>('autoConnect', true),
    syncWorkspaceExtensions: config.get<boolean>('syncWorkspaceExtensions', true),
    syncEnabled: config.get<boolean>('syncEnabled', true),
    pullResourcesToWorkspace: config.get<boolean>('pullResourcesToWorkspace', true),
    serverCheckIntervalSeconds: config.get<number>('serverCheckIntervalSeconds', 60),
  };
}

function getWorkspaceRootPath(): string | null {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? null;
}

function sanitizeFileName(value: string): string {
  return value.replace(/[^a-zA-Z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || 'resource';
}

function didSyncedSkillFilesChange(previousFiles: string[], nextFiles: string[]): boolean {
  const isSkillFile = (filePath: string): boolean => (
    filePath.includes('/skills/') ||
    filePath.includes('\\skills\\') ||
    filePath.endsWith('/SKILL.md') ||
    filePath.endsWith('\\SKILL.md') ||
    filePath.endsWith('.agent.md')
  );

  const previousSkillFiles = previousFiles.filter(isSkillFile).sort();
  const nextSkillFiles = nextFiles.filter(isSkillFile).sort();
  if (previousSkillFiles.length !== nextSkillFiles.length) {
    return true;
  }
  for (let index = 0; index < previousSkillFiles.length; index += 1) {
    if (previousSkillFiles[index] !== nextSkillFiles[index]) {
      return true;
    }
  }
  return false;
}

function getUserAgentsRootPath(): string {
  return path.join(os.homedir(), '.agents');
}

function getUserPromptsAgentsPath(): string {
  return path.join(os.homedir(), 'Library', 'Application Support', 'Code', 'User', 'prompts', 'agents');
}

function normalizeSupportingPath(relativePath: string): string | null {
  const normalized = relativePath.replace(/\\/g, '/').trim();
  if (!normalized || normalized.startsWith('/') || normalized.includes('..')) {
    return null;
  }
  return normalized;
}

async function removeIfFile(filePath: string): Promise<void> {
  try {
    const stat = await fs.stat(filePath);
    if (stat.isFile()) {
      await fs.rm(filePath, { force: true });
    }
  } catch {
    // no-op when file does not exist
  }
}

async function prepareSkillPackageDirectory(skillsParentDir: string, skillId: string): Promise<string> {
  const packageRoot = path.join(skillsParentDir, skillId);

  // Migrate legacy flat-file layouts to package directory layout.
  await removeIfFile(path.join(skillsParentDir, `${skillId}.md`));
  await removeIfFile(path.join(skillsParentDir, skillId));

  await fs.mkdir(packageRoot, { recursive: true });
  return packageRoot;
}

/** Build skill package content for SKILL.md. */
function buildAgentFileContent(detail: { id: string; name: string; description: string; content: string }): string {
  const frontmatter = [
    '---',
    `name: ${JSON.stringify(detail.id)}`,
    `description: ${JSON.stringify(detail.description ?? '')}`,
    '---',
    '',
  ].join('\n');
  return `${frontmatter}${detail.content.trim()}\n`;
}

/** Build a VS Code Copilot user-agent file copy for a skill. */
function buildCopilotAgentFileContent(detail: { id: string; name: string; description: string; content: string }): string {
  const frontmatter = [
    '---',
    `description: ${JSON.stringify(detail.description ?? '')}`,
    '---',
    '',
  ].join('\n');
  return `${frontmatter}${detail.content.trim()}\n`;
}

/** Build a .instructions.md file for a rule (VS Code Copilot). */
function buildCopilotInstructionsContent(detail: { id: string; name: string; description: string; content: string }): string {
  const frontmatter = [
    '---',
    `description: ${JSON.stringify(detail.description ?? '')}`,
    'applyTo: "**/*"',
    '---',
    '',
  ].join('\n');
  return `${frontmatter}${detail.content.trim()}\n`;
}

/** Build a .mdc file for a rule (Cursor). */
function buildCursorRuleContent(detail: { id: string; name: string; description: string; content: string }): string {
  const frontmatter = [
    '---',
    `description: ${JSON.stringify(detail.description ?? '')}`,
    'globs: "**/*"',
    'alwaysApply: true',
    '---',
    '',
  ].join('\n');
  return `${frontmatter}${detail.content.trim()}\n`;
}

/** Build a Cursor rule copy for a skill so Cursor can ingest skill guidance too. */
function buildCursorSkillContent(detail: { id: string; name: string; description: string; content: string }): string {
  const frontmatter = [
    '---',
    `description: ${JSON.stringify(detail.description ?? '')}`,
    'globs: "**/*"',
    'alwaysApply: false',
    '---',
    '',
  ].join('\n');
  return `${frontmatter}${detail.content.trim()}\n`;
}

/**
 * Read the current contents of a file (or null if it doesn't exist),
 * record it in workspaceState as the backup if not already backed up,
 * then write the new content.
 */
async function backupAndWrite(filePath: string, newContent: string, ctx: vscode.ExtensionContext): Promise<void> {
  const backups = ctx.workspaceState.get<Record<string, string | null>>(BACKUP_STATE_KEY, {});
  if (!(filePath in backups)) {
    let original: string | null = null;
    try {
      original = await fs.readFile(filePath, 'utf8');
    } catch {
      original = null;
    }
    backups[filePath] = original;
    await ctx.workspaceState.update(BACKUP_STATE_KEY, backups);
  }
  await fs.writeFile(filePath, newContent, 'utf8');
}

/**
 * Restore all files that were backed up before the last sync.
 * Files that did not exist before the sync are deleted; others are written back.
 */
async function restoreBackedUpFiles(ctx: vscode.ExtensionContext): Promise<void> {
  const backups = ctx.workspaceState.get<Record<string, string | null>>(BACKUP_STATE_KEY, {});
  const entries = Object.entries(backups);
  if (entries.length === 0) return;
  for (const [filePath, originalContent] of entries) {
    try {
      if (originalContent === null) {
        await fs.rm(filePath, { force: true });
      } else {
        await fs.writeFile(filePath, originalContent, 'utf8');
      }
    } catch {
      // best-effort per file
    }
  }
  await ctx.workspaceState.update(BACKUP_STATE_KEY, {});
}

async function syncActiveResourcesToWorkspace(
  synapseClient: SynapseClient,
  activeSynapseNames: string[],
): Promise<void> {
  const workspaceRoot = getWorkspaceRootPath();
  if (!workspaceRoot) {
    lastLocalSyncSummary = 'No workspace folder is open, so resources were not written locally.';
    return;
  }

  if (!extensionContext) return;
  const ctx = extensionContext;

  const { localSyncPath } = getConfigurationState();
  const syncRoot = path.join(workspaceRoot, localSyncPath || '.agents');
  // .agents for synced workspace artifacts and tools; .cursor/rules for Cursor-compatible rule copies.
  // Also mirror skills/rules into the user-level ~/.agents so Copilot can pick them up globally.
  const agentsSkillsDir = path.join(syncRoot, 'skills');
  const agentsInstructionsDir = path.join(syncRoot, 'instructions');
  const cursorRulesDir = path.join(workspaceRoot, '.cursor', 'rules');
  const toolsDir = path.join(syncRoot, 'tools');
  const userAgentsRoot = getUserAgentsRootPath();
  const userSkillsDir = path.join(userAgentsRoot, 'skills');
  const userInstructionsDir = path.join(userAgentsRoot, 'instructions');
  const userPromptsAgentsDir = getUserPromptsAgentsPath();

  await Promise.all([
    fs.mkdir(agentsSkillsDir, { recursive: true }),
    fs.mkdir(agentsInstructionsDir, { recursive: true }),
    fs.mkdir(cursorRulesDir, { recursive: true }),
    fs.mkdir(toolsDir, { recursive: true }),
    fs.mkdir(userSkillsDir, { recursive: true }),
    fs.mkdir(userInstructionsDir, { recursive: true }),
    fs.mkdir(userPromptsAgentsDir, { recursive: true }),
  ]);

  // Load previous manifest to know which synced files may now be stale
  const manifestPath = path.join(syncRoot, 'manifest.json');
  let previousFiles: string[] = [];
  try {
    const raw = await fs.readFile(manifestPath, 'utf8');
    previousFiles = JSON.parse(raw).files ?? [];
  } catch {
    previousFiles = [];
  }

  // Collect all resources across active synapses (deduplicate by id)
  const resourceMap = new Map<string, { resourceType: 'skill' | 'rule' | 'tool'; resourceId: string }>();
  for (const synapseName of activeSynapseNames) {
    const grouped = await synapseClient.getSynapseResources(synapseName);
    for (const resource of grouped.skills ?? []) {
      resourceMap.set(`skill:${resource.id}`, { resourceType: 'skill', resourceId: resource.id });
    }
    for (const resource of grouped.rules ?? []) {
      resourceMap.set(`rule:${resource.id}`, { resourceType: 'rule', resourceId: resource.id });
    }
    for (const resource of grouped.tools ?? []) {
      resourceMap.set(`tool:${resource.id}`, { resourceType: 'tool', resourceId: resource.id });
    }
  }

  const nextFiles: string[] = [];
  const counts = { skill: 0, rule: 0, tool: 0 };

  const writeSkillBundleSupportFiles = async (
    targetSkillRoot: string,
    supportingFiles: { path: string; content: string }[] | undefined,
  ): Promise<void> => {
    if (!supportingFiles?.length) {
      return;
    }
    for (const file of supportingFiles) {
      const safeRelativePath = normalizeSupportingPath(file.path);
      if (!safeRelativePath) {
        continue;
      }
      const targetPath = path.join(targetSkillRoot, safeRelativePath);
      await fs.mkdir(path.dirname(targetPath), { recursive: true });
      await backupAndWrite(targetPath, file.content, ctx);
      nextFiles.push(targetPath);
    }
  };

  for (const resource of resourceMap.values()) {
    const detail = await synapseClient.getResourceDetail(resource.resourceType, resource.resourceId);
    const safeName = sanitizeFileName(detail.id);

    if (resource.resourceType === 'skill') {
      // Write skills as package dirs with SKILL.md so .agents skill loaders can detect them.
      const workspaceSkillRoot = await prepareSkillPackageDirectory(agentsSkillsDir, safeName);
      const skillPath = path.join(workspaceSkillRoot, 'SKILL.md');
      await backupAndWrite(skillPath, buildAgentFileContent(detail), ctx);
      nextFiles.push(skillPath);
      await writeSkillBundleSupportFiles(workspaceSkillRoot, detail.supporting_files);

      const userSkillRoot = await prepareSkillPackageDirectory(userSkillsDir, safeName);
      const userSkillPath = path.join(userSkillRoot, 'SKILL.md');
      await backupAndWrite(userSkillPath, buildAgentFileContent(detail), ctx);
      nextFiles.push(userSkillPath);
      await writeSkillBundleSupportFiles(userSkillRoot, detail.supporting_files);

      // Copilot user prompt agent copy for immediate pickup by the VS Code prompt loader.
      const copilotAgentPath = path.join(userPromptsAgentsDir, `${safeName}.agent.md`);
      await backupAndWrite(copilotAgentPath, buildCopilotAgentFileContent(detail), ctx);
      nextFiles.push(copilotAgentPath);

      // Cursor skill mirror as .mdc rule file.
      const cursorSkillPath = path.join(cursorRulesDir, `skill-${safeName}.mdc`);
      await backupAndWrite(cursorSkillPath, buildCursorSkillContent(detail), ctx);
      nextFiles.push(cursorSkillPath);
      counts.skill += 1;

    } else if (resource.resourceType === 'rule') {
      // Write rules to .agents/instructions as markdown.
      const instructionsPath = path.join(agentsInstructionsDir, `${safeName}.md`);
      await backupAndWrite(instructionsPath, buildCopilotInstructionsContent(detail), ctx);
      nextFiles.push(instructionsPath);

      const userInstructionsPath = path.join(userInstructionsDir, `${safeName}.md`);
      await backupAndWrite(userInstructionsPath, buildCopilotInstructionsContent(detail), ctx);
      nextFiles.push(userInstructionsPath);

      // Write as .mdc in .cursor/rules/ (Cursor)
      const mdcPath = path.join(cursorRulesDir, `${safeName}.mdc`);
      await backupAndWrite(mdcPath, buildCursorRuleContent(detail), ctx);
      nextFiles.push(mdcPath);
      counts.rule += 1;

    } else {
      // Tools: write raw JSON under .agents/tools/
      const toolPath = path.join(toolsDir, `${safeName}.json`);
      await backupAndWrite(toolPath, `${detail.content.trim()}\n`, ctx);
      nextFiles.push(toolPath);
      counts.tool += 1;
    }
  }

  // Remove stale synced files from previous sync that are no longer active
  const staleFiles = previousFiles.filter((f) => !nextFiles.includes(f));
  for (const staleFile of staleFiles) {
    // Restore from backup (or delete if no prior content) rather than blindly removing
    const backups = ctx.workspaceState.get<Record<string, string | null>>(BACKUP_STATE_KEY, {});
    if (staleFile in backups) {
      const original = backups[staleFile];
      try {
        if (original === null) {
          await fs.rm(staleFile, { force: true });
        } else {
          await fs.writeFile(staleFile, original, 'utf8');
        }
      } catch { /* best-effort */ }
      delete backups[staleFile];
      await ctx.workspaceState.update(BACKUP_STATE_KEY, backups);
    } else {
      await fs.rm(staleFile, { force: true });
    }
  }

  const manifest = {
    synced_at: new Date().toISOString(),
    active_synapses: activeSynapseNames,
    files: nextFiles,
    counts,
  };
  await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2), 'utf8');
  const skillFilesChanged = didSyncedSkillFilesChange(previousFiles, nextFiles);
  const skillsDisplayPath = path.relative(workspaceRoot, agentsSkillsDir) || agentsSkillsDir;
  const instructionsDisplayPath = path.relative(workspaceRoot, agentsInstructionsDir) || agentsInstructionsDir;
  const cursorDisplayPath = path.relative(workspaceRoot, cursorRulesDir) || cursorRulesDir;
  const toolsDisplayPath = path.relative(workspaceRoot, toolsDir) || toolsDir;
  lastLocalSyncSummary = `Synced ${counts.skill} skills → ${skillsDisplayPath} and ~/.agents/skills, ${counts.rule} rules → ${instructionsDisplayPath} and ~/.agents/instructions (copied to ${cursorDisplayPath}), ${counts.tool} tools → ${toolsDisplayPath}.`;

}

function setStatusBar(state: 'connected' | 'disconnected', activeSynapses: string[] = []): void {
  const wasConnected = connectionState === 'connected';
  connectionState = state;
  currentActiveSynapses = [...activeSynapses];
  const syncEnabled = vscode.workspace.getConfiguration('sharedSynapse').get<boolean>('syncEnabled', true);
  const syncLabel = syncEnabled ? 'Sync On' : 'Sync Off';

  if (state === 'connected') {
    const synapseLabel = activeSynapses.length > 0 ? ` [${activeSynapses.join(', ')}]` : '';
    statusBarItem.text = `$(brain) Synapse${synapseLabel} · ${syncLabel}`;
    statusBarItem.tooltip = `Shared Synapse – connected${synapseLabel}. Background sync: ${syncLabel}. Click to activate a synapse.`;
    statusBarItem.backgroundColor = undefined;
  } else {
    statusBarItem.text = `$(brain) Synapse (disconnected) · ${syncLabel}`;
    statusBarItem.tooltip = `Shared Synapse – not connected. Background sync: ${syncLabel}. Click to set up.`;
    statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
  }
  statusBarItem.show();
  // When transitioning from connected → disconnected, restore pre-sync files
  if (wasConnected && state === 'disconnected' && extensionContext) {
    restoreBackedUpFiles(extensionContext).catch(() => {});
  }
  sidebarProvider?.update(state, currentActiveSynapses, syncEnabled, lastLocalSyncSummary, getConfigurationState());
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
