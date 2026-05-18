use async_trait::async_trait;
use sqlx::{sqlite::SqliteRow, Row, Sqlite};

use super::{
    quota_snapshot_select, ProviderQuotaReadRepository, ProviderQuotaWriteRepository,
    StoredProviderQuotaSnapshot,
};
use crate::driver::sqlite::{sqlite_optional_real, sqlite_real, SqlitePool};
use crate::error::SqlResultExt;
use crate::DataLayerError;
use aether_data_query::SqlDialect;

#[derive(Debug, Clone)]
pub struct SqliteProviderQuotaRepository {
    pool: SqlitePool,
}

impl SqliteProviderQuotaRepository {
    pub fn new(pool: SqlitePool) -> Self {
        Self { pool }
    }
}

#[async_trait]
impl ProviderQuotaReadRepository for SqliteProviderQuotaRepository {
    async fn find_by_provider_id(
        &self,
        provider_id: &str,
    ) -> Result<Option<StoredProviderQuotaSnapshot>, DataLayerError> {
        let mut statement = quota_snapshot_select().statement::<Sqlite>(SqlDialect::Sqlite);
        statement.where_eq("id", provider_id.to_string()).limit(1);
        let row = statement
            .finish()
            .build()
            .fetch_optional(&self.pool)
            .await
            .map_sql_err()?;
        row.as_ref().map(map_row).transpose()
    }

    async fn find_by_provider_ids(
        &self,
        provider_ids: &[String],
    ) -> Result<Vec<StoredProviderQuotaSnapshot>, DataLayerError> {
        if provider_ids.is_empty() {
            return Ok(Vec::new());
        }

        let mut statement = quota_snapshot_select().statement::<Sqlite>(SqlDialect::Sqlite);
        statement
            .where_in("id", provider_ids)
            .order_by_sql("id ASC");
        let rows = statement
            .finish()
            .build()
            .fetch_all(&self.pool)
            .await
            .map_sql_err()?;
        rows.iter().map(map_row).collect()
    }
}

#[async_trait]
impl ProviderQuotaWriteRepository for SqliteProviderQuotaRepository {
    async fn reset_due(&self, now_unix_secs: u64) -> Result<usize, DataLayerError> {
        let now = i64::try_from(now_unix_secs).map_err(|_| {
            DataLayerError::InvalidInput("provider quota reset timestamp overflow".to_string())
        })?;
        let rows_affected = sqlx::query(
            r#"
UPDATE providers
SET monthly_used_usd = 0.0,
    quota_last_reset_at = ?,
    updated_at = ?
WHERE billing_type = 'monthly_quota'
  AND is_active = 1
  AND (
    quota_last_reset_at IS NULL
    OR (? - quota_last_reset_at) >= (quota_reset_day * 86400)
  )
"#,
        )
        .bind(now)
        .bind(now)
        .bind(now)
        .execute(&self.pool)
        .await
        .map_sql_err()?
        .rows_affected();
        Ok(usize::try_from(rows_affected).unwrap_or_default())
    }
}

fn map_row(row: &SqliteRow) -> Result<StoredProviderQuotaSnapshot, DataLayerError> {
    StoredProviderQuotaSnapshot::new(
        row.try_get("provider_id").map_sql_err()?,
        row.try_get("billing_type").map_sql_err()?,
        sqlite_optional_real(row, "monthly_quota_usd")?,
        sqlite_real(row, "monthly_used_usd")?,
        row.try_get("quota_reset_day").map_sql_err()?,
        row.try_get("quota_last_reset_at_unix_secs").map_sql_err()?,
        row.try_get("quota_expires_at_unix_secs").map_sql_err()?,
        row.try_get("is_active").map_sql_err()?,
    )
}

#[cfg(test)]
mod tests {
    use super::SqliteProviderQuotaRepository;
    use crate::lifecycle::migrate::run_sqlite_migrations;
    use crate::repository::quota::{ProviderQuotaReadRepository, ProviderQuotaWriteRepository};

    #[tokio::test]
    async fn sqlite_repository_reads_and_resets_provider_quotas() {
        let pool = sqlx::sqlite::SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .expect("sqlite pool should connect");
        run_sqlite_migrations(&pool)
            .await
            .expect("sqlite migrations should run");
        seed_provider_quotas(&pool).await;

        let repository = SqliteProviderQuotaRepository::new(pool);
        let quota = repository
            .find_by_provider_id("provider-1")
            .await
            .expect("quota should load")
            .expect("quota should exist");
        assert_eq!(quota.monthly_used_usd, 5.0);

        let quota = repository
            .find_by_provider_id("provider-null-used")
            .await
            .expect("quota with null usage should load")
            .expect("quota with null usage should exist");
        assert_eq!(quota.monthly_used_usd, 0.0);

        let quotas = repository
            .find_by_provider_ids(&["provider-2".to_string(), "provider-1".to_string()])
            .await
            .expect("quotas should load");
        assert_eq!(
            quotas
                .iter()
                .map(|quota| quota.provider_id.as_str())
                .collect::<Vec<_>>(),
            vec!["provider-1", "provider-2"]
        );

        let reset = repository
            .reset_due(1_000 + 7 * 24 * 60 * 60)
            .await
            .expect("quota reset should run");
        assert_eq!(reset, 1);
        let quota = repository
            .find_by_provider_id("provider-1")
            .await
            .expect("quota should reload")
            .expect("quota should exist");
        assert_eq!(quota.monthly_used_usd, 0.0);
        assert_eq!(quota.quota_last_reset_at_unix_secs, Some(605_800));
    }

    async fn seed_provider_quotas(pool: &sqlx::SqlitePool) {
        sqlx::query(
            r#"
INSERT INTO providers (
  id, name, provider_type, billing_type, monthly_quota_usd, monthly_used_usd,
  quota_reset_day, quota_last_reset_at, is_active, created_at, updated_at
)
VALUES
  ('provider-1', 'Provider One', 'openai', 'monthly_quota', 20.0, 5.0, 7, 1000, 1, 1, 1),
  ('provider-2', 'Provider Two', 'openai', 'payg', NULL, 1.5, NULL, NULL, 1, 1, 1),
  ('provider-null-used', 'Provider Null Used', 'openai', 'payg', NULL, NULL, NULL, NULL, 1, 1, 1)
"#,
        )
        .execute(pool)
        .await
        .expect("providers should seed");
    }
}
