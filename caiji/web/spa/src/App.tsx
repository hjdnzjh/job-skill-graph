import React from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import CLayout from './layouts/CLayout';
import BLayout from './layouts/BLayout';

// C-end Pages
import Home from './pages/c-end/Home';
import NewJobs from './pages/c-end/NewJobs';
import SkillGraphPage from './pages/c-end/SkillGraphPage';
import ResumeEvaluate from './pages/c-end/ResumeEvaluate';
import Profile from './pages/c-end/Profile';
import RAGChat from './pages/c-end/RAGChat';

// B-end Pages
import Dashboard from './pages/b-end/Dashboard';
import JobReview from './pages/b-end/JobReview';
import SkillManage from './pages/b-end/SkillManage';
import GraphManage from './pages/b-end/GraphManage';
import BatchMatch from './pages/b-end/BatchMatch';
import Reports from './pages/b-end/Reports';
import QuickMatch from './pages/b-end/QuickMatch';

export default function App() {
  const location = useLocation();

  return (
    <Routes location={location} key={location.pathname.split('/')[1] || 'root'}>
      {/* C-end Routes */}
      <Route element={<CLayout />}>
        <Route path="/" element={<Home />} />
        <Route path="/new-jobs" element={<NewJobs />} />
        <Route path="/skill-graph" element={<SkillGraphPage />} />
        <Route path="/resume-evaluate" element={<ResumeEvaluate />} />
        <Route path="/rag-chat" element={<RAGChat />} />
        <Route path="/profile" element={<Profile />} />
      </Route>

      {/* B-end Routes */}
      <Route path="/admin" element={<BLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="job-review" element={<JobReview />} />
        <Route path="skill-manage" element={<SkillManage />} />
        <Route path="graph-manage" element={<GraphManage />} />
        <Route path="batch-resume" element={<BatchMatch />} />
        <Route path="quick-match" element={<QuickMatch />} />
        <Route path="reports" element={<Reports />} />
      </Route>
    </Routes>
  );
}
