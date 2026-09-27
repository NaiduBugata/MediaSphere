import { Module } from '@nestjs/common';
import { PipelineController } from './pipeline.controller';
import { PipelineLockService } from './pipeline-lock.service';
import { PipelineStateService } from './pipeline-state.service';
import { PipelineHistoryService } from './pipeline-history.service';
import { PipelineRunnerService } from './pipeline-runner.service';
import { PythonBridgeService } from './python-bridge.service';
import { PipelineSchedulerService } from './pipeline-scheduler.service';
import { PipelineHealthService } from './pipeline-health.service';
import { CombinedPipelineService } from './native/combined-pipeline.service';

/**
 * Phase 3 control plane. DatabaseModule is @Global, so repositories are
 * available without re-importing it here.
 */
@Module({
  controllers: [PipelineController],
  providers: [
    PipelineLockService,
    PipelineStateService,
    PipelineHistoryService,
    PythonBridgeService,
    CombinedPipelineService,
    PipelineRunnerService,
    PipelineSchedulerService,
    PipelineHealthService,
  ],
  exports: [
    PipelineLockService,
    PipelineStateService,
    PipelineHistoryService,
    PipelineRunnerService,
    PipelineSchedulerService,
    PipelineHealthService,
  ],
})
export class PipelineModule {}
