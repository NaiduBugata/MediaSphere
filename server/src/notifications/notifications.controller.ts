import {
  Controller,
  Get,
  Header,
  HttpException,
  HttpStatus,
  Logger,
  Res,
} from '@nestjs/common';
import type { Response } from 'express';
import { NotificationsService } from './notifications.service';

@Controller('api/notifications')
export class NotificationsController {
  private readonly logger = new Logger(NotificationsController.name);

  constructor(private readonly notifications: NotificationsService) {}

  @Get('status')
  @Header('Cache-Control', 'no-store')
  async status(@Res({ passthrough: true }) res: Response) {
    try {
      return await this.notifications.buildStatusSnapshot();
    } catch (err) {
      this.logger.error(
        'notifications status failed',
        err instanceof Error ? err.stack : err,
      );
      res.setHeader('Cache-Control', 'no-store');
      throw new HttpException(
        {
          email: {
            enabled: false,
            configured: false,
            status: 'unknown',
            last_at: null,
            last_error: 'unavailable',
            pending_articles: 0,
            last_daily_report: null,
          },
          whatsapp: {
            enabled: false,
            configured: false,
            status: 'unknown',
            last_at: null,
            last_error: 'unavailable',
            pending_articles: 0,
          },
        },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }
}
