/** Mirrors `goldenboy.protocol.ProtocolError` / `goldenboy.core.errors.GoldenBoyError`:
 * a specific, actionable error for something this SDK deliberately rejects
 * (malformed payload, incompatible schema version, non-zero CLI exit),
 * never an unlabeled generic Error. */
export class GoldenBoyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "GoldenBoyError";
  }
}

export class ProtocolError extends GoldenBoyError {
  constructor(message: string) {
    super(message);
    this.name = "ProtocolError";
  }
}

/** The `goldenboy` CLI exited non-zero, or could not be found/spawned. */
export class CliError extends GoldenBoyError {
  readonly exitCode: number | null;
  readonly stderr: string;

  constructor(message: string, exitCode: number | null, stderr: string) {
    super(message);
    this.name = "CliError";
    this.exitCode = exitCode;
    this.stderr = stderr;
  }
}
