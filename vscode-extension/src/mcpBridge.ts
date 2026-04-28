/**
 * MCP stdio bridge.
 *
 * Spawns `python -m src.mcp_server.server` from the local backend directory so that
 * MCP-aware clients (GitHub Copilot, Cursor, Continue) can attach to Shared Synapse
 * without a hosted server.
 *
 * The spawned process communicates over stdio in the MCP JSON-RPC protocol.
 */
import * as cp from 'child_process';
import * as path from 'path';
import * as vscode from 'vscode';

export class McpBridge {
  private backendPath: string;
  private process: cp.ChildProcess | null = null;
  private outputChannel: vscode.OutputChannel;

  constructor(backendPath: string) {
    this.backendPath = backendPath;
    this.outputChannel = vscode.window.createOutputChannel('Shared Synapse MCP');
  }

  start(): void {
    if (this.process) {
      this.outputChannel.appendLine('[McpBridge] Already running.');
      return;
    }

    this.outputChannel.appendLine(`[McpBridge] Starting from ${this.backendPath}`);
    this.outputChannel.show(true);

    this.process = cp.spawn('python', ['-m', 'src.mcp_server.server'], {
      cwd: this.backendPath,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env },
    });

    this.process.stdout?.on('data', (data: Buffer) => {
      this.outputChannel.append(data.toString());
    });

    this.process.stderr?.on('data', (data: Buffer) => {
      this.outputChannel.append(`[stderr] ${data.toString()}`);
    });

    this.process.on('close', (code) => {
      this.outputChannel.appendLine(`[McpBridge] Process exited with code ${code}`);
      this.process = null;
    });

    this.process.on('error', (err) => {
      this.outputChannel.appendLine(`[McpBridge] Error: ${err.message}`);
      vscode.window.showErrorMessage(`MCP bridge failed: ${err.message}`);
      this.process = null;
    });
  }

  stop(): void {
    if (this.process) {
      this.process.kill();
      this.process = null;
      this.outputChannel.appendLine('[McpBridge] Stopped.');
    }
  }

  get isRunning(): boolean {
    return this.process !== null;
  }
}
