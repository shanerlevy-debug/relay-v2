/**
 * Typed fetch wrappers for the FastAPI gateway.
 *
 * Client-side (in browser): use `apiFetch(path)`. Goes to /api/* which
 * Next.js rewrites to the backend in dev (via next.config.mjs). The
 * session cookie flows automatically since both UI and rewrite share
 * the same origin from the browser's POV.
 *
 * Server-side (in React Server Components): use `serverFetch(path)`.
 * Hits the API URL directly and forwards the request's cookies. Reads
 * the cookie header from `next/headers` automatically.
 *
 * Both wrappers translate the API's `{error: {code, message, status}}`
 * envelope into a typed `ApiError`.
 */

const SERVER_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types — mirror the Pydantic schemas in api/relay_api/schemas/
// ---------------------------------------------------------------------------

export interface UserOut {
  id: string;
  email: string;
  role: "admin" | "member";
  workspace_id: string;
  email_verified_at: string | null;
  created_at: string;
}

export interface WorkspaceOut {
  id: string;
  display_name: string;
  slack_team_id: string | null;
  created_at: string;
}

export interface SessionOut {
  user: UserOut;
  workspace: WorkspaceOut;
}

export interface SignupRequest {
  email: string;
  password: string;
  workspace_name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ApiErrorBody {
  error?: {
    code?: string;
    message?: string;
    status?: number;
  };
}

async function throwFromResponse(res: Response): Promise<never> {
  let body: ApiErrorBody | null = null;
  try {
    body = (await res.json()) as ApiErrorBody;
  } catch {
    // Non-JSON response (rare — Next.js rewrites occasionally produce HTML)
  }
  throw new ApiError(
    res.status,
    body?.error?.code ?? "unknown",
    body?.error?.message ?? res.statusText ?? "request failed",
  );
}

// ---------------------------------------------------------------------------
// Client-side fetch (browser → /api/* → Next rewrite → FastAPI)
// ---------------------------------------------------------------------------

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    await throwFromResponse(res);
  }
  // 204 No Content has no body
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Server-side fetch (React Server Components → FastAPI directly)
// ---------------------------------------------------------------------------

/**
 * Server-side fetch. Reads cookies via next/headers automatically.
 *
 * Use ONLY in Server Components, Route Handlers, or Server Actions.
 * For client-side calls, use `apiFetch` instead.
 */
export async function serverFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const { cookies } = await import("next/headers");
  const cookieHeader = (await cookies()).toString();

  const res = await fetch(`${SERVER_API_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Cookie: cookieHeader,
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    await throwFromResponse(res);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Typed endpoints
// ---------------------------------------------------------------------------

export async function getMe(): Promise<SessionOut> {
  return serverFetch<SessionOut>("/api/me");
}

export async function login(req: LoginRequest): Promise<SessionOut> {
  return apiFetch<SessionOut>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function signup(req: SignupRequest): Promise<SessionOut> {
  return apiFetch<SessionOut>("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function logout(): Promise<void> {
  return apiFetch<void>("/api/auth/logout", { method: "POST" });
}

// ---------------------------------------------------------------------------
// Agents
// ---------------------------------------------------------------------------

export interface AgentOut {
  id: string;
  workspace_id: string;
  slug: string;
  anthropic_agent_id: string;
  environment_id: string;
  description: string | null;
  is_default: boolean;
  created_at: string;
  archived_at: string | null;
}

export interface AgentSeats {
  active: number;
  cap: number;
}

export interface AgentListOut {
  agents: AgentOut[];
  seats: AgentSeats;
}

export interface AgentCreateRequest {
  slug: string;
  anthropic_agent_id: string;
  environment_id: string;
  description?: string | null;
  is_default?: boolean;
}

export interface AgentUpdateRequest {
  slug?: string;
  anthropic_agent_id?: string;
  environment_id?: string;
  description?: string | null;
  is_default?: boolean;
}

export async function listAgents(): Promise<AgentListOut> {
  return apiFetch<AgentListOut>("/api/agents");
}

export async function listAgentsServer(): Promise<AgentListOut> {
  return serverFetch<AgentListOut>("/api/agents");
}

export async function createAgent(req: AgentCreateRequest): Promise<AgentOut> {
  return apiFetch<AgentOut>("/api/agents", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function updateAgent(id: string, req: AgentUpdateRequest): Promise<AgentOut> {
  return apiFetch<AgentOut>(`/api/agents/${id}`, {
    method: "PATCH",
    body: JSON.stringify(req),
  });
}

export async function archiveAgent(id: string): Promise<void> {
  return apiFetch<void>(`/api/agents/${id}`, { method: "DELETE" });
}
