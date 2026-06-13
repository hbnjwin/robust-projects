import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

import type {
  RawResource,
  RawContract,
  RawDispatch,
  RawAggregation,
  Resource,
  Contract,
  Dispatch,
  Aggregation,
  ResourceType,
  ResourceStatus,
  ContractStatus,
  DispatchCommand,
  DispatchStatus,
} from '@/types/vpp'

import { parseDateSafe } from '@/utils/date'
import { tauriInvoke } from '@/utils/env'

// ---------------------------------------------------------------------------
// Normalizer functions
// ---------------------------------------------------------------------------

/**
 * Normalise a raw resource from the backend into the typed frontend model.
 *
 * BUG (fixed): `device_count` and `capacity_kw` arrive as strings from
 * some backend endpoints (e.g. "5" instead of 5). When these values were
 * used in arithmetic like `totalPower += resource.capacityKw * resource.deviceCount`,
 * JavaScript's implicit coercion turned the expression into string
 * concatenation: "100" + "200" → "100200" instead of 300.
 *
 * FIX: Explicitly coerce every numeric field with `Number()` at the
 * normalisation boundary so downstream code always operates on real numbers.
 */
export function normalizeResource(raw: RawResource): Resource {
  return {
    id: raw.id,
    name: raw.name,
    type: raw.type as ResourceType,
    status: raw.status as ResourceStatus,
    capacityKw: Number(raw.capacity_kw),
    deviceCount: Number(raw.device_count),
    latitude: Number(raw.latitude),
    longitude: Number(raw.longitude),
    ownerId: raw.owner_id,
    region: raw.region,
    createdAt: parseDateSafe(raw.created_at),
    updatedAt: parseDateSafe(raw.updated_at),
  }
}

/**
 * Normalise a raw contract into the typed frontend model.
 *
 * BUG (fixed): `start_date` / `end_date` were parsed with bare
 * `new Date(str)`, which fails in Safari for ISO strings that use a
 * space separator (e.g. "2024-01-15 10:30:00") — returning Invalid Date.
 * The subsequent `endDate < new Date()` comparison always evaluated to
 * `false`, so expired contracts were never flagged.
 *
 * FIX: Use `parseDateSafe()` which normalises the string to a
 * Safari-compatible format before constructing the Date, and throws
 * eagerly on unparseable input.
 */
export function normalizeContract(raw: RawContract): Contract {
  const startDate = parseDateSafe(raw.start_date)
  const endDate = parseDateSafe(raw.end_date)

  // Compare timestamps (numbers), not Date objects, to avoid subtle
  // coercion pitfalls with relational operators on objects.
  const isExpired =
    raw.status === 'expired' || endDate.getTime() < Date.now()

  return {
    id: raw.id,
    resourceId: raw.resource_id,
    ownerName: raw.owner_name,
    startDate,
    endDate,
    powerCommitmentKw: Number(raw.power_commitment_kw),
    pricePerKwh: Number(raw.price_per_kwh),
    status: (isExpired ? 'expired' : raw.status) as ContractStatus,
    isExpired,
    signedAt: parseDateSafe(raw.signed_at),
  }
}

export function normalizeDispatch(raw: RawDispatch): Dispatch {
  return {
    id: raw.id,
    resourceId: raw.resource_id,
    command: raw.command as DispatchCommand,
    powerKw: Number(raw.power_kw),
    scheduledAt: parseDateSafe(raw.scheduled_at),
    executedAt: raw.executed_at ? parseDateSafe(raw.executed_at) : null,
    status: raw.status as DispatchStatus,
    operatorId: raw.operator_id,
  }
}

export function normalizeAggregation(raw: RawAggregation): Aggregation {
  return {
    region: raw.region,
    totalCapacityKw: Number(raw.total_capacity_kw),
    activeResources: Number(raw.active_resources),
    totalDevices: Number(raw.total_devices),
    avgUtilization: Number(raw.avg_utilization),
    timestamp: parseDateSafe(raw.timestamp),
  }
}

// ---------------------------------------------------------------------------
// Mock data for non-Tauri (web) development
// ---------------------------------------------------------------------------

const MOCK_RESOURCES: RawResource[] = [
  {
    id: 'res-001', name: 'Rooftop Solar A', type: 'solar', status: 'online',
    capacity_kw: 250, device_count: 40, latitude: 31.23, longitude: 121.47,
    owner_id: 'usr-01', region: 'east', created_at: '2024-03-10T08:00:00Z',
    updated_at: '2024-06-01T12:00:00Z',
  },
]

const MOCK_CONTRACTS: RawContract[] = [
  {
    id: 'ctr-001', resource_id: 'res-001', owner_name: 'Acme Energy',
    start_date: '2024-01-01T00:00:00Z', end_date: '2025-12-31T23:59:59Z',
    power_commitment_kw: 200, price_per_kwh: 0.35, status: 'active',
    signed_at: '2023-12-15T09:30:00Z',
  },
]

// ---------------------------------------------------------------------------
// Pinia store
// ---------------------------------------------------------------------------

export const useVppStore = defineStore('vpp', () => {
  const resources = ref<Resource[]>([])
  const contracts = ref<Contract[]>([])
  const dispatches = ref<Dispatch[]>([])
  const aggregations = ref<Aggregation[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Derived state — relies on capacityKw and deviceCount being actual
  // numbers, not strings. Before the fix this produced garbage like "100200".
  const totalPower = computed(() =>
    resources.value.reduce((sum, r) => sum + r.capacityKw * r.deviceCount, 0),
  )

  const activeContracts = computed(() =>
    contracts.value.filter((c) => !c.isExpired),
  )

  const onlineResources = computed(() =>
    resources.value.filter((r) => r.status === 'online'),
  )

  // -----------------------------------------------------------------------
  // Actions – fetch from Tauri backend, falling back to mocks when running
  // in the browser during development.
  // -----------------------------------------------------------------------

  async function fetchResources() {
    loading.value = true
    error.value = null
    try {
      const rawList = await tauriInvoke<RawResource[]>(
        'get_resources',
        undefined,
        () => MOCK_RESOURCES,
      )
      resources.value = rawList.map(normalizeResource)
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  async function fetchContracts() {
    loading.value = true
    error.value = null
    try {
      const rawList = await tauriInvoke<RawContract[]>(
        'get_contracts',
        undefined,
        () => MOCK_CONTRACTS,
      )
      contracts.value = rawList.map(normalizeContract)
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  async function fetchDispatches() {
    loading.value = true
    error.value = null
    try {
      const rawList = await tauriInvoke<RawDispatch[]>(
        'get_dispatches',
        undefined,
        () => [],
      )
      dispatches.value = rawList.map(normalizeDispatch)
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  async function fetchAggregations() {
    loading.value = true
    error.value = null
    try {
      const rawList = await tauriInvoke<RawAggregation[]>(
        'get_aggregations',
        undefined,
        () => [],
      )
      aggregations.value = rawList.map(normalizeAggregation)
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  async function dispatchCommand(
    resourceId: string,
    command: DispatchCommand,
    powerKw: number,
  ) {
    error.value = null
    try {
      const raw = await tauriInvoke<RawDispatch>('send_dispatch', {
        resourceId,
        command,
        powerKw,
      })
      dispatches.value.push(normalizeDispatch(raw))
    } catch (e) {
      error.value = (e as Error).message
    }
  }

  return {
    // state
    resources,
    contracts,
    dispatches,
    aggregations,
    loading,
    error,

    // getters
    totalPower,
    activeContracts,
    onlineResources,

    // actions
    fetchResources,
    fetchContracts,
    fetchDispatches,
    fetchAggregations,
    dispatchCommand,

    // expose normalizers for testing
    normalizeResource,
    normalizeContract,
    normalizeDispatch,
    normalizeAggregation,
  }
})
