export type RiskTier = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export type UserRole = 'ADMIN' | 'SUPERVISOR' | 'AUTHORITY_OFFICER' | 'REVIEWER';

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  badge_id: string;
  role: UserRole | string;
  jurisdiction_state?: string | null;
  jurisdiction_district?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
}

export interface DatabaseHealth {
  status: 'connected' | 'disconnected';
  latency_ms?: number;
  error?: string | null;
}

export interface SystemHealth {
  status: string;
  project: string;
  version: string;
  environment: string;
  timestamp: string;
  database?: DatabaseHealth;
}

export interface MetricCardData {
  title: string;
  value: string | number;
  change?: string;
  trend?: 'up' | 'down' | 'neutral';
  description: string;
  badge?: string;
}

export interface CaseSummary {
  id: string;
  case_number: string;
  title: string;
  status: string;
  priority: string;
  jurisdiction_district?: string | null;
  created_at: string;
}
