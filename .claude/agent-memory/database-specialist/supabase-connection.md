# Supabase Connection Troubleshooting

## Issue: Direct DB host (db.*.supabase.co) only has IPv6 AAAA record
- The `db.fspnxqmewtxmuyqqwwni.supabase.co` hostname resolves ONLY to IPv6: `2406:da1c:f42:ae00:6b9d:156:9d29:865b`
- No A (IPv4) record exists
- In environments without IPv6 support, the direct connection URL will fail with "could not translate host name"

## Solution: Use Supabase Pooler (Supavisor)
- **Pooler Host:** `aws-1-ap-southeast-2.pooler.supabase.com` (IPv4 available)
- **Session mode (port 5432):** Full PostgreSQL compatibility, use for migrations/DDL
- **Transaction mode (port 6543):** Better for connection pooling in production, some DDL limitations
- **Username format:** `postgres.PROJECT_REF` (e.g., `postgres.fspnxqmewtxmuyqqwwni`)
- **Connection string:** `postgresql://postgres.fspnxqmewtxmuyqqwwni:PASSWORD@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres`

## How to find the correct pooler region
- Supabase does not make it obvious which pooler hostname to use
- Method: brute-force DNS resolution + connection testing across all regions
- Regions tried: aws-0-*, aws-1-*, aws-2-*, fly-0-* with various region names
- The project was found at `aws-1-ap-southeast-2` (not the default `aws-0-*`)

## DNS Resolution Tips
- Use DNS-over-HTTPS (https://dns.google/resolve?name=HOST&type=AAAA) to check records
- Standard system DNS may not return AAAA records in all environments
- External DNS servers (8.8.8.8, 1.1.1.1) confirmed only AAAA exists

## .env File Updated
- The DATABASE_URL was changed from direct to pooler connection
- The direct URL is preserved as a comment for environments with IPv6 support
