// ---------------------------------------------------------------------------
// Raw backend response types (snake_case, loose types)
// ---------------------------------------------------------------------------

export interface RawResource {
  id: string
  name: string
  type: string                // 'solar' | 'battery' | 'wind' | 'ev_charger'
  status: string              // 'online' | 'offline' | 'maintenance'
  capacity_kw: number | string
  device_count: number | string   // backend sometimes returns string
  latitude: number | string
  longitude: number | string
  owner_id: string
  region: string
  created_at: string
  updated_at: string
}

export interface RawContract {
  id: string
  resource_id: string
  owner_name: string
  start_date: string          // ISO 8601, e.g. "2024-01-15 10:30:00" or "2024-01-15T10:30:00Z"
  end_date: string
  power_commitment_kw: number | string
  price_per_kwh: number | string
  status: string              // 'active' | 'expired' | 'pending' | 'terminated'
  signed_at: string
}

export interface RawDispatch {
  id: string
  resource_id: string
  command: string             // 'charge' | 'discharge' | 'curtail' | 'restore'
  power_kw: number | string
  scheduled_at: string
  executed_at: string | null
  status: string              // 'pending' | 'executed' | 'failed' | 'cancelled'
  operator_id: string
}

export interface RawAggregation {
  region: string
  total_capacity_kw: number | string
  active_resources: number | string
  total_devices: number | string
  avg_utilization: number | string
  timestamp: string
}

// ---------------------------------------------------------------------------
// Normalized frontend types (camelCase, strict types)
// ---------------------------------------------------------------------------

export type ResourceType = 'solar' | 'battery' | 'wind' | 'ev_charger'
export type ResourceStatus = 'online' | 'offline' | 'maintenance'

export interface Resource {
  id: string
  name: string
  type: ResourceType
  status: ResourceStatus
  capacityKw: number
  deviceCount: number
  latitude: number
  longitude: number
  ownerId: string
  region: string
  createdAt: Date
  updatedAt: Date
}

export type ContractStatus = 'active' | 'expired' | 'pending' | 'terminated'

export interface Contract {
  id: string
  resourceId: string
  ownerName: string
  startDate: Date
  endDate: Date
  powerCommitmentKw: number
  pricePerKwh: number
  status: ContractStatus
  isExpired: boolean
  signedAt: Date
}

export type DispatchCommand = 'charge' | 'discharge' | 'curtail' | 'restore'
export type DispatchStatus = 'pending' | 'executed' | 'failed' | 'cancelled'

export interface Dispatch {
  id: string
  resourceId: string
  command: DispatchCommand
  powerKw: number
  scheduledAt: Date
  executedAt: Date | null
  status: DispatchStatus
  operatorId: string
}

export interface Aggregation {
  region: string
  totalCapacityKw: number
  activeResources: number
  totalDevices: number
  avgUtilization: number
  timestamp: Date
}
