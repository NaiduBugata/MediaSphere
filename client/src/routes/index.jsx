import { Navigate, Route, Routes } from 'react-router-dom';
import AppShell from '../layouts/AppShell';
import DashboardPage from '../pages/DashboardPage';
import NewsPage from '../pages/NewsPage';
import ProblemsPage from '../pages/ProblemsPage';
import AnalyticsPage from '../pages/AnalyticsPage';
import DepartmentsPage from '../pages/DepartmentsPage';
import AdminPage from '../pages/AdminPage';
import ProfilePage from '../pages/ProfilePage';

export default function AppRoutes() {
  return (
    <Routes>
      {/* Canonical admin entry — outside AppShell so news load cannot block it */}
      <Route path="@admin" element={<AdminPage />} />
      <Route path="/@admin" element={<AdminPage />} />

      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="news" element={<NewsPage />} />
        <Route path="problems" element={<ProblemsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="departments" element={<DepartmentsPage />} />
        <Route path="departments/:slug" element={<DepartmentsPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="settings" element={<Navigate to="/profile" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
