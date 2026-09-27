import { DatabaseService } from './database.service';
import { ConfigService } from '@nestjs/config';

describe('DatabaseService health probe contract helpers', () => {
  it('reports disconnected when MONGODB_URI missing', async () => {
    const config = {
      get: (key: string) => {
        if (key === 'database.uri') return '';
        if (key === 'database.name') return 'MediaSphere';
        if (key === 'database.articlesCollection') return 'articles';
        return undefined;
      },
    } as ConfigService;

    const db = new DatabaseService(config);
    await db.onModuleInit();
    expect(db.isConnected).toBe(false);
    const ok = await db.ensureConnected();
    expect(ok).toBe(false);
  });
});
