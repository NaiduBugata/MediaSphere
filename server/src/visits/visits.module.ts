import { Module } from '@nestjs/common';
import { AdminModule } from '../admin/admin.module';
import { VisitFollowupScheduler } from './visit-followup.scheduler';
import { VisitFollowupService } from './visit-followup.service';
import { VisitsController } from './visits.controller';
import { VisitsService } from './visits.service';

@Module({
  imports: [AdminModule],
  controllers: [VisitsController],
  providers: [VisitsService, VisitFollowupService, VisitFollowupScheduler],
  exports: [VisitFollowupService],
})
export class VisitsModule {}
