import { UsersView } from "@/components/users/UsersView";
import { getMe, listUsersServer } from "@/lib/api";

/**
 * Server-side entry for /users. Fetches session + users in parallel,
 * then renders UsersView with the data + current user id (for the "you"
 * badge + self-delete guard) + admin flag.
 *
 * (console)/layout.tsx hides the Users nav item from non-admins, but
 * if a member navigates here directly the page still renders read-only.
 */
export default async function UsersPage() {
  const [session, users] = await Promise.all([getMe(), listUsersServer()]);
  return (
    <UsersView
      initial={users}
      currentUserId={session.user.id}
      isAdmin={session.user.role === "admin"}
    />
  );
}
