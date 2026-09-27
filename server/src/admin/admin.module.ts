import { Module } from '@nestjs/common';
import { AdminAuthService } from './auth/admin-auth.service';
import { AdminAuthController } from './auth/admin-auth.controller';
import { AdminFetchService } from './fetch/admin-fetch.service';
import { AdminController } from './admin.controller';
import { AdminAuthGuard } from '../common/guards/admin-auth.guard';
import { PipelineModule } from '../pipeline/pipeline.module';

@Module({
  imports: [PipelineModule],
  controllers: [AdminAuthController, AdminController],
  providers: [AdminAuthService, AdminFetchService, AdminAuthGuard],
  exports: [AdminAuthService],
})
export class AdminModule {}
