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
  slack_display_name: string | null;
  slack_icon_url: string | null;
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
  slack_display_name?: string | null;
  slack_icon_url?: string | null;
}

export interface AgentUpdateRequest {
  slug?: string;
  anthropic_agent_id?: string;
  environment_id?: string;
  description?: string | null;
  is_default?: boolean;
  slack_display_name?: string | null;
  slack_icon_url?: string | null;
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

export async function uploadAgentIcon(id: string, file: File): Promise<AgentOut> {
  // Raw fetch — apiFetch() hard-codes Content-Type: application/json, which
  // would smother the multipart boundary the browser sets for FormData.
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`/api/agents/${id}/icon`, {
    method: "POST",
    body: form,
    credentials: "include",
  });
  if (!res.ok) {
    await throwFromResponse(res);
  }
  return res.json() as Promise<AgentOut>;
}

export async function deleteAgentIcon(id: string): Promise<AgentOut> {
  return apiFetch<AgentOut>(`/api/agents/${id}/icon`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// CMA discovery — browse-and-pick Add Agent
// ---------------------------------------------------------------------------

export interface CmaAgentSummary {
  id: string;
  model: string | null;
  system: string | null;
  archived_at: string | null;
}

export interface CmaEnvironmentSummary {
  id: string;
  name: string | null;
  networking_type: string | null;
}

export interface CmaAgentsList {
  agents: CmaAgentSummary[];
}

export interface CmaEnvironmentsList {
  environments: CmaEnvironmentSummary[];
  /** Last environment used in this workspace — the picker pre-selects this. */
  default_environment_id: string | null;
}

export async function listCmaAgents(): Promise<CmaAgentsList> {
  return apiFetch<CmaAgentsList>("/api/cma/agents");
}

export async function listCmaEnvironments(): Promise<CmaEnvironmentsList> {
  return apiFetch<CmaEnvironmentsList>("/api/cma/environments");
}

// ---------------------------------------------------------------------------
// Groups — positive-grant access control
// ---------------------------------------------------------------------------

export interface GroupOut {
  id: string;
  workspace_id: string;
  name: string;
  is_default: boolean;
  created_at: string;
  archived_at: string | null;
}

export interface GroupSummary {
  id: string;
  name: string;
  is_default: boolean;
}

export interface GroupMemberUser {
  id: string;
  email: string;
  role: "admin" | "member";
}

export interface GroupMemberAgent {
  id: string;
  slug: string;
  slack_display_name: string | null;
  slack_icon_url: string | null;
}

export interface GroupMembersOut {
  group: GroupOut;
  users: GroupMemberUser[];
  agents: GroupMemberAgent[];
}

export interface GroupListOut {
  groups: GroupOut[];
}

export interface GroupMembershipMap {
  users: Record<string, GroupSummary[]>;
  agents: Record<string, GroupSummary[]>;
}

export async function listGroups(): Promise<GroupListOut> {
  return apiFetch<GroupListOut>("/api/groups");
}

export async function listGroupsServer(): Promise<GroupListOut> {
  return serverFetch<GroupListOut>("/api/groups");
}

export async function getGroup(id: string): Promise<GroupMembersOut> {
  return apiFetch<GroupMembersOut>(`/api/groups/${id}`);
}

export async function createGroup(name: string): Promise<GroupOut> {
  return apiFetch<GroupOut>("/api/groups", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function renameGroup(id: string, name: string): Promise<GroupOut> {
  return apiFetch<GroupOut>(`/api/groups/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export async function archiveGroup(id: string): Promise<void> {
  return apiFetch<void>(`/api/groups/${id}`, { method: "DELETE" });
}

export async function addUserToGroup(
  groupId: string,
  userId: string,
): Promise<void> {
  return apiFetch<void>(`/api/groups/${groupId}/users/${userId}`, {
    method: "PUT",
  });
}

export async function removeUserFromGroup(
  groupId: string,
  userId: string,
): Promise<void> {
  return apiFetch<void>(`/api/groups/${groupId}/users/${userId}`, {
    method: "DELETE",
  });
}

export async function addAgentToGroup(
  groupId: string,
  agentId: string,
): Promise<void> {
  return apiFetch<void>(`/api/groups/${groupId}/agents/${agentId}`, {
    method: "PUT",
  });
}

export async function removeAgentFromGroup(
  groupId: string,
  agentId: string,
): Promise<void> {
  return apiFetch<void>(`/api/groups/${groupId}/agents/${agentId}`, {
    method: "DELETE",
  });
}

export async function getGroupMemberships(): Promise<GroupMembershipMap> {
  return apiFetch<GroupMembershipMap>("/api/groups/memberships");
}

export async function getGroupMembershipsServer(): Promise<GroupMembershipMap> {
  return serverFetch<GroupMembershipMap>("/api/groups/memberships");
}

// ---------------------------------------------------------------------------
// Users + invites
// ---------------------------------------------------------------------------

export interface UserListItem {
  id: string;
  email: string;
  role: "admin" | "member";
  email_verified_at: string | null;
  created_at: string;
}

export interface InviteOut {
  id: string;
  email: string;
  role: "admin" | "member";
  expires_at: string;
  created_at: string;
  created_by_user_id: string | null;
}

export interface WorkspaceSeats {
  active: number;
  pending_invites: number;
  cap: number;
}

export interface UserListOut {
  users: UserListItem[];
  pending_invites: InviteOut[];
  seats: WorkspaceSeats;
}

export interface InviteCreateRequest {
  email: string;
  role?: "admin" | "member";
}

export interface InviteCreateResponse {
  invite: InviteOut;
  invite_url: string;
}

export async function listUsers(): Promise<UserListOut> {
  return apiFetch<UserListOut>("/api/users");
}

export async function listUsersServer(): Promise<UserListOut> {
  return serverFetch<UserListOut>("/api/users");
}

export async function inviteUser(req: InviteCreateRequest): Promise<InviteCreateResponse> {
  return apiFetch<InviteCreateResponse>("/api/users/invite", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function deleteUser(id: string): Promise<void> {
  return apiFetch<void>(`/api/users/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Anthropic key (BYOK)
// ---------------------------------------------------------------------------

export interface AnthropicKeyStatus {
  has_key: boolean;
  created_at: string | null;
  updated_at: string | null;
  created_by_user_id: string | null;
}

export async function getAnthropicKeyStatus(): Promise<AnthropicKeyStatus> {
  return apiFetch<AnthropicKeyStatus>("/api/workspace/anthropic-key");
}

export async function getAnthropicKeyStatusServer(): Promise<AnthropicKeyStatus> {
  return serverFetch<AnthropicKeyStatus>("/api/workspace/anthropic-key");
}

export async function setAnthropicKey(key: string): Promise<AnthropicKeyStatus> {
  return apiFetch<AnthropicKeyStatus>("/api/workspace/anthropic-key", {
    method: "PUT",
    body: JSON.stringify({ key }),
  });
}

export async function deleteAnthropicKey(): Promise<void> {
  return apiFetch<void>("/api/workspace/anthropic-key", { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Audit log
// ---------------------------------------------------------------------------

export interface AuditLogEntry {
  id: string;
  event_type: string;
  subject_type: string;
  subject_id: string | null;
  actor_user_id: string | null;
  actor_email: string | null;
  metadata_json: Record<string, unknown>;
  occurred_at: string;
}

export interface AuditListOut {
  entries: AuditLogEntry[];
  has_more: boolean;
}

export async function listAudit(limit = 50, offset = 0): Promise<AuditListOut> {
  return apiFetch<AuditListOut>(`/api/audit?limit=${limit}&offset=${offset}`);
}

export async function listAuditServer(limit = 50, offset = 0): Promise<AuditListOut> {
  return serverFetch<AuditListOut>(`/api/audit?limit=${limit}&offset=${offset}`);
}
