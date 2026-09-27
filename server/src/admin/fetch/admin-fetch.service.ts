import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PipelineHealthService } from '../../pipeline/pipeline-health.service';
import { PipelineHistoryService } from '../../pipeline/pipeline-history.service';
import { PipelineLockService } from '../../pipeline/pipeline-lock.service';
import {
  PipelineRunnerService,
  newRunId,
} from '../../pipeline/pipeline-runner.service';
import { PipelineSchedulerService } from '../../pipeline/pipeline-scheduler.service';
import { PipelineStateService } from '../../pipeline/pipeline-state.service';
import { agoSeconds } from '../../common/utils/iso-time';

export interface TriggerResult {
  accepted: boolean;
  status: string;
  message: string;
  run_id?: string;
  trigger?: string;
  lock?: unknown;
}

/**
 * Port of Flask `server/admin/fetch_service.py`.
 * Read paths aggregate `scheduler_state` + `pipeline_history`; the write path
 * delegates to the canonical PipelineRunnerService.
 */
@Injectable()
export class AdminFetchService {
  constructor(
    private readonly config: ConfigService,
    private readonly state: PipelineStateService,
    private readonly history: PipelineHistoryService,
    private readonly lock: PipelineLockService,
    private readonly health: PipelineHealthService,
    private readonly runner: PipelineRunnerService,
    private readonly scheduler: PipelineSchedulerService,
  ) {}

  fetchIntervalHours(): number {
    return this.config.get<number>('pipeline.fetchIntervalHours') || 1;
  }

  delayToleranceMinutes(): number {
    return this.config.get<number>('pipeline.delayToleranceMinutes') || 30;
  }

  listHistory(options: {
    limit?: number;
    status?: string | null;
    trigger?: string | null;
    q?: string | null;
  }) {
    return this.history.list(options);
  }

  getRun(runId: string) {
    return this.history.getRun(runId);
  }

  historyStats() {
    return this.history.stats();
  }

  /** Flask `build_admin_status`. */
  async buildAdminStatus(): Promise<Record<string, unknown>> {
    const snapshot = await this.health.snapshot();
    const lock = (snapshot.lock || {}) as { held?: boolean };
    const lastSuccess = snapshot.last_success;
    const lastFailure = snapshot.last_failure;
    const intervalH = this.fetchIntervalHours();
    const toleranceM = this.delayToleranceMinutes();
    const ageS = agoSeconds(lastSuccess);
    const intervalS = intervalH * 3600;

    let headline: string;
    let delayed = false;
    let delaySeconds = 0;
    if (ageS === null) {
      headline = 'never_fetched';
    } else if (lock.held || snapshot.status === 'running') {
      headline = 'running';
    } else if (
      snapshot.status === 'failed' &&
      lastFailure &&
      (!lastSuccess || String(lastFailure) > String(lastSuccess))
    ) {
      headline = 'failed';
    } else if (ageS > intervalS + toleranceM * 60) {
      headline = 'scheduler_delayed';
      delayed = true;
      delaySeconds = ageS - intervalS;
    } else {
      headline = 'healthy';
    }

    let freshness = 'unknown';
    if (ageS !== null) {
      if (ageS <= intervalS) freshness = 'fresh';
      else if (ageS <= intervalS + toleranceM * 60) freshness = 'aging';
      else freshness = 'stale';
    }

    const stats = await this.historyStats();
    const alerts: Array<{ level: string; code: string; message: string }> = [];
    if (headline === 'failed') {
      alerts.push({
        level: 'critical',
        code: 'fetch_failed',
        message: 'The latest automatic/manual fetch failed.',
      });
    }
    if (delayed || headline === 'scheduler_delayed') {
      alerts.push({
        level: 'warning',
        code: 'scheduler_delayed',
        message:
          `No successful fetch within the expected ${formatG(intervalH)}h interval ` +
          `(+${String(toleranceM)}m tolerance).`,
      });
    }
    if (headline === 'running') {
      alerts.push({
        level: 'info',
        code: 'fetch_running',
        message: 'A fetch operation is currently running.',
      });
    }
    if (headline === 'never_fetched') {
      alerts.push({
        level: 'warning',
        code: 'never_fetched',
        message: 'No successful fetch has been recorded yet.',
      });
    }

    return {
      headline,
      scheduler: snapshot.scheduler,
      status: snapshot.status,
      lock: snapshot.lock,
      last_run: snapshot.last_run,
      last_success: lastSuccess,
      last_failure: lastFailure,
      next_run: snapshot.next_run,
      last_duration_seconds: snapshot.last_duration_seconds,
      articles_inserted_last_run: snapshot.articles_inserted_last_run,
      articles_count: snapshot.articles_processed,
      data_revision: await this.state.getDataRevision(),
      sources: snapshot.sources,
      interval_hours: intervalH,
      delay_tolerance_minutes: toleranceM,
      data_age_seconds: ageS,
      scheduler_delayed: delayed,
      delay_seconds: delayed ? delaySeconds : 0,
      freshness,
      stats,
      alerts,
      pipeline_on_api: Boolean(this.config.get<boolean>('pipeline.onApi')),
      admin_token_configured: Boolean(
        this.config.get<string>('pipeline.adminToken'),
      ),
    };
  }

  /** Flask `build_health_check`. */
  async buildHealthCheck(): Promise<Record<string, unknown>> {
    const checks: Record<string, Record<string, unknown>> = {};
    try {
      const ping = await this.state.pingDiagnostics();
      checks.database = { ok: true, latency_ms: ping.latency_ms };
    } catch (err) {
      checks.database = {
        ok: false,
        error: (err instanceof Error ? err.message : String(err)).slice(0, 200),
      };
    }

    const onApi = Boolean(this.config.get<boolean>('pipeline.onApi'));
    checks.application = { ok: true };
    checks.scheduler = {
      ok: this.scheduler.isRunning() || !onApi,
      running: this.scheduler.isRunning(),
      pipeline_on_api: onApi,
    };

    const status = await this.buildAdminStatus();
    const age = status.data_age_seconds as number | null;
    checks.latest_data = {
      ok:
        age !== null &&
        age <=
          this.fetchIntervalHours() * 3600 + this.delayToleranceMinutes() * 60,
      age_seconds: age,
      freshness: status.freshness,
    };
    const sources = (status.sources || {}) as Record<string, string>;
    checks.data_source = {
      ok: Object.values(sources).every((v) =>
        ['healthy', 'disabled'].includes(v),
      ),
      sources,
    };

    const overall = Object.values(checks).every((c) => Boolean(c.ok));
    return { ok: overall, checks };
  }

  newRunId(): string {
    return newRunId();
  }

  /**
   * Flask `trigger_fetch` — checks the Mongo lock, stamps a pending run id, then
   * starts the canonical runner detached (Flask used a daemon thread).
   */
  async triggerFetch(options: {
    trigger: 'manual' | 'retry';
    parentRunId?: string | null;
  }): Promise<TriggerResult> {
    const lock = await this.lock.summary();
    if (lock.held) {
      return {
        accepted: false,
        status: 'already_running',
        message: 'A fetch operation is already running.',
        lock,
      };
    }

    const runId = this.newRunId();
    await this.state.updateState({
      status: 'running',
      trigger: options.trigger,
      pending_run_id: runId,
      pending_parent_run_id: options.parentRunId ?? null,
    });

    this.runner.runDetached({
      trigger: options.trigger,
      runId,
      parentRunId: options.parentRunId ?? null,
      nextRunIso: () => this.scheduler.nextRunIso(),
    });

    return {
      accepted: true,
      status: 'accepted',
      message: 'Pipeline cycle triggered',
      run_id: runId,
      trigger: options.trigger,
    };
  }
}

/** Python `f"{value:g}"` for the alert message (1.0 -> "1"). */
function formatG(value: number): string {
  if (Number.isInteger(value)) return String(value);
  return String(parseFloat(value.toPrecision(6)));
}
