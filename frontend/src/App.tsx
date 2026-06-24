import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'

const DashboardPage    = lazy(() => import('./pages/DashboardPage'))
const ResumeUploadPage = lazy(() => import('./pages/ResumeUploadPage'))
const JDInputPage      = lazy(() => import('./pages/JDInputPage'))
const MatchResultPage  = lazy(() => import('./pages/MatchResultPage'))
const RewritePage      = lazy(() => import('./pages/RewritePage'))
const InterviewPage    = lazy(() => import('./pages/InterviewPage'))
const ReviewPage       = lazy(() => import('./pages/ReviewPage'))
const LoginPage        = lazy(() => import('./pages/LoginPage'))

function PageLoader() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
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
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
