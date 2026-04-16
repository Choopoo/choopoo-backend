# Migrations

Run automatically by gateway on startup via golang-migrate. File source is mounted at `/app/migrations` in the gateway container.

Naming: `NNNN_short_name.{up,down}.sql`. Apply order = lexicographic.

| # | Purpose |
|---|---|
| 0001 | `orgs`, `users`, `magic_link_tokens` (auth + tenancy primitives) |
| 0002 | Add `org_id` to existing `pages`, `analysis_results` (sentinel = 0 for legacy rows) |
| 0003 | Enable RLS on tenant tables; pipeline service role gets BYPASSRLS for backwards compat |

To roll back manually: connect to postgres, run the matching `*.down.sql` (or use the `migrate` CLI if installed).
