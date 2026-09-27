import { Module } from '@nestjs/common';
import { ReportsController } from './reports.controller';
import { ReportsSchedulerService } from './reports-scheduler.service';
import { ReportsService } from './reports.service';

@Module({
  controllers: [ReportsController],
  providers: [ReportsService, ReportsSchedulerService],
  exports: [ReportsService],
})
export class ReportsModule {}
