# Performance Tuning Guide for Game Asset Postgres DB

This guide covers optimization for high-throughput scenarios, like bulk asset uploads during game title releases.

## 1. Indexing Strategy
- Use GIN indexes on JSONB metadata: `CREATE INDEX idx_assets_metadata ON assets USING GIN (metadata);`
- For tag searches: Ensure composite indexes on asset_tags.

## 2. Vacuum and Analyze
- Run `VACUUM ANALYZE;` weekly to update stats.
- Enable autovacuum tuning: Set `autovacuum = on` in conf.

## 3. Connection Pooling
- Use PgBouncer or similar for handling many game dev connections.
- Set `max_connections = 100` but pool to 20-50.

## 4. Query Optimization
- Explain queries: `EXPLAIN ANALYZE SELECT * FROM assets WHERE metadata @> '{"format": "png"}';`
- Partition large tables (e.g., audit_log by timestamp) for >1M rows.

## 5. Hardware/Monitoring
- Allocate 25% RAM to shared_buffers.
- Monitor with pg_stat_statements extension.
- For scale: Consider read replicas for reporting.

Benchmark with pgbench: `pgbench -i -s 10 asset_db; pgbench -c 10 -j 2 -T 60 asset_db`
