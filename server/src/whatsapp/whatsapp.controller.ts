import { Controller, Get, Inject, Optional, Post, Req, Res } from '@nestjs/common';
import type { Request, Response } from 'express';
import { ChatbotService } from '../chatbot/chatbot.service';
import { WhatsAppWebhookRepository } from './whatsapp.repository';
import { processWebhookPost, verifyWebhook, webhookEnabled } from './whatsapp.webhook';

@Controller()
export class WhatsAppController {
  constructor(
    private readonly events: WhatsAppWebhookRepository,
    @Optional() @Inject(ChatbotService) private readonly chatbot?: ChatbotService,
  ) {}

  @Get('webhook')
  verify(@Req() req: Request, @Res() res: Response): void {
    const query = req.query as Record<string, string | undefined>;
    const result = verifyWebhook({
      mode: query['hub.mode'],
      token: query['hub.verify_token'],
      challenge: query['hub.challenge'],
    });
    res.status(result.status).type('text/plain').send(result.body);
  }

  @Post('webhook')
  async receive(@Req() req: Request, @Res() res: Response): Promise<void> {
    if (!webhookEnabled()) {
      res.status(503).type('text/plain').send('Webhook disabled');
      return;
    }
    const forwarded = req.header('x-forwarded-for');
    const clientIp = forwarded ? forwarded.split(',')[0].trim() : req.ip || null;
    const result = await processWebhookPost(req.body, {
      clientIp,
      wabaId: process.env.WHATSAPP_WABA_ID || process.env.WHATSAPP_BUSINESS_ACCOUNT_ID || '',
      save: (event, raw) => this.events.saveEvent(event, clientIp, raw),
    });
    res.status(result.status).type('text/plain').send(result.body);
    if (result.status === 200) this.chatbot?.consider(req.body);
  }
}
