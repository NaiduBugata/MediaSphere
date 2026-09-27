import { Module } from '@nestjs/common';
import { WhatsAppController } from './whatsapp.controller';
import { WhatsAppLifecycleService } from './whatsapp.lifecycle';
import { WhatsAppWebhookRepository } from './whatsapp.repository';

@Module({
  controllers: [WhatsAppController],
  providers: [WhatsAppWebhookRepository, WhatsAppLifecycleService],
  exports: [WhatsAppWebhookRepository],
})
export class WhatsAppModule {}
