import { execFile } from "node:child_process";

import { CliError, ProtocolError } from "./errors.js";
import { parseDecisionJson } from "./validate.js";
import type { GoldenBoyDecision } from "./types.js";

export interface GoldenBoyClientOptions {
  /** Path to the `goldenboy` executable. Defaults to `"goldenboy"`,
   * resolved via PATH — the same binary `pip install goldenboy` installs. */
  binaryPath?: string;
  /** Working directory the CLI runs in (its `.goldenboy/` state — config,
   * checkpoint, history — is resolved relative to this). Defaults to the
   * Node process's own cwd. */
  cwd?: string;
  /** Milliseconds before a CLI call is killed. Default 15000. */
  timeoutMs?: number;
}

export interface AnalyzeOptions {
  /** Mock starting budget percentage (0-100). Default 100. */
  budget?: number;
  /** Reported progress on the task, 0.0-1.0. Omit if genuinely unknown. */
  progress?: number;
}

interface RawStatus {
  remaining_percentage: number;
  usable_percentage: number;
  is_exhausted: boolean;
  source: string;
  confidence: string;
  checkpoint: { task_name: string; mode: string; deferred_units: number } | null;
}

interface RawDoctor {
  python: string;
  dependencies: Record<string, { installed: boolean; api_key_configured?: boolean }>;
  config: { ok: boolean; detail: unknown };
  checkpoint: { ok: boolean; detail: string };
}

/**
 * A thin client over the `goldenboy` CLI's `--json` output. This is
 * deliberately *not* a reimplementation of Golden Boy's cost estimation,
 * task classification, or risk logic in TypeScript — every method here
 * spawns the real Python CLI and parses its structured output through the
 * same protocol validation (`parseDecisionJson`) the rest of this SDK
 * exposes. If you need Golden Boy's actual decision logic, this is the
 * only correct way to get it from a non-Python agent; there is no
 * separate JS implementation of the decision engine to drift out of sync
 * with the Python one.
 */
export class GoldenBoyClient {
  private readonly binaryPath: string;
  private readonly cwd: string | undefined;
  private readonly timeoutMs: number;

  constructor(options: GoldenBoyClientOptions = {}) {
    this.binaryPath = options.binaryPath ?? "goldenboy";
    this.cwd = options.cwd;
    this.timeoutMs = options.timeoutMs ?? 15_000;
  }

  private run(args: string[]): Promise<string> {
    return new Promise((resolve, reject) => {
      execFile(
        this.binaryPath,
        args,
        { cwd: this.cwd, timeout: this.timeoutMs, maxBuffer: 16 * 1024 * 1024 },
        (error, stdout, stderr) => {
          if (error) {
            const exitCode = typeof error.code === "number" ? error.code : null;
            if ((error as NodeJS.ErrnoException).code === "ENOENT") {
              reject(
                new CliError(
                  `Could not find the '${this.binaryPath}' executable. Is Golden Boy installed ` +
                    "('pip install goldenboy') and on PATH? Pass { binaryPath } to GoldenBoyClient otherwise.",
                  null,
                  stderr,
                ),
              );
              return;
            }
            reject(
              new CliError(
                `'${this.binaryPath} ${args.join(" ")}' exited with an error: ${stderr.trim() || error.message}`,
                exitCode,
                stderr,
              ),
            );
            return;
          }
          resolve(stdout);
        },
      );
    });
  }

  /** Runs `goldenboy analyze <task> --json` and returns the parsed,
   * protocol-validated `GoldenBoyDecision`. */
  async analyze(task: string, options: AnalyzeOptions = {}): Promise<GoldenBoyDecision> {
    const args = ["analyze", task, "--json"];
    if (options.budget !== undefined) args.push("--budget", String(options.budget));
    if (options.progress !== undefined) args.push("--progress", String(options.progress));
    const stdout = await this.run(args);
    return parseDecisionJson(stdout);
  }

  /** Runs `goldenboy status --json`. */
  async status(budget = 100): Promise<RawStatus> {
    const stdout = await this.run(["status", "--budget", String(budget), "--json"]);
    return this.parseJsonOr("status", stdout) as RawStatus;
  }

  /** Runs `goldenboy doctor --json`. Never includes API key *values* —
   * only whether one is configured (`dependencies.<name>.api_key_configured`),
   * matching the CLI's own guarantee. */
  async doctor(): Promise<RawDoctor> {
    const stdout = await this.run(["doctor", "--json"]);
    return this.parseJsonOr("doctor", stdout) as RawDoctor;
  }

  /** Runs `goldenboy validate --json`. Throws `CliError` if the CLI itself
   * exited non-zero (a broken config, or POOR local data quality). */
  async validate(): Promise<unknown> {
    const stdout = await this.run(["validate", "--json"]);
    return this.parseJsonOr("validate", stdout);
  }

  /** Runs `goldenboy replay --json` (optionally against an exported
   * dataset file instead of the default local history). */
  async replay(datasetPath?: string): Promise<unknown> {
    const args = ["replay", "--json"];
    if (datasetPath) args.push("--dataset", datasetPath);
    const stdout = await this.run(args);
    return this.parseJsonOr("replay", stdout);
  }

  private parseJsonOr(command: string, text: string): unknown {
    try {
      return JSON.parse(text);
    } catch (e) {
      throw new ProtocolError(`'goldenboy ${command} --json' did not print valid JSON: ${(e as Error).message}`);
    }
  }
}
