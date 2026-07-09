// Mirrors app/schemas/user.py, app/schemas/study_session.py, and app/schemas/reward.py on the backend.

export interface UserResponse {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
  last_login: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export type SessionStatus = "active" | "paused" | "completed" | "flagged";
export type CheckType = "attention" | "recall" | "summary";

export interface SessionCheckResponse {
  id: number;
  check_type: CheckType;
  prompt: string | null;
  triggered_at: string;
  expires_at: string;
  responded_at: string | null;
  passed: boolean | null;
}

export interface StudySessionResponse {
  id: number;
  subject_tag: string | null;
  status: SessionStatus;
  started_at: string;
  ended_at: string | null;
  accumulated_seconds: number;
  verified_minutes: number;
  flag_reason: string | null;
}

export interface StudySessionDetail extends StudySessionResponse {
  summary_text: string | null;
  checks: SessionCheckResponse[];
}

export interface HeartbeatResponse {
  status: SessionStatus;
  accumulated_seconds: number;
  pending_check: SessionCheckResponse | null;
}

export interface BalanceResponse {
  points: number;
}

export interface LedgerEntryResponse {
  id: number;
  session_id: number | null;
  points: number;
  reason: string;
  created_at: string;
}

export interface RedemptionTier {
  ghs_amount: number;
  kp_cost: number;
}

export type MobileNetwork = "mtn" | "telecel" | "airteltigo";

export interface RedeemRequest {
  ghs_amount: number;
  recipient_phone: string;
  network: MobileNetwork;
}

export type RedemptionStatus = "pending" | "completed" | "failed";

export interface RedemptionResponse {
  id: number;
  points_spent: number;
  ghs_amount: number;
  reward_type: string;
  status: RedemptionStatus;
  provider_ref: string | null;
  recipient_phone: string;
  network: string;
  created_at: string;
}

export type SubscriptionPlanName = "monthly" | "quarterly" | "annual";

export interface SubscriptionPlan {
  plan: SubscriptionPlanName;
  ghs_amount: number;
  duration_days: number;
}

export interface SubscriptionStatus {
  is_active: boolean;
  plan: string | null;
  expires_at: string | null;
}

export interface InitializeSubscriptionResponse {
  authorization_url: string;
  reference: string;
}

export type SubscriptionPaymentStatus = "pending" | "active" | "failed";

export interface SubscriptionResponse {
  id: number;
  plan: string;
  ghs_amount: number;
  status: SubscriptionPaymentStatus;
  started_at: string | null;
  expires_at: string | null;
  created_at: string;
}
