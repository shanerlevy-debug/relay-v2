import { redirect } from "next/navigation";

import { GroupsView } from "@/components/groups/GroupsView";
import { getMe, listGroupsServer } from "@/lib/api";

/**
 * Server-side entry for /groups. Admin-only: members are bounced to
 * /home (matches the AppShell nav's adminOnly flag). The initial list
 * comes back as part of the SSR response; the view fetches details on
 * demand when the admin clicks into a group.
 */
export default async function GroupsPage() {
  const session = await getMe();
  if (session.user.role !== "admin") {
    redirect("/home");
  }
  const initial = await listGroupsServer();
  return <GroupsView initial={initial} />;
}
