# Render to DigitalOcean PostgreSQL Migration

This repo uses Prisma with PostgreSQL from [backend/prisma/schema.prisma](/Users/nathanhadlock/PaperDrop/backend/prisma/schema.prisma). PaperDrop currently stores its data in these tables:

- `users`
- `devices`
- `firmware_releases`
- `templates`
- `automations`
- `feedbacks`
- `device_access`
- `device_invites`
- `feedback_replies`
- `messages`

## Recommended target layout

Because the DigitalOcean cluster is shared with other projects, do not migrate PaperDrop into `defaultdb.public`.

Use one of these:

1. Recommended: create a separate database named `paperdrop` in the shared cluster.
2. Acceptable: keep `defaultdb`, but create a dedicated schema like `paperdrop` and use `?schema=paperdrop` in `DATABASE_URL`.

For the current Coolify deployment, the backend is using the dedicated `paperdrop_backend` database with the default `public` schema.

DigitalOcean documents that managed PostgreSQL clusters include a default database named `defaultdb`, that you can add additional databases, and that importing a dump is the recommended migration path when the source user does not have `superuser`:
[Manage users and databases](https://docs.digitalocean.com/products/databases/postgresql/how-to/manage-users-and-databases/)
[Import PostgreSQL databases](https://docs.digitalocean.com/products/databases/postgresql/how-to/import-databases/)
[PostgreSQL limits](https://docs.digitalocean.com/products/databases/postgresql/details/limits/)

## Current source facts

The Render source database is PostgreSQL 18.3 and currently contains:

- `users`: 9
- `devices`: 4
- `device_access`: 17
- `device_invites`: 9
- `messages`: 173
- `feedbacks`: 1

The Render role is not a PostgreSQL `superuser`, so DigitalOcean continuous migration is not the right fit. Use a point-in-time migration.

## Networking prerequisite

This machine must be added to the DigitalOcean cluster's trusted sources before the migration script can connect.

If you are running the migration from this machine, add this public IP as a trusted source:

- `169.155.237.213`

DigitalOcean documents trusted-source networking and notes that managed databases are publicly reachable until you restrict them:

- [How to manage users and databases](https://docs.digitalocean.com/products/databases/postgresql/how-to/manage-users-and-databases/)
- [How to migrate PostgreSQL databases to DigitalOcean](https://docs.digitalocean.com/products/databases/postgresql/how-to/migrate/)

## Migration steps

1. In DigitalOcean, create a new database named `paperdrop` in the existing cluster.
2. Add your migration machine as a trusted source.
3. Build a target connection string:

```text
postgresql://doadmin:REDACTED@db-postgresql-ams3-06533-do-user-9374024-0.k.db.ondigitalocean.com:25060/paperdrop_backend?sslmode=require
```

If you must stay inside `defaultdb`, use:

```text
postgresql://doadmin:REDACTED@db-postgresql-ams3-06533-do-user-9374024-0.k.db.ondigitalocean.com:25060/defaultdb?sslmode=require&schema=paperdrop
```

4. Run the migration helper from the repo root:

```bash
SOURCE_DATABASE_URL='postgresql://REDACTED' \
TARGET_DATABASE_URL='postgresql://REDACTED' \
node scripts/migrate_render_to_do.js
```

The script will:

- run `prisma db push` against the target
- refuse to write into `defaultdb.public`
- truncate only the PaperDrop target tables
- copy rows in foreign-key-safe order
- verify row counts after the copy

5. Update the backend `DATABASE_URL` to the new DigitalOcean URL.
6. Update the frontend `VITE_API_URL` to the Coolify backend URL.
7. Redeploy the backend and frontend.
8. Verify the health endpoint and a few core flows:

- `GET /health`
- log in
- claim/open an existing device
- send a test message
- confirm a device reconnects over WebSocket

## Migration verification on 2026-05-11

The Render source was copied into `paperdrop_backend.public` and verified with these counts:

- `users`: 9
- `devices`: 4
- `firmware_releases`: 0
- `templates`: 0
- `automations`: 0
- `feedbacks`: 1
- `device_access`: 17
- `device_invites`: 9
- `feedback_replies`: 0
- `messages`: 173

## Operational note

If the backend will stay on Render after the database cutover, make sure the Render service can reach the DigitalOcean database. That usually means explicitly allowing the backend's egress source in DigitalOcean trusted sources or attaching the app directly if you later move the backend to DigitalOcean App Platform.
