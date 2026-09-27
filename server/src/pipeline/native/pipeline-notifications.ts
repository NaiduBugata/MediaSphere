import { Logger } from '@nestjs/common';

export type NotifyEvent =
  | 'pipeline_started'
  | 'pipeline_completed'
  | 'new_article'
  | 'critical_issue'
  | 'pipeline_failure';

/**
 * Notification integration layer. Email and WhatsApp delivery stay out of scope.
 * Events are recorded and logged; a failure here must not roll back article writes.
 */
export class PipelineNotifications {
  readonly events: Array<{ event: NotifyEvent; detail: string }> = [];
  private readonly logger = new Logger('PipelineNotifications');

  emit(event: NotifyEvent, detail: string): void {
    this.events.push({ event, detail: detail.slice(0, 300) });
    this.logger.log(`[NOTIFY] ${event} ${detail.slice(0, 180)}`);
  }
}
