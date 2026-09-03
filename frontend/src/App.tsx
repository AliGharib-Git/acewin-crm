import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Layout } from "./components/Layout";
import { useAuth } from "./context/AuthContext";
import { PageSpinner } from "./components/ui";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Contacts from "./pages/Contacts";
import ContactDetail from "./pages/ContactDetail";
import Companies from "./pages/Companies";
import CompanyDetail from "./pages/CompanyDetail";
import Deals from "./pages/Deals";
import Catalog from "./pages/Catalog";
import Tasks from "./pages/Tasks";
import Settings from "./pages/Settings";
import Copilot from "./pages/Copilot";
import Analytics from "./pages/Analytics";
import Kpis from "./pages/Kpis";
import Okrs from "./pages/Okrs";
import Gamification from "./pages/Gamification";
import Pricing from "./pages/Pricing";
import About from "./pages/About";
import PublicCatalog from "./pages/PublicCatalog";
import PlatformAdmin from "./pages/PlatformAdmin";

function Protected({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
}

// Guards /platform-admin: requires both an authenticated session AND
// the caller's user.is_platform_admin flag (set server-side from
// PLATFORM_ADMIN_EMAILS -- see backend app/deps.py). This is purely a
// UX convenience (hide the nav link / bounce non-admins to the
// dashboard); every actual platform-admin API call is independently
// re-checked by the backend, which is the real authorization boundary.
function PlatformAdminRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-paper">
        <PageSpinner />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!user.is_platform_admin) {
    return <Navigate to="/" replace />;
  }

  return <Layout>{children}</Layout>;
}

// Root ("/") shows the public marketing home page to signed-out visitors,
// and the app dashboard to signed-in users -- so "/" no longer bounces
// straight to /login for anonymous traffic.
function RootRoute() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-paper">
        <PageSpinner />
      </div>
    );
  }

  if (!user) {
    return <Home />;
  }

  return (
    <Layout>
      <Dashboard />
    </Layout>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/pricing" element={<Pricing />} />
      <Route path="/about" element={<About />} />
      <Route path="/catalog" element={<PublicCatalog />} />
      <Route path="/" element={<RootRoute />} />
      <Route
        path="/contacts"
        element={
          <Protected>
            <Contacts />
          </Protected>
        }
      />
      <Route
        path="/contacts/:id"
        element={
          <Protected>
            <ContactDetail />
          </Protected>
        }
      />
      <Route
        path="/companies"
        element={
          <Protected>
            <Companies />
          </Protected>
        }
      />
      <Route
        path="/companies/:id"
        element={
          <Protected>
            <CompanyDetail />
          </Protected>
        }
      />
      <Route
        path="/deals"
        element={
          <Protected>
            <Deals />
          </Protected>
        }
      />
      <Route
        path="/sales-catalog"
        element={
          <Protected>
            <Catalog />
          </Protected>
        }
      />
      <Route
        path="/tasks"
        element={
          <Protected>
            <Tasks />
          </Protected>
        }
      />
      <Route
        path="/copilot"
        element={
          <Protected>
            <Copilot />
          </Protected>
        }
      />
      <Route
        path="/analytics"
        element={
          <Protected>
            <Analytics />
          </Protected>
        }
      />
      <Route
        path="/kpis"
        element={
          <Protected>
            <Kpis />
          </Protected>
        }
      />
      <Route
        path="/okrs"
        element={
          <Protected>
            <Okrs />
          </Protected>
        }
      />
      <Route
        path="/gamification"
        element={
          <Protected>
            <Gamification />
          </Protected>
        }
      />
      <Route
        path="/settings"
        element={
          <Protected>
            <Settings />
          </Protected>
        }
      />
      <Route
        path="/platform-admin"
        element={
          <PlatformAdminRoute>
            <PlatformAdmin />
          </PlatformAdminRoute>
        }
      />
    </Routes>
  );
}
