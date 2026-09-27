import {
  Controller,
  Get,
  Headers,
  HttpCode,
  HttpException,
  HttpStatus,
  Logger,
  Post,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PipelineHealthService } from './pipeline-health.service';
import { PipelineRunnerService } from './pipeline-runner.service';
import { PipelineSchedulerService } from './pipeline-scheduler.service';

/**
 * Mirrors Flask `/api/pipeline/health` and `/api/pipeline/run-now`.
 *
 * run-now uses the cron-style `X-Pipeline-Admin-Token` header (NOT the admin
 * HMAC session), exactly like Flask, so the existing GitHub Actions keep-alive
 * keeps working after cutover.
 */
@Controller('api/pipeline')
export class PipelineController {
  private readonly logger = new Logger(PipelineController.name);

  constructor(
    private readonly config: ConfigService,
    private readonly health: PipelineHealthService,
    private readonly runner: PipelineRunnerService,
    private readonly scheduler: PipelineSchedulerService,
  ) {}

  @Get('health')
  async pipelineHealth() {
    try {
      return await this.health.publicSnapshot();
    } catch (err) {
      this.logger.error(
        'pipeline health failed',
        err instanceof Error ? err.stack : String(err),
      );
      throw new HttpException(
        { scheduler: 'unknown', status: 'unhealthy', error: 'unavailable' },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }

  @Post('run-now')
  @HttpCode(HttpStatus.ACCEPTED)
  runNow(@Headers('x-pipeline-admin-token') provided?: string) {
    const allowed = new Set(
      [
        (process.env.PIPELINE_ADMIN_TOKEN || '').trim(),
        (process.env.ADMIN_PASSWORD || '').trim(),
        this.config.get<string>('pipeline.adminToken') || '',
      ].filter(Boolean),
    );

    if (!allowed.size) {
      throw new HttpException(
        {
          status: 'disabled',
          error: 'PIPELINE_ADMIN_TOKEN is not configured',
          hint: 'Set PIPELINE_ADMIN_TOKEN (or ADMIN_PASSWORD) on Render, mirror in GitHub Actions secrets.',
        },
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }

    if (!allowed.has(provided || '')) {
      throw new HttpException(
        { status: 'forbidden', error: 'Invalid admin token' },
        HttpStatus.FORBIDDEN,
      );
    }

    if (
      !this.scheduler.isRunning() &&
      !this.config.get<boolean>('pipeline.onApi')
    ) {
      throw new HttpException(
        { status: 'error', error: 'Pipeline scheduler is not enabled' },
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }

    // Same canonical runner + same Mongo lock as the scheduler.
    this.runner.runDetached({
      trigger: 'manual',
      nextRunIso: () => this.scheduler.nextRunIso(),
    });
    return { status: 'accepted', message: 'Pipeline cycle triggered' };
  }
}
