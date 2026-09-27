import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Document } from 'mongodb';
import { PipelineStateService } from './pipeline-state.service';
import { PipelineLockService, LockSummary } from './pipeline-lock.service';
import { PipelineSchedulerService } from './pipeline-scheduler.service';

export interface HealthSnapshot {
  scheduler: string;
  last_run: unknown;
  last_success: unknown;
  last_failure: unknown;
  next_run: unknown;
  status: unknown;
  articles_processed: number | null;
  last_duration_seconds: unknown;
  articles_inserted_last_run: unknown;
  lock: LockSummary | Record<string, never>;
  data_revision: unknown;
  sources: Record<string, string>;
  last_sakshi_run: unknown;
  last_sakshi_articles: unknown;
  sakshi: Record<string, unknown>;
}

/** Python `value or 0`. */
function orZero(value: unknown): unknown {
  return value ? value : 0;
}

/**
 * Port of Flask `pipeline_scheduler.health_snapshot` — sanitized, no secrets or
 * stack traces.
 */
@Injectable()
export class PipelineHealthService {
  private readonly logger = new Logger(PipelineHealthService.name);

  constructor(
    private readonly config: ConfigService,
    private readonly state: PipelineStateService,
    private readonly lock: PipelineLockService,
    private readonly scheduler: PipelineSchedulerService,
  ) {}

  /** Flask `_source_health`. */
  private sourceHealth(
    name: string,
    enabled: boolean,
    state: Document,
  ): string {
    if (!enabled) return 'disabled';
    const errors = state[`${name}_last_errors`];
    if (Array.isArray(errors) && errors.length) return 'degraded';
    if (state.last_success || state.last_run) return 'healthy';
    return this.scheduler.isRunning() ? 'healthy' : 'stopped';
  }

  async snapshot(): Promise<HealthSnapshot> {
    let state: Document = {};
    let lock: LockSummary | Record<string, never> = {};
    let articles: number | null = null;
    try {
      state = await this.state.getState();
      lock = await this.lock.summary();
      articles = await this.state.articleCount();
    } catch (err) {
      this.logger.warn(
        'Pipeline health state unavailable: ' +
          (err instanceof Error ? err.message : String(err)),
      );
    }

    const running = this.scheduler.isRunning();
    const sources = this.config.get<{
      youtubeEnabled: boolean;
      sakshiEnabled: boolean;
    }>('pipeline.sources');

    return {
      scheduler: running ? 'running' : 'stopped',
      last_run: state.last_run ?? null,
      last_success: state.last_success ?? null,
      last_failure: state.last_failure ?? null,
      next_run: this.scheduler.nextRunIso() ?? state.next_run ?? null,
      status: state.status || (running ? 'healthy' : 'stopped'),
      articles_processed: articles,
      last_duration_seconds: state.duration_seconds ?? null,
      articles_inserted_last_run: state.articles_inserted ?? null,
      lock,
      data_revision: state.last_success || state.last_run || null,
      sources: {
        lokal: this.sourceHealth('lokal', true, state),
        youtube: this.sourceHealth(
          'youtube',
          Boolean(sources?.youtubeEnabled),
          state,
        ),
        sakshi: this.sourceHealth(
          'sakshi',
          Boolean(sources?.sakshiEnabled),
          state,
        ),
      },
      last_sakshi_run: state.last_sakshi_run ?? null,
      last_sakshi_articles: orZero(state.last_sakshi_articles),
      sakshi: {
        fetched: orZero(state.sakshi_fetched),
        accepted: orZero(state.sakshi_accepted),
        rejected: orZero(state.sakshi_rejected),
        last_run: state.last_sakshi_run ?? null,
        inserted_last_run: orZero(state.last_sakshi_articles),
        rejected_reasons: state.sakshi_rejected_reasons || {},
      },
    };
  }

  /**
   * Flask `/api/pipeline/health` post-processing: failed -> unhealthy,
   * running scheduler -> healthy.
   */
  async publicSnapshot(): Promise<HealthSnapshot> {
    const snapshot = await this.snapshot();
    if (snapshot.status === 'failed') {
      snapshot.status = 'unhealthy';
    } else if (snapshot.scheduler === 'running') {
      snapshot.status = 'healthy';
    }
    return snapshot;
  }
}
