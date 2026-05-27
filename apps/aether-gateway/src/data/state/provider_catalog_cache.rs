use std::collections::HashMap;
use std::future::Future;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use aether_cache::ExpiringMap;
use aether_data::DataLayerError;
use aether_data_contracts::repository::provider_catalog::{
    ProviderCatalogKeyListQuery, ProviderCatalogReadRepository, StoredProviderCatalogEndpoint,
    StoredProviderCatalogKey, StoredProviderCatalogKeyMaintenanceSummary,
    StoredProviderCatalogKeyPage, StoredProviderCatalogKeyStats, StoredProviderCatalogProvider,
};
use async_trait::async_trait;
use tokio::sync::Notify;

const PROVIDER_CATALOG_CACHE_TTL: Duration = Duration::from_secs(5);
const PROVIDER_CATALOG_CACHE_MAX_ENTRIES: usize = 1024;

pub(super) struct CachedProviderCatalogReadRepository {
    inner: Arc<dyn ProviderCatalogReadRepository>,
    entries: ExpiringMap<ProviderCatalogCacheKey, ProviderCatalogCacheValue>,
    inflight: Mutex<HashMap<ProviderCatalogCacheKey, u64>>,
    inflight_notify: Notify,
    next_inflight_token: AtomicU64,
    epoch: AtomicU64,
}

impl CachedProviderCatalogReadRepository {
    pub(super) fn new(inner: Arc<dyn ProviderCatalogReadRepository>) -> Self {
        Self {
            inner,
            entries: ExpiringMap::new(),
            inflight: Mutex::new(HashMap::new()),
            inflight_notify: Notify::new(),
            next_inflight_token: AtomicU64::new(1),
            epoch: AtomicU64::new(0),
        }
    }

    async fn get_or_load<F, Fut>(
        &self,
        key: ProviderCatalogCacheKey,
        load: F,
    ) -> Result<ProviderCatalogCacheValue, DataLayerError>
    where
        F: Fn() -> Fut,
        Fut: Future<Output = Result<ProviderCatalogCacheValue, DataLayerError>>,
    {
        if let Some(value) = self.entries.get_fresh(&key, PROVIDER_CATALOG_CACHE_TTL) {
            return Ok(value);
        }

        loop {
            let notified = self.inflight_notify.notified();
            match self.register_inflight(&key) {
                InflightRegistration::Bypass => return load().await,
                InflightRegistration::Follower => {
                    notified.await;
                    if let Some(value) = self.entries.get_fresh(&key, PROVIDER_CATALOG_CACHE_TTL) {
                        return Ok(value);
                    }
                }
                InflightRegistration::Leader(token) => {
                    let mut guard = InflightGuard::new(self, key.clone(), token);
                    let load_epoch = self.epoch.load(Ordering::Acquire);
                    let result = load().await;
                    if let Ok(value) = &result {
                        if load_epoch == self.epoch.load(Ordering::Acquire) {
                            self.entries.insert(
                                key.clone(),
                                value.clone(),
                                PROVIDER_CATALOG_CACHE_TTL,
                                PROVIDER_CATALOG_CACHE_MAX_ENTRIES,
                            );
                        }
                    }
                    guard.finish();
                    return result;
                }
            }
        }
    }

    fn register_inflight(&self, key: &ProviderCatalogCacheKey) -> InflightRegistration {
        match self.inflight.lock() {
            Ok(mut inflight) => {
                if inflight.contains_key(key) {
                    return InflightRegistration::Follower;
                }
                let token = self.next_inflight_token.fetch_add(1, Ordering::AcqRel);
                inflight.insert(key.clone(), token);
                InflightRegistration::Leader(token)
            }
            Err(_) => InflightRegistration::Bypass,
        }
    }

    fn finish_inflight(&self, key: &ProviderCatalogCacheKey, token: u64) {
        let mut removed = false;
        if let Ok(mut inflight) = self.inflight.lock() {
            if inflight.get(key).copied() == Some(token) {
                inflight.remove(key);
                removed = true;
            }
        }
        if removed {
            self.inflight_notify.notify_waiters();
        }
    }

    fn clear(&self) {
        self.epoch.fetch_add(1, Ordering::AcqRel);
        self.entries.clear();
        let mut cleared_inflight = false;
        if let Ok(mut inflight) = self.inflight.lock() {
            cleared_inflight = !inflight.is_empty();
            inflight.clear();
        }
        if cleared_inflight {
            self.inflight_notify.notify_waiters();
        }
    }
}

#[async_trait]
impl ProviderCatalogReadRepository for CachedProviderCatalogReadRepository {
    fn clear_local_cache(&self) {
        self.clear();
        self.inner.clear_local_cache();
    }

    async fn list_providers(
        &self,
        active_only: bool,
    ) -> Result<Vec<StoredProviderCatalogProvider>, DataLayerError> {
        match self
            .get_or_load(
                ProviderCatalogCacheKey::Providers { active_only },
                || async move {
                    self.inner
                        .list_providers(active_only)
                        .await
                        .map(ProviderCatalogCacheValue::Providers)
                },
            )
            .await?
        {
            ProviderCatalogCacheValue::Providers(items) => Ok(items),
            _ => Ok(Vec::new()),
        }
    }

    async fn list_providers_by_ids(
        &self,
        provider_ids: &[String],
    ) -> Result<Vec<StoredProviderCatalogProvider>, DataLayerError> {
        let key = ProviderCatalogCacheKey::ProvidersByIds(normalize_ids(provider_ids));
        match self
            .get_or_load(key, || async move {
                self.inner
                    .list_providers_by_ids(provider_ids)
                    .await
                    .map(ProviderCatalogCacheValue::Providers)
            })
            .await?
        {
            ProviderCatalogCacheValue::Providers(items) => Ok(items),
            _ => Ok(Vec::new()),
        }
    }

    async fn list_endpoints_by_ids(
        &self,
        endpoint_ids: &[String],
    ) -> Result<Vec<StoredProviderCatalogEndpoint>, DataLayerError> {
        self.inner.list_endpoints_by_ids(endpoint_ids).await
    }

    async fn list_endpoints_by_provider_ids(
        &self,
        provider_ids: &[String],
    ) -> Result<Vec<StoredProviderCatalogEndpoint>, DataLayerError> {
        let key = ProviderCatalogCacheKey::EndpointsByProviderIds(normalize_ids(provider_ids));
        match self
            .get_or_load(key, || async move {
                self.inner
                    .list_endpoints_by_provider_ids(provider_ids)
                    .await
                    .map(ProviderCatalogCacheValue::Endpoints)
            })
            .await?
        {
            ProviderCatalogCacheValue::Endpoints(items) => Ok(items),
            _ => Ok(Vec::new()),
        }
    }

    async fn list_keys_by_ids(
        &self,
        key_ids: &[String],
    ) -> Result<Vec<StoredProviderCatalogKey>, DataLayerError> {
        self.inner.list_keys_by_ids(key_ids).await
    }

    async fn list_keys_by_provider_ids(
        &self,
        provider_ids: &[String],
    ) -> Result<Vec<StoredProviderCatalogKey>, DataLayerError> {
        let key = ProviderCatalogCacheKey::KeysByProviderIds(normalize_ids(provider_ids));
        match self
            .get_or_load(key, || async move {
                self.inner
                    .list_keys_by_provider_ids(provider_ids)
                    .await
                    .map(ProviderCatalogCacheValue::Keys)
            })
            .await?
        {
            ProviderCatalogCacheValue::Keys(items) => Ok(items),
            _ => Ok(Vec::new()),
        }
    }

    async fn list_key_summaries_by_provider_ids(
        &self,
        provider_ids: &[String],
    ) -> Result<Vec<StoredProviderCatalogKey>, DataLayerError> {
        let key = ProviderCatalogCacheKey::KeySummariesByProviderIds(normalize_ids(provider_ids));
        match self
            .get_or_load(key, || async move {
                self.inner
                    .list_key_summaries_by_provider_ids(provider_ids)
                    .await
                    .map(ProviderCatalogCacheValue::Keys)
            })
            .await?
        {
            ProviderCatalogCacheValue::Keys(items) => Ok(items),
            _ => Ok(Vec::new()),
        }
    }

    async fn list_key_maintenance_summaries_by_provider_ids(
        &self,
        provider_ids: &[String],
    ) -> Result<Vec<StoredProviderCatalogKeyMaintenanceSummary>, DataLayerError> {
        let key = ProviderCatalogCacheKey::KeyMaintenanceSummariesByProviderIds(normalize_ids(
            provider_ids,
        ));
        match self
            .get_or_load(key, || async move {
                self.inner
                    .list_key_maintenance_summaries_by_provider_ids(provider_ids)
                    .await
                    .map(ProviderCatalogCacheValue::KeyMaintenanceSummaries)
            })
            .await?
        {
            ProviderCatalogCacheValue::KeyMaintenanceSummaries(items) => Ok(items),
            _ => Ok(Vec::new()),
        }
    }

    async fn list_keys_page(
        &self,
        query: &ProviderCatalogKeyListQuery,
    ) -> Result<StoredProviderCatalogKeyPage, DataLayerError> {
        self.inner.list_keys_page(query).await
    }

    async fn list_key_stats_by_provider_ids(
        &self,
        provider_ids: &[String],
    ) -> Result<Vec<StoredProviderCatalogKeyStats>, DataLayerError> {
        let key = ProviderCatalogCacheKey::KeyStatsByProviderIds(normalize_ids(provider_ids));
        match self
            .get_or_load(key, || async move {
                self.inner
                    .list_key_stats_by_provider_ids(provider_ids)
                    .await
                    .map(ProviderCatalogCacheValue::KeyStats)
            })
            .await?
        {
            ProviderCatalogCacheValue::KeyStats(items) => Ok(items),
            _ => Ok(Vec::new()),
        }
    }
}

#[derive(Clone, Debug, Eq, Hash, PartialEq)]
enum ProviderCatalogCacheKey {
    Providers { active_only: bool },
    ProvidersByIds(Vec<String>),
    EndpointsByProviderIds(Vec<String>),
    KeysByProviderIds(Vec<String>),
    KeySummariesByProviderIds(Vec<String>),
    KeyMaintenanceSummariesByProviderIds(Vec<String>),
    KeyStatsByProviderIds(Vec<String>),
}

#[derive(Clone)]
enum ProviderCatalogCacheValue {
    Providers(Vec<StoredProviderCatalogProvider>),
    Endpoints(Vec<StoredProviderCatalogEndpoint>),
    Keys(Vec<StoredProviderCatalogKey>),
    KeyMaintenanceSummaries(Vec<StoredProviderCatalogKeyMaintenanceSummary>),
    KeyStats(Vec<StoredProviderCatalogKeyStats>),
}

enum InflightRegistration {
    Leader(u64),
    Follower,
    Bypass,
}

struct InflightGuard<'a> {
    cache: &'a CachedProviderCatalogReadRepository,
    key: Option<ProviderCatalogCacheKey>,
    token: u64,
}

impl<'a> InflightGuard<'a> {
    fn new(
        cache: &'a CachedProviderCatalogReadRepository,
        key: ProviderCatalogCacheKey,
        token: u64,
    ) -> Self {
        Self {
            cache,
            key: Some(key),
            token,
        }
    }

    fn finish(&mut self) {
        if let Some(key) = self.key.take() {
            self.cache.finish_inflight(&key, self.token);
        }
    }
}

impl Drop for InflightGuard<'_> {
    fn drop(&mut self) {
        self.finish();
    }
}

fn normalize_ids(ids: &[String]) -> Vec<String> {
    let mut normalized = ids
        .iter()
        .map(|id| id.trim())
        .filter(|id| !id.is_empty())
        .map(ToOwned::to_owned)
        .collect::<Vec<_>>();
    normalized.sort();
    normalized.dedup();
    normalized
}
