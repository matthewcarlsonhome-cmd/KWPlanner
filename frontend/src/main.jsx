import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import AccountDetail from './pages/AccountDetail'
import SettingsPage from './pages/Settings'
import ResearchProgress from './pages/ResearchProgress'
import ImportWizard from './pages/ImportWizard'
import ImportResults from './pages/ImportResults'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/accounts/:id" element={<AccountDetail />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/research/active" element={<ResearchProgress />} />
          <Route path="/import" element={<ImportWizard />} />
          <Route path="/imports/:importId/results" element={<ImportResults />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
