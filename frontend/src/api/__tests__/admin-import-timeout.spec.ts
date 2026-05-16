import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { AggregateImportRequest, ConfigImportRequest, UsersImportRequest } from '@/api/admin'

const { postMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  default: {
    post: postMock,
  },
}))

import { adminApi } from '@/api/admin'

const SYSTEM_DATA_IMPORT_TIMEOUT_MS = 10 * 60 * 1000

describe('adminApi system data import timeouts', () => {
  beforeEach(() => {
    postMock.mockReset()
    postMock.mockResolvedValue({ data: {} })
  })

  it('uses a long timeout for config imports', async () => {
    const payload = {
      version: '1',
      exported_at: '2026-01-01T00:00:00.000Z',
      global_models: [],
      providers: [],
      merge_mode: 'skip',
    } satisfies ConfigImportRequest

    await adminApi.importConfig(payload)

    expect(postMock).toHaveBeenCalledWith(
      '/api/admin/system/config/import',
      payload,
      { timeout: SYSTEM_DATA_IMPORT_TIMEOUT_MS }
    )
  })

  it('uses a long timeout for user imports', async () => {
    const payload = {
      version: '1',
      exported_at: '2026-01-01T00:00:00.000Z',
      users: [],
      merge_mode: 'skip',
    } satisfies UsersImportRequest

    await adminApi.importUsers(payload)

    expect(postMock).toHaveBeenCalledWith(
      '/api/admin/system/users/import',
      payload,
      { timeout: SYSTEM_DATA_IMPORT_TIMEOUT_MS }
    )
  })

  it('uses a long timeout for aggregate imports', async () => {
    const payload = {
      version: '1',
      exported_at: '2026-01-01T00:00:00.000Z',
      config_data: {
        version: '1',
        exported_at: '2026-01-01T00:00:00.000Z',
        global_models: [],
        providers: [],
      },
      user_data: {
        version: '1',
        exported_at: '2026-01-01T00:00:00.000Z',
        users: [],
      },
      merge_mode: 'skip',
    } satisfies AggregateImportRequest

    await adminApi.importAggregateData(payload)

    expect(postMock).toHaveBeenCalledWith(
      '/api/admin/system/data/import',
      payload,
      { timeout: SYSTEM_DATA_IMPORT_TIMEOUT_MS }
    )
  })
})
