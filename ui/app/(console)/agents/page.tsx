import { AgentsView } from "@/components/agents/AgentsView";
import { getMe, listAgentsServer } from "@/lib/api";

/**
 * Server-side entry for /agents. Fetches the session + initial agents
 * list in parallel, then renders the client-side AgentsView with that
 * data as initial state. Mutations happen via client-side apiFetch.
 */
export default async function AgentsPage() {
  const [session, agents] = await Promise.all([getMe(), listAgentsServer()]);
  return <AgentsView initial={agents} isAdmin={session.user.role === "admin"} />;
}
