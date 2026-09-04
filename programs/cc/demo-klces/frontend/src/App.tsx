import { Routes, Route, useLocation, Navigate } from "react-router-dom";
import BottomTab from "./components/ui";
import DesktopLayout from "./components/DesktopLayout";
import { useAuth } from "./auth/AuthContext";
import { RequireAuth, RequireRole, homeOf } from "./auth/Guards";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Account from "./pages/Account";
import Home from "./pages/Home";
import AssessCenter from "./pages/AssessCenter";
import AssessAnswer from "./pages/AssessAnswer";
import AssessReport from "./pages/AssessReport";
import KnowledgeGraph from "./pages/KnowledgeGraph";
import MyPlan from "./pages/MyPlan";
import KnowledgeStudy from "./pages/KnowledgeStudy";
import ErrorList from "./pages/ErrorList";
import ErrorDetail from "./pages/ErrorDetail";
import GrowthCenter from "./pages/GrowthCenter";
import ClassOverview from "./pages/teacher/ClassOverview";
import ClassAssessManage from "./pages/teacher/ClassAssessManage";
import StudentProfile from "./pages/teacher/StudentProfile";
import KnowledgeManage from "./pages/admin/KnowledgeManage";
import QuestionManage from "./pages/admin/QuestionManage";
import UserManage from "./pages/admin/UserManage";
import RoleManage from "./pages/admin/RoleManage";
import AuditLogs from "./pages/admin/AuditLogs";
import SchoolApprovals from "./pages/admin/SchoolApprovals";
import SchoolDashboard from "./pages/school/SchoolDashboard";
import SchoolUsers from "./pages/school/SchoolUsers";
import SchoolStructure from "./pages/school/SchoolStructure";
import SchoolKnowledge from "./pages/school/SchoolKnowledge";
import SchoolQuestions from "./pages/school/SchoolQuestions";
import GradeDashboard from "./pages/grade/GradeDashboard";
import GradeKnowledge from "./pages/grade/GradeKnowledge";
import GradeQuestions from "./pages/grade/GradeQuestions";
import ClassContent from "./pages/teacher/ClassContent";

export default function App() {
  const { pathname } = useLocation();
  const isDesktop = pathname.startsWith("/teacher") || pathname.startsWith("/admin") || pathname.startsWith("/school") || pathname.startsWith("/grade");

  // 登录/注册/账号设置 独立全屏页（所有角色通用）
  if (pathname === "/login" || pathname === "/register" || pathname === "/account") {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/account" element={<RequireAuth><Account /></RequireAuth>} />
      </Routes>
    );
  }

  if (isDesktop) {
    return (
      <Routes>
        <Route element={<RequireAuth><DesktopLayout /></RequireAuth>}>
          {/* 教师端 */}
          <Route path="/teacher" element={<RequireRole roles={["teacher"]}><ClassOverview /></RequireRole>} />
          <Route path="/teacher/assessments" element={<RequireRole roles={["teacher"]}><ClassAssessManage /></RequireRole>} />
          <Route path="/teacher/student/:id" element={<RequireRole roles={["teacher"]}><StudentProfile /></RequireRole>} />
          <Route path="/teacher/knowledge" element={<RequireRole roles={["teacher"]}><ClassContent /></RequireRole>} />
          {/* 学校管理员 */}
          <Route path="/school" element={<RequireRole roles={["schooladmin"]}><SchoolDashboard /></RequireRole>} />
          <Route path="/school/users" element={<RequireRole roles={["schooladmin"]}><SchoolUsers /></RequireRole>} />
          <Route path="/school/structure" element={<RequireRole roles={["schooladmin"]}><SchoolStructure /></RequireRole>} />
          <Route path="/school/knowledge" element={<RequireRole roles={["schooladmin"]}><SchoolKnowledge /></RequireRole>} />
          <Route path="/school/questions" element={<RequireRole roles={["schooladmin"]}><SchoolQuestions /></RequireRole>} />
          {/* 年级管理员 */}
          <Route path="/grade" element={<RequireRole roles={["gradeadmin"]}><GradeDashboard /></RequireRole>} />
          <Route path="/grade/knowledge" element={<RequireRole roles={["gradeadmin"]}><GradeKnowledge /></RequireRole>} />
          <Route path="/grade/questions" element={<RequireRole roles={["gradeadmin"]}><GradeQuestions /></RequireRole>} />
          {/* 三权分立管理后台 */}
          <Route path="/admin/school-approvals" element={<RequireRole roles={["bizadmin"]}><SchoolApprovals /></RequireRole>} />
          <Route path="/admin/users" element={<RequireRole roles={["sysadmin"]}><UserManage /></RequireRole>} />
          <Route path="/admin/roles" element={<RequireRole roles={["secadmin"]}><RoleManage /></RequireRole>} />
          <Route path="/admin/audit" element={<RequireRole roles={["audadmin"]}><AuditLogs /></RequireRole>} />
          {/* 业务管理：仅业务管理员（其他管理员不再处理业务） */}
          <Route path="/admin/knowledge" element={<RequireRole roles={["bizadmin"]}><KnowledgeManage /></RequireRole>} />
          <Route path="/admin/questions" element={<RequireRole roles={["bizadmin"]}><QuestionManage /></RequireRole>} />
        </Route>
      </Routes>
    );
  }

  const showTab = ["/", "/assess", "/plan", "/errors", "/growth"].includes(pathname);
  return (
    <div className="w-full max-w-md sm:max-w-2xl lg:max-w-3xl mx-auto bg-slate-50 min-h-screen relative shadow-xl">
      <Routes>
        <Route path="/" element={<RequireAuth><Home /></RequireAuth>} />
        <Route path="/assess" element={<RequireAuth><AssessCenter /></RequireAuth>} />
        <Route path="/assess/answer/:sid" element={<RequireAuth><AssessAnswer /></RequireAuth>} />
        <Route path="/report/:id" element={<RequireAuth><AssessReport /></RequireAuth>} />
        <Route path="/knowledge" element={<RequireAuth><KnowledgeGraph /></RequireAuth>} />
        <Route path="/plan" element={<RequireAuth><MyPlan /></RequireAuth>} />
        <Route path="/study/:kpId" element={<RequireAuth><KnowledgeStudy /></RequireAuth>} />
        <Route path="/errors" element={<RequireAuth><ErrorList /></RequireAuth>} />
        <Route path="/errors/:id" element={<RequireAuth><ErrorDetail /></RequireAuth>} />
        <Route path="/growth" element={<RequireAuth><GrowthCenter /></RequireAuth>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      {showTab && <BottomTab />}
      {showTab && <div className="h-14" />}
    </div>
  );
}

// 根据登录角色自动跳转首页（用于旧入口兼容）
export function RoleHome() {
  const { user } = useAuth();
  return <Navigate to={user ? homeOf(user.role) : "/login"} replace />;
}
