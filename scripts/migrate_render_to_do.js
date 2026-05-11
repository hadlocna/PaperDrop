#!/usr/bin/env node

const path = require("path");
const { spawnSync } = require("child_process");
const { URL } = require("url");
const { Client } = require("../backend/node_modules/pg");

const TABLE_ORDER = [
  "users",
  "devices",
  "firmware_releases",
  "templates",
  "automations",
  "feedbacks",
  "device_access",
  "device_invites",
  "feedback_replies",
  "messages",
];

function usage() {
  console.error(`
Usage:
  SOURCE_DATABASE_URL=... TARGET_DATABASE_URL=... node scripts/migrate_render_to_do.js

Optional:
  TARGET_SCHEMA=paperdrop     Copy into a non-public schema inside the target database.
  SKIP_DB_PUSH=1              Skip running "prisma db push" against the target.
  SKIP_TRUNCATE=1             Keep existing target rows and append instead.

Safety:
  The script refuses to write into defaultdb.public because that is unsafe for a shared cluster.
  Use a dedicated target database (recommended) or set TARGET_SCHEMA to isolate PaperDrop.
`);
}

function requiredEnv(name) {
  const value = process.env[name];
  if (!value) {
    console.error(`Missing required environment variable: ${name}`);
    usage();
    process.exit(1);
  }
  return value;
}

function parseDbUrl(rawUrl) {
  const url = new URL(rawUrl);
  const dbName = url.pathname.replace(/^\//, "");
  const schema = url.searchParams.get("schema") || process.env.TARGET_SCHEMA || "public";
  return { url, dbName, schema };
}

function prismaTargetUrl(rawUrl, schema) {
  const url = new URL(rawUrl);
  if (schema && schema !== "public") {
    url.searchParams.set("schema", schema);
  }
  return url.toString();
}

function quoteIdent(name) {
  return `"${String(name).replace(/"/g, "\"\"")}"`;
}

function qname(schema, table) {
  return `${quoteIdent(schema)}.${quoteIdent(table)}`;
}

async function connect(connectionString) {
  const parsed = new URL(connectionString);
  const client = new Client({
    host: parsed.hostname,
    port: parsed.port ? Number(parsed.port) : 5432,
    database: parsed.pathname.replace(/^\//, ""),
    user: decodeURIComponent(parsed.username),
    password: decodeURIComponent(parsed.password),
    ssl: { rejectUnauthorized: false },
    connectionTimeoutMillis: 15000,
    statement_timeout: 30000,
    query_timeout: 30000,
  });
  await client.connect();
  return client;
}

function runPrismaDbPush(targetUrl) {
  const backendDir = path.join(__dirname, "..", "backend");
  const result = spawnSync(
    "npx",
    ["prisma", "db", "push", "--accept-data-loss"],
    {
      cwd: backendDir,
      env: {
        ...process.env,
        DATABASE_URL: targetUrl,
      },
      stdio: "inherit",
    }
  );

  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}

async function fetchTableColumns(client, schema, table) {
  const result = await client.query(
    `
      select column_name
      from information_schema.columns
      where table_schema = $1 and table_name = $2
      order by ordinal_position
    `,
    [schema, table]
  );

  return result.rows.map((row) => row.column_name);
}

async function fetchTableCount(client, schema, table) {
  const result = await client.query(`select count(*)::int as count from ${qname(schema, table)}`);
  return result.rows[0].count;
}

async function truncateTarget(client, schema) {
  const tableList = TABLE_ORDER.slice().reverse().map((table) => qname(schema, table)).join(", ");
  await client.query(`TRUNCATE TABLE ${tableList} RESTART IDENTITY CASCADE`);
}

async function copyTable(sourceClient, targetClient, targetSchema, table) {
  const sourceColumns = await fetchTableColumns(sourceClient, "public", table);
  const targetColumns = await fetchTableColumns(targetClient, targetSchema, table);
  const targetColumnSet = new Set(targetColumns);
  const columns = sourceColumns.filter((column) => targetColumnSet.has(column));

  if (columns.length === 0) {
    throw new Error(`No compatible columns found for ${table}`);
  }

  const selectSql = `select ${columns.map(quoteIdent).join(", ")} from ${qname("public", table)}`;
  const sourceRows = await sourceClient.query(selectSql);

  if (sourceRows.rows.length === 0) {
    return 0;
  }

  const batchSize = 100;
  for (let offset = 0; offset < sourceRows.rows.length; offset += batchSize) {
    const batch = sourceRows.rows.slice(offset, offset + batchSize);
    const values = [];
    const placeholders = batch.map((row, rowIndex) => {
      const rowPlaceholders = columns.map((column, columnIndex) => {
        values.push(row[column]);
        return `$${rowIndex * columns.length + columnIndex + 1}`;
      });
      return `(${rowPlaceholders.join(", ")})`;
    });

    const insertSql = `
      insert into ${qname(targetSchema, table)} (${columns.map(quoteIdent).join(", ")})
      values ${placeholders.join(", ")}
    `;

    await targetClient.query(insertSql, values);
  }

  return sourceRows.rows.length;
}

async function verifyTables(sourceClient, targetClient, targetSchema) {
  for (const table of TABLE_ORDER) {
    const sourceCount = await fetchTableCount(sourceClient, "public", table);
    const targetCount = await fetchTableCount(targetClient, targetSchema, table);
    if (sourceCount !== targetCount) {
      throw new Error(`Count mismatch for ${table}: source=${sourceCount}, target=${targetCount}`);
    }
  }
}

async function main() {
  const sourceUrl = requiredEnv("SOURCE_DATABASE_URL");
  const targetUrl = requiredEnv("TARGET_DATABASE_URL");
  const skipDbPush = process.env.SKIP_DB_PUSH === "1";
  const skipTruncate = process.env.SKIP_TRUNCATE === "1";

  const sourceInfo = parseDbUrl(sourceUrl);
  const targetInfo = parseDbUrl(targetUrl);

  if (targetInfo.dbName === "defaultdb" && targetInfo.schema === "public") {
    throw new Error(
      "Refusing to write into defaultdb.public on the shared DigitalOcean cluster. " +
      "Create a dedicated database (recommended) or set TARGET_SCHEMA to an isolated schema."
    );
  }

  const effectiveTargetUrl = prismaTargetUrl(targetUrl, targetInfo.schema);

  if (!skipDbPush) {
    console.log(`Running prisma db push against ${targetInfo.dbName}.${targetInfo.schema}`);
    runPrismaDbPush(effectiveTargetUrl);
  }

  const sourceClient = await connect(sourceUrl);
  const targetClient = await connect(effectiveTargetUrl);

  try {
    if (targetInfo.schema !== "public") {
      await targetClient.query(`create schema if not exists ${quoteIdent(targetInfo.schema)}`);
    }

    if (!skipTruncate) {
      console.log(`Truncating existing PaperDrop tables in ${targetInfo.dbName}.${targetInfo.schema}`);
      await truncateTarget(targetClient, targetInfo.schema);
    }

    const copied = {};
    for (const table of TABLE_ORDER) {
      const rowCount = await copyTable(sourceClient, targetClient, targetInfo.schema, table);
      copied[table] = rowCount;
      console.log(`Copied ${rowCount} rows into ${targetInfo.schema}.${table}`);
    }

    await verifyTables(sourceClient, targetClient, targetInfo.schema);
    console.log("Migration verified successfully.");
    console.log(JSON.stringify(copied, null, 2));
  } finally {
    await sourceClient.end();
    await targetClient.end();
  }
}

main().catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});
