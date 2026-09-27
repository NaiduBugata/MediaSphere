import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { spawn } from 'node:child_process';

export interface CycleStats {
  articles_fetched: number;
  duplicates: number;
  inserted: number;
  lokal_processed: number;
  youtube_processed: number;
  sakshi_processed: number;
  errors: string[];
}

export interface BridgeResult {
  exitCode: number;
  stats: CycleStats;
  timedOut: boolean;
  parsed: boolean;
  outputTail: string;
  command: string;
}

export function emptyStats(): CycleStats {
  return {
    articles_fetched: 0,
    duplicates: 0,
    inserted: 0,
    lokal_processed: 0,
    youtube_processed: 0,
    sakshi_processed: 0,
    errors: [],
  };
}

/**
 * Final summary line emitted by `pipeline/runner.py::run_combined_cycle`:
 *
 *   COMBINED PIPELINE CYCLE END | exit=0 | inserted=3 | duplicates=1 | fetched=9 | sakshi=2
 */
const SUMMARY_RE =
  /COMBINED PIPELINE CYCLE END \| exit=(-?\d+) \| inserted=(\d+) \| duplicates=(\d+) \| fetched=(\d+) \| sakshi=(\d+)/;

/**
 * OPTION B BRIDGE.
 *
 * Nest owns the pipeline *control plane* (auth, lock, state, history,
 * scheduler). Pipeline *execution* is still the existing Python code: we invoke
 * `python run_all_pipelines.py --once` with cwd=server/. Collectors, Groq
 * analysis, YouTube, Sakshi and notifications are therefore NOT migrated — they
 * run unchanged inside that subprocess.
 *
 * Consequence to keep in mind: the Python cycle also writes a few
 * `scheduler_state` fields itself (`last_run`, `status`, `last_success`,
 * `articles_inserted_last_run`, `articles_processed`). Nest writes the richer
 * scheduler-equivalent fields around it, and Nest's write happens last.
 */
@Injectable()
export class PythonBridgeService {
  private readonly logger = new Logger(PythonBridgeService.name);

  constructor(private readonly config: ConfigService) {}

  private cfg() {
    return {
      executable:
        this.config.get<string>('pipeline.python.executable') || 'python',
      cwd: this.config.get<string>('pipeline.python.cwd') || '',
      script:
        this.config.get<string>('pipeline.python.script') ||
        'run_all_pipelines.py',
      args: this.config.get<string[]>('pipeline.python.args') || ['--once'],
      timeoutMs:
        this.config.get<number>('pipeline.python.timeoutMs') || 45 * 60 * 1000,
    };
  }

  describe(): string {
    const c = this.cfg();
    return `${c.executable} ${c.script} ${c.args.join(' ')} (cwd=${c.cwd})`;
  }

  /** Run exactly one combined Lokal + YouTube + Sakshi cycle. Never throws. */
  async runCombinedOnce(): Promise<BridgeResult> {
    const c = this.cfg();
    const command = this.describe();
    this.logger.log(`[PYTHON_BRIDGE] spawning ${command}`);

    return new Promise<BridgeResult>((resolvePromise) => {
      let settled = false;
      let timedOut = false;
      const chunks: string[] = [];

      const child = spawn(c.executable, [c.script, ...c.args], {
        cwd: c.cwd,
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true,
      });

      const collect = (buf: Buffer) => {
        chunks.push(buf.toString('utf8'));
        // Bound memory; the cycle can log a lot.
        if (chunks.length > 4000) chunks.splice(0, chunks.length - 4000);
      };
      child.stdout?.on('data', collect);
      child.stderr?.on('data', collect);

      const timer = setTimeout(() => {
        timedOut = true;
        this.kill(child.pid);
      }, c.timeoutMs);

      const finish = (exitCode: number, extraError?: string) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        const output = chunks.join('');
        const stats = emptyStats();
        const match = SUMMARY_RE.exec(output);
        if (match) {
          stats.inserted = parseInt(match[2], 10);
          stats.duplicates = parseInt(match[3], 10);
          stats.articles_fetched = parseInt(match[4], 10);
          stats.sakshi_processed = parseInt(match[5], 10);
        }
        if (timedOut) {
          stats.errors.push(
            `python_bridge_timeout_after_ms=${String(c.timeoutMs)}`,
          );
        }
        if (extraError) stats.errors.push(extraError.slice(0, 200));
        if (exitCode !== 0 && !timedOut && !extraError) {
          stats.errors.push(`combined_cycle_exit_code=${String(exitCode)}`);
        }
        resolvePromise({
          exitCode: timedOut ? 1 : exitCode,
          stats,
          timedOut,
          parsed: Boolean(match),
          outputTail: output.slice(-4000),
          command,
        });
      };

      child.on('error', (err) => {
        this.logger.error(`[PYTHON_BRIDGE] spawn failed: ${err.message}`);
        finish(1, `python_bridge_spawn_failed: ${err.message}`);
      });
      child.on('close', (code) => {
        this.logger.log(
          `[PYTHON_BRIDGE] exited code=${String(code)} timedOut=${String(timedOut)}`,
        );
        finish(typeof code === 'number' ? code : 1);
      });
    });
  }

  private kill(pid: number | undefined): void {
    if (!pid) return;
    try {
      if (process.platform === 'win32') {
        spawn('taskkill', ['/pid', String(pid), '/T', '/F'], {
          windowsHide: true,
        });
      } else {
        process.kill(pid, 'SIGTERM');
      }
    } catch {
      /* already gone */
    }
  }
}
