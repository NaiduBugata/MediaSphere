# database/

MongoDB database layer for MediaSphere.

| File | Purpose |
|------|---------|
| `mongo.py` | Connection management, CRUD operations, indexes |

## Connection

Uses `MONGODB_URI` environment variable. Thread-safe singleton client with
double-checked locking. DNS pre-import for `mongodb+srv` URIs.
