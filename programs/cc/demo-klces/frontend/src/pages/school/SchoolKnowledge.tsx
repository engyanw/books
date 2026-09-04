import { useAuth } from "../../auth/AuthContext";
import { Spinner } from "../../components/desktop";
import ScopeContentManager from "../../components/ScopeContentManager";

export default function SchoolKnowledge() {
  const { user } = useAuth();
  if (!user?.schoolId) return <Spinner label="未绑定学校" />;
  return <ScopeContentManager scope="school" id={user.schoolId} mode="knowledge" />;
}
