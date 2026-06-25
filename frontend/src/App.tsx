import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ErrorBoundary from './components/ErrorBoundary'
import LoadingPage from './components/LoadingPage'

const DashboardPage    = lazy(() => import('./pages/DashboardPage'))
const ResumeUploadPage = lazy(() => import('./pages/ResumeUploadPage'))
const JDInputPage      = lazy(() => import('./pages/JDInputPage'))
const MatchResultPage  = lazy(() => import('./pages/MatchResultPage'))
const RewritePage      = lazy(() => import('./pages/RewritePage'))
const InterviewPage    = lazy(() => import('./pages/InterviewPage'))
const ReviewPage       = lazy(() => import('./pages/ReviewPage'))
const LoginPage        = lazy(() => import('./pages/LoginPage'))
const WorkflowPage     = lazy(() => import('./pages/WorkflowPage'))
const NotFoundPage     = lazy(() => import('./pages/NotFoundPage'))

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={<LoadingPage />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<Layout />}>
              <Route path="/"              element={<DashboardPage />} />
              <Route path="/upload"        element={<ResumeUploadPage />} />
              <Route path="/jd"            element={<JDInputPage />} />
              <Route path="/match/:id"     element={<MatchResultPage />} />
              <Route path="/rewrite/:id"   element={<RewritePage />} />
              <Route path="/interview/:id" element={<InterviewPage />} />
              <Route path="/review/:id"    element={<ReviewPage />} />
              <Route path="/workflow"      element={<WorkflowPage />} />
            <Route path="*"             element={<NotFoundPage />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
