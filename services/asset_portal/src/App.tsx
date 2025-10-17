import { Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import { Center, Spinner } from '@chakra-ui/react';
import AppLayout from './components/layout/AppLayout';
import LandingPage from './pages/dashboard/LandingPage';
import ProjectOverviewPage from './pages/dashboard/ProjectOverviewPage';
import WorkloadDashboardPage from './pages/dashboard/WorkloadDashboardPage';
import AssetBrowserPage from './pages/discovery/AssetBrowserPage';
import WorkflowBoardPage from './pages/workflow/WorkflowBoardPage';
import OperationsOverviewPage from './pages/operations/OperationsOverviewPage';
import SettingsPage from './pages/settings/SettingsPage';

const App = () => {
  return (
    <AppLayout>
      <Suspense
        fallback={
          <Center py={20}>
            <Spinner size="xl" />
          </Center>
        }
      >
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/dashboards/projects" element={<ProjectOverviewPage />} />
          <Route path="/dashboards/workload" element={<WorkloadDashboardPage />} />
          <Route path="/discovery/assets" element={<AssetBrowserPage />} />
          <Route path="/workflow/board" element={<WorkflowBoardPage />} />
          <Route path="/operations/overview" element={<OperationsOverviewPage />} />
          <Route path="/settings/preferences" element={<SettingsPage />} />
        </Routes>
      </Suspense>
    </AppLayout>
  );
};

export default App;
