import { Module } from '@nestjs/common';
import { AdminModule } from '../admin/admin.module';
import { VisitsController } from './visits.controller';
import { VisitsService } from './visits.service';

@Module({
  imports: [AdminModule],
  controllers: [VisitsController],
  providers: [VisitsService],
})
export class VisitsModule {}
