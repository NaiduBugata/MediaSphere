import {
  Controller,
  Get,
  Header,
  HttpException,
  HttpStatus,
  Logger,
  Query,
  Res,
} from '@nestjs/common';
import type { Response } from 'express';
import { NewsService } from './news.service';

@Controller('api/news')
export class NewsController {
  private readonly logger = new Logger(NewsController.name);

  constructor(private readonly newsService: NewsService) {}

  @Get()
  @Header('Cache-Control', 'no-store')
  async getNews(
    @Query('source') source = 'all',
    @Res({ passthrough: true }) res: Response,
  ) {
    try {
      return await this.newsService.listNews(source);
    } catch (err) {
      this.logger.error('Failed to fetch news', err instanceof Error ? err.stack : err);
      res.setHeader('Cache-Control', 'no-store');
      throw new HttpException(
        { error: 'Failed to fetch news', articles: [], count: 0 },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }

  @Get('stats')
  @Header('Cache-Control', 'no-store')
  async getStats(@Res({ passthrough: true }) res: Response) {
    try {
      return await this.newsService.getStats();
    } catch (err) {
      this.logger.error('Failed to fetch stats', err instanceof Error ? err.stack : err);
      res.setHeader('Cache-Control', 'no-store');
      throw new HttpException(
        { error: 'Failed to fetch stats' },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }
}
