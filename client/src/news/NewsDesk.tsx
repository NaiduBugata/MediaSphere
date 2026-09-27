import { Route, Routes } from "react-router-dom";
import { NewsProvider } from "@/mediasphere/context/NewsContext.jsx";
import AppShell from "@/mediasphere/layouts/AppShell.jsx";
import NewsPage from "@/mediasphere/pages/NewsPage.jsx";
import ProblemsPage from "@/mediasphere/pages/ProblemsPage.jsx";
import AnalyticsPage from "@/mediasphere/pages/AnalyticsPage.jsx";
import DepartmentsPage from "@/mediasphere/pages/DepartmentsPage.jsx";
import ProfilePage from "@/mediasphere/pages/ProfilePage.jsx";
import AdminPage from "@/mediasphere/pages/AdminPage.jsx";
import "@/mediasphere/mediasphere.css";

export default function NewsDesk() {
  return (
    <div className="mediasphere h-full min-h-0 overflow-auto">
      <NewsProvider>
        <Routes>
          <Route path="/news/@admin" element={<AdminPage />} />
          <Route path="/news" element={<AppShell embed />}>
            <Route index element={<NewsPage />} />
            <Route path="problems" element={<ProblemsPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="departments" element={<DepartmentsPage />} />
            <Route path="departments/:slug" element={<DepartmentsPage />} />
            <Route path="profile" element={<ProfilePage />} />
          </Route>
        </Routes>
      </NewsProvider>
    </div>
  );
}
