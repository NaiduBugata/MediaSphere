import { Module } from '@nestjs/common';
import { AdminModule } from '../admin/admin.module';
import { BirthdaysController } from './birthdays.controller';
import { BirthdaysSchedulerService } from './birthdays-scheduler.service';
import { BirthdaysService } from './birthdays.service';

@Module({
  imports: [AdminModule],
  controllers: [BirthdaysController],
  providers: [BirthdaysService, BirthdaysSchedulerService],
})
export class BirthdaysModule {}
