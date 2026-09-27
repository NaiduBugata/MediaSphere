import { Module } from '@nestjs/common';
import { ChatbotModule } from '../chatbot/chatbot.module';
import { WhatsAppController } from './whatsapp.controller';
import { WhatsAppLifecycleService } from './whatsapp.lifecycle';
import { WhatsAppWebhookRepository } from './whatsapp.repository';

@Module({
  imports: [ChatbotModule],
  controllers: [WhatsAppController],
  providers: [WhatsAppWebhookRepository, WhatsAppLifecycleService],
  exports: [WhatsAppWebhookRepository],
})
export class WhatsAppModule {}
