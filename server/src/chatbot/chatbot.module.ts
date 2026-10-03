import { Module } from '@nestjs/common';
import { VisitsModule } from '../visits/visits.module';
import { ChatbotService } from './chatbot.service';

@Module({
  imports: [VisitsModule],
  providers: [ChatbotService],
  exports: [ChatbotService],
})
export class ChatbotModule {}
