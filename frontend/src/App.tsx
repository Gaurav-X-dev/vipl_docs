import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { Loading } from "./components";
import { AppLayout } from "./layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Cases from "./pages/Cases";
import MyCases from "./pages/MyCases";
import Attendance from "./pages/Attendance";
import ActivityLog from "./pages/ActivityLog";
import CaseDetail from "./pages/CaseDetail";
import Imports from "./pages/Imports";
import StaffPage from "./pages/Staff";
import StaffDetail from "./pages/StaffDetail";
import Companies from "./pages/Companies";
import HR from "./pages/HR";
import Templates from "./pages/Templates";
import Reports from "./pages/Reports";
import Audit from "./pages/Audit";
import Admin from "./pages/Admin";

function Protected() {
  const { user, loading } = useAuth();
  if (loading) return <Loading label="Opening secure workspace…" />;
  return user ? <AppLayout /> : <Navigate to="/login" replace />;
}
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protected />}>
        <Route index element={<Dashboard />} />
        <Route path="cases" element={<Cases />} />
        {/* The sidebar links here; the category comes from the path and
            the company and status bucket from the querystring. */}
        <Route path="investigation" element={<Cases />} />
        <Route path="death-claim" element={<Cases />} />
        <Route path="my-cases" element={<MyCases />} />
        <Route path="attendance" element={<Attendance />} />
        <Route path="activity" element={<ActivityLog />} />
        <Route path="cases/:id" element={<CaseDetail />} />
        <Route path="imports" element={<Imports />} />
        <Route path="staff" element={<StaffPage />} />
        <Route path="staff/:id" element={<StaffDetail />} />
        <Route path="hr" element={<HR />} />
        <Route path="companies" element={<Companies />} />
        <Route path="templates" element={<Templates />} />
        <Route path="reports" element={<Reports />} />
        <Route path="audit" element={<Audit />} />
        <Route path="admin" element={<Admin />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
