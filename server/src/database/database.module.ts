import { Global, Module } from '@nestjs/common';
import { DatabaseService } from './database.service';
import { ArticleRepository } from './repositories/article.repository';
import { PipelineStateRepository } from './repositories/pipeline-state.repository';
import { NotificationStatusRepository } from './repositories/notification-status.repository';
import { DailyReportRepository } from './repositories/daily-report.repository';

@Global()
@Module({
  providers: [
    DatabaseService,
    ArticleRepository,
    PipelineStateRepository,
    NotificationStatusRepository,
    DailyReportRepository,
  ],
  exports: [
    DatabaseService,
    ArticleRepository,
    PipelineStateRepository,
    NotificationStatusRepository,
    DailyReportRepository,
  ],
})
export class DatabaseModule {}
