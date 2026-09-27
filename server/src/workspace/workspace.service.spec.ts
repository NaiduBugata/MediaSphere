import { WorkspaceService } from './workspace.service';
import { ConfigService } from '@nestjs/config';
import { DatabaseService } from '../database/database.service';

describe('WorkspaceService', () => {
  it('registers, logs in, and stores a grievance without a live database', async () => {
    const users: Array<Record<string, unknown>> = [];
    const records: Array<Record<string, unknown>> = [];
    const db = {
      ensureConnected: async () => true,
      articlesCollectionName: 'articles',
      collection: (name: string) => ({
        findOne: async (filter: { email?: string }) => users.find((row) => row.email === filter.email) || null,
        insertOne: async (doc: Record<string, unknown>) => {
          const _id = `${name}-${(name === 'jv_users' ? users : records).length + 1}`;
          const row = { ...doc, _id };
          (name === 'jv_users' ? users : records).push(row);
          return { insertedId: _id };
        },
        find: () => ({
          sort: () => ({
            limit: () => ({
              toArray: async () => records.filter((row) => row.section === 'grievances'),
            }),
          }),
        }),
        countDocuments: async (filter: { section?: string }) => records.filter((row) => !filter.section || row.section === filter.section).length,
      }),
    };
    const config = { get: () => 'test-secret' } as unknown as ConfigService;
    const service = new WorkspaceService(db as unknown as DatabaseService, config);

    const created = await service.register('local@janavignanam.local', 'localpass', 'local');
    expect(created.user.email).toBe('local@janavignanam.local');
    const again = await service.login('local@janavignanam.local', 'localpass');
    expect(again.user.name).toBe('local');
    await expect(service.login('local@janavignanam.local', 'wrongpass')).rejects.toThrow('incorrect');

    const row = await service.create({
      section: 'grievances',
      title: 'Water supply',
      detail: 'Ward 14',
      createdBy: again.user.email,
    });
    expect(row.title).toBe('Water supply');
    expect(await service.list('grievances')).toHaveLength(1);
  });
});
