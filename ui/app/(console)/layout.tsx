import { redirect } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ApiError, getMe } from "@/lib/api";

/**
 * Auth gate + AppShell wrapper for every route under (console)/.
 *
 * Runs server-side on every request to this route group. Fetches /api/me
 * with the session cookie; if 401, redirects to /login. Otherwise wraps
 * the page in AppShell with the session passed as a prop.
 */
export default async function ConsoleLayout({ children }: { children: React.ReactNode }) {
  let session;
  try {
    session = await getMe();
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    throw err;
  }

  return <AppShell session={session}>{children}</AppShell>;
}
