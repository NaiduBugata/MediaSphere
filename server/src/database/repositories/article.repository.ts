import { Injectable } from '@nestjs/common';
import { Document } from 'mongodb';
import { DatabaseService } from '../database.service';

@Injectable()
export class ArticleRepository {
  constructor(private readonly db: DatabaseService) {}

  async findAll(): Promise<Document[]> {
    await this.db.ensureConnected();
    return this.db.articles().find({}).toArray();
  }

  async count(): Promise<number> {
    await this.db.ensureConnected();
    return this.db.articles().countDocuments({});
  }

  async countEmailPending(): Promise<number> {
    return this.db.articles().countDocuments({ email_sent: false });
  }

  async countWhatsappPending(): Promise<number> {
    return this.db.articles().countDocuments({ whatsapp_sent: false });
  }

  async findNewestForRevision(): Promise<Document | null> {
    return this.db.articles().findOne(
      {},
      {
        sort: { first_seen_at: -1 },
        projection: { first_seen_at: 1, last_updated_at: 1 },
      },
    );
  }
}
