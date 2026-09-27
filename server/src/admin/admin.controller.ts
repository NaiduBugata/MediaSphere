import {
  Controller,
  Get,
  HttpException,
  HttpStatus,
  Logger,
  Param,
  Post,
  Query,
  Res,
} from '@nestjs/common';
import type { Response } from 'express';
import { AdminFetchService } from './fetch/admin-fetch.service';
import { AdminOnly } from '../common/decorators/admin.decorator';

/**
 * Mirrors Flask `admin_bp` fetch/scheduler/health routes.
 *
 * Route order matters: `fetch/status` and `fetch/history` are declared before
 * `fetch/:runId` so the literal paths win (Flask's separate rules do the same).
 */
@Controller('api/admin')
@AdminOnly()
export class AdminController {
  private readonly logger = new Logger(AdminController.name);

  constructor(private readonly fetch: AdminFetchService) {}

  @Get('fetch/status')
  async fetchStatus() {
    try {
      return await this.fetch.buildAdminStatus();
    } catch (err) {
      this.logger.error(
        'admin fetch status failed',
        err instanceof Error ? err.stack : String(err),
      );
      throw new HttpException(
        { error: 'unavailable', headline: 'unknown' },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }

  @Get('fetch/history')
  async fetchHistory(
    @Query('limit') limitRaw?: string,
    @Query('status') status?: string,
    @Query('trigger') trigger?: string,
    @Query('q') q?: string,
  ) {
    // Flask: int(request.args.get("limit", "50")) with ValueError -> 50
    let limit = 50;
    if (limitRaw !== undefined) {
      const parsed = parseInt(limitRaw, 10);
      limit = Number.isNaN(parsed) ? 50 : parsed;
    }
    const runs = await this.fetch.listHistory({
      limit,
      status: status ?? null,
      trigger: trigger ?? null,
      q: q ?? null,
    });
    return {
      runs,
      count: runs.length,
      stats: await this.fetch.historyStats(),
    };
  }

  /** 202 when accepted, 409 when the Mongo lock is already held. */
  @Post('fetch/trigger')
  async fetchTrigger(@Res({ passthrough: true }) res: Response) {
    try {
      const result = await this.fetch.triggerFetch({ trigger: 'manual' });
      res.status(result.accepted ? HttpStatus.ACCEPTED : HttpStatus.CONFLICT);
      return result;
    } catch (err) {
      this.logger.error(
        'admin fetch trigger failed',
        err instanceof Error ? err.stack : String(err),
      );
      throw new HttpException(
        {
          accepted: false,
          error: (err instanceof Error ? err.message : String(err)).slice(
            0,
            200,
          ),
        },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }

  @Post('fetch/retry/:runId')
  async fetchRetry(
    @Param('runId') runId: string,
    @Res({ passthrough: true }) res: Response,
  ) {
    const parent = await this.fetch.getRun(runId);
    if (!parent) {
      throw new HttpException({ error: 'Run not found' }, HttpStatus.NOT_FOUND);
    }
    try {
      const result = await this.fetch.triggerFetch({
        trigger: 'retry',
        parentRunId: runId,
      });
      res.status(result.accepted ? HttpStatus.ACCEPTED : HttpStatus.CONFLICT);
      return result;
    } catch (err) {
      this.logger.error(
        'admin fetch retry failed',
        err instanceof Error ? err.stack : String(err),
      );
      throw new HttpException(
        {
          accepted: false,
          error: (err instanceof Error ? err.message : String(err)).slice(
            0,
            200,
          ),
        },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }

  @Get('fetch/:runId')
  async fetchDetail(@Param('runId') runId: string) {
    const row = await this.fetch.getRun(runId);
    if (!row) {
      throw new HttpException({ error: 'Run not found' }, HttpStatus.NOT_FOUND);
    }
    return row;
  }

  @Get('scheduler/status')
  async schedulerStatus() {
    const status = await this.fetch.buildAdminStatus();
    return {
      scheduler: status.scheduler ?? null,
      next_run: status.next_run ?? null,
      last_success: status.last_success ?? null,
      interval_hours: status.interval_hours ?? null,
      delay_tolerance_minutes: status.delay_tolerance_minutes ?? null,
      scheduler_delayed: status.scheduler_delayed ?? null,
      delay_seconds: status.delay_seconds ?? null,
      pipeline_on_api: status.pipeline_on_api ?? null,
      headline: status.headline ?? null,
    };
  }

  @Get('health')
  async adminHealth() {
    return this.fetch.buildHealthCheck();
  }
}
