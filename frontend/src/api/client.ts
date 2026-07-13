import type {
  UserResponse,
  TokenResponse,
  StudySessionResponse,
  StudySessionDetail,
  HeartbeatResponse,
  SessionCheckResponse,
  BalanceResponse,
  LedgerEntryResponse,
  RedeemRequest,
  RedemptionResponse,
  RedemptionTier,
  SubscriptionPlan,
  SubscriptionStatus,
  SubscriptionPlanName,
  InitializeSubscriptionResponse,
  SubscriptionResponse,
  QuizOut,
  QuizResultOut,
  PointsLeaderboardEntry,
  StreakLeaderboardEntry,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const ACCESS_TOKEN_KEY = "convex.access_token";
const REFRESH_TOKEN_KEY = "convex.refresh_token";

export const tokenStore = {
  get access() {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },
  set(tokens: TokenResponse) {
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// FastAPI errors are either {"detail": "message"} or, on validation failures,
// {"detail": [{"msg": "...", ...}, ...]}.
function extractMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => (item && typeof item === "object" && "msg" in item ? String((item as { msg: unknown }).msg) : String(item)))
        .join(" ");
    }
  }
  return fallback;
}

let refreshInFlight: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const refresh_token = tokenStore.refresh;
  if (!refresh_token) return false;

  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token }),
    })
      .then(async (res) => {
        if (!res.ok) return false;
        const tokens = (await res.json()) as TokenResponse;
        tokenStore.set(tokens);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  form?: Record<string, string>;
  formData?: FormData;
  auth?: boolean;
  /** Internal: prevents infinite refresh loops. */
  _retried?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, form, formData, auth = true, _retried = false } = opts;

  const headers: Record<string, string> = {};
  let requestBody: BodyInit | undefined;

  if (formData) {
    // No Content-Type here - the browser sets the multipart boundary itself.
    requestBody = formData;
  } else if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    requestBody = new URLSearchParams(form).toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    requestBody = JSON.stringify(body);
  }

  if (auth && tokenStore.access) {
    headers["Authorization"] = `Bearer ${tokenStore.access}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { method, headers, body: requestBody });

  if (res.status === 401 && auth && !_retried) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      return request<T>(path, { ...opts, _retried: true });
    }
    tokenStore.clear();
    throw new ApiError(401, "Your session expired. Please sign in again.");
  }

  if (!res.ok) {
    let payload: unknown = null;
    try {
      payload = await res.json();
    } catch {
      // non-JSON error body, fall through to the generic message
    }
    throw new ApiError(res.status, extractMessage(payload, `Request failed (${res.status}).`));
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ----------------- Auth -----------------

export function register(input: {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
}): Promise<UserResponse> {
  return request("/auth/register", { method: "POST", body: input, auth: false });
}

export async function login(username: string, password: string): Promise<TokenResponse> {
  const tokens = await request<TokenResponse>("/auth/login", {
    method: "POST",
    form: { username, password },
    auth: false,
  });
  tokenStore.set(tokens);
  return tokens;
}

export async function logout(): Promise<void> {
  const refresh_token = tokenStore.refresh;
  tokenStore.clear();
  if (!refresh_token) return;
  try {
    await request("/auth/logout", { method: "POST", body: { refresh_token }, auth: false });
  } catch {
    // best-effort: the local tokens are already cleared either way
  }
}

export function getCurrentUser(): Promise<UserResponse> {
  return request("/users/me");
}

// ----------------- Study Sessions -----------------

export function listSessions(): Promise<StudySessionResponse[]> {
  return request("/study-sessions");
}

export function getSession(id: number): Promise<StudySessionDetail> {
  return request(`/study-sessions/${id}`);
}

export function startSession(subject_tag: string | null): Promise<StudySessionResponse> {
  return request("/study-sessions/start", { method: "POST", body: { subject_tag } });
}

export function startGuidedSession(input: {
  subject_tag: string;
  target_minutes: number;
  material: File;
}): Promise<StudySessionResponse> {
  const formData = new FormData();
  formData.append("subject_tag", input.subject_tag);
  formData.append("target_minutes", String(input.target_minutes));
  formData.append("material", input.material);
  return request("/study-sessions/start-guided", { method: "POST", formData });
}

export function sendHeartbeat(id: number): Promise<HeartbeatResponse> {
  return request(`/study-sessions/${id}/heartbeat`, { method: "POST" });
}

export function pauseSession(id: number): Promise<StudySessionResponse> {
  return request(`/study-sessions/${id}/pause`, { method: "POST" });
}

export function resumeSession(id: number): Promise<StudySessionResponse> {
  return request(`/study-sessions/${id}/resume`, { method: "POST" });
}

export function respondToCheck(
  sessionId: number,
  checkId: number,
  responseText: string
): Promise<SessionCheckResponse> {
  return request(`/study-sessions/${sessionId}/checks/${checkId}/respond`, {
    method: "POST",
    body: { response: responseText },
  });
}

export function endSession(id: number, summary_text: string): Promise<StudySessionDetail> {
  return request(`/study-sessions/${id}/end`, { method: "POST", body: { summary_text } });
}

export function getQuiz(sessionId: number): Promise<QuizOut> {
  return request(`/study-sessions/${sessionId}/quiz`);
}

export function submitQuiz(sessionId: number, answers: number[]): Promise<QuizResultOut> {
  return request(`/study-sessions/${sessionId}/quiz/submit`, { method: "POST", body: { answers } });
}

// ----------------- Rewards -----------------

export function getBalance(): Promise<BalanceResponse> {
  return request("/rewards/balance");
}

export function getRedemptionTiers(): Promise<RedemptionTier[]> {
  return request("/rewards/redemption-tiers", { auth: false });
}

export function getLedger(): Promise<LedgerEntryResponse[]> {
  return request("/rewards/ledger");
}

export function redeemPoints(redeem_in: RedeemRequest): Promise<RedemptionResponse> {
  return request("/rewards/redeem", { method: "POST", body: redeem_in });
}

export function getRedemptions(): Promise<RedemptionResponse[]> {
  return request("/rewards/redemptions");
}

// ----------------- Leaderboard -----------------

export function getPointsLeaderboard(): Promise<PointsLeaderboardEntry[]> {
  return request("/leaderboard/points");
}

export function getStreakLeaderboard(): Promise<StreakLeaderboardEntry[]> {
  return request("/leaderboard/streaks");
}

// ----------------- Subscriptions -----------------

export function getSubscriptionPlans(): Promise<SubscriptionPlan[]> {
  return request("/subscriptions/plans", { auth: false });
}

export function getSubscriptionStatus(): Promise<SubscriptionStatus> {
  return request("/subscriptions/status");
}

export function initializeSubscription(plan: SubscriptionPlanName): Promise<InitializeSubscriptionResponse> {
  return request("/subscriptions/initialize", { method: "POST", body: { plan } });
}

export function verifySubscription(reference: string): Promise<SubscriptionResponse> {
  return request("/subscriptions/verify", { method: "POST", body: { reference } });
}

export function getSubscriptionHistory(): Promise<SubscriptionResponse[]> {
  return request("/subscriptions/history");
}
