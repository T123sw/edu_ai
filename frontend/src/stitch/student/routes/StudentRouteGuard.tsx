import { useEffect, type PropsWithChildren } from "react";

import { useAuthSession } from "../../authSession";
import { defaultHashForRole } from "../../shared/routes/roleRouteResolver";

export function StudentRouteGuard({ children }: PropsWithChildren) {
  const { user } = useAuthSession();

  useEffect(() => {
    if (user && user.role !== "student") {
      window.location.replace(defaultHashForRole(user.role));
    }
  }, [user]);

  if (!user || user.role !== "student") {
    return <div className="student-shell__route-state">正在返回对应工作区…</div>;
  }
  return <>{children}</>;
}
