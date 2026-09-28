import { NotificationsService } from './notifications.service';
import { ConfigService } from '@nestjs/config';

describe('NotificationsService snapshot', () => {
  it('returns disabled/failed shapes when channels off / unconfigured', async () => {
    const config = {
      get: (key: string) => {
        const map: Record<string, unknown> = {
          'email.enabled': 'false',
          'email.provider': 'auto',
          'email.recipients': '',
          'email.resendApiKey': '',
          'email.smtpUsername': '',
          'email.smtpPassword': '',
          'whatsapp.enabled': 'true',
          'whatsapp.accessToken': '',
          'whatsapp.phoneNumberId': '',
          'whatsapp.recipients': '',
        };
        return map[key];
      },
    } as ConfigService;

    const articles = {
      countWhatsappPending: async () => 0,
    };
    const statusStore = {
      getAll: async () => ({ email: null, whatsapp: null }),
    };
    const dailyReports = { latest: async () => null };

    const svc = new NotificationsService(
      config,
      articles as never,
      statusStore as never,
      dailyReports as never,
    );
    const snap = await svc.buildStatusSnapshot();
    expect(snap.email.enabled).toBe(false);
    expect(snap.email.status).toBe('disabled');
    expect(snap.whatsapp.enabled).toBe(true);
    expect(snap.whatsapp.configured).toBe(false);
    expect(snap.whatsapp.status).toBe('failed');
    expect(snap.whatsapp.last_error).toBe(
      'missing_token_phone_id_or_recipients',
    );
  });
});
