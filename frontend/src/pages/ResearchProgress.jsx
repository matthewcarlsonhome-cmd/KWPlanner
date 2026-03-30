import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { research } from '../lib/api'

export default function ResearchProgress() {
  const [status, setStatus] = useState(null)
  const [logs, setLogs] = useState([])
  const navigate = useNavigate()

  useEffect(() => {
    const poll = setInterval(async () => {
      try {
        const s = await research.status()
        setStatus(s)

        if (s.current_account && !logs.find(l => l.account === s.current_account && l.status === 'processing')) {
          setLogs(prev => {
            // Mark previous as done
            const updated = prev.map(l =>
              l.status === 'processing' ? { ...l, status: 'done' } : l
            )
            return [...updated, { account: s.current_account, status: 'processing', time: new Date().toLocaleTimeString() }]
          })
        }

        if (s.status === 'idle' && logs.length > 0) {
          setLogs(prev => prev.map(l => ({ ...l, status: 'done' })))
          setTimeout(() => navigate('/'), 2000)
        }
      } catch (err) {
        console.error(err)
      }
    }, 2000)

    return () => clearInterval(poll)
  }, [navigate, logs])

  const progress = status && status.accounts_total > 0
    ? Math.round((status.accounts_completed / status.accounts_total) * 100)
    : 0

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Research in Progress</h1>

      {!status || status.status === 'idle' ? (
        <div className="bg-white rounded-lg shadow-sm border p-8 text-center">
          <p className="text-gray-500 mb-4">No active research running.</p>
          <button onClick={() => navigate('/')} className="text-blue-600 hover:underline">
            Back to Dashboard
          </button>
        </div>
      ) : (
        <>
          {/* Progress bar */}
          <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
            <div className="flex justify-between text-sm text-gray-700 mb-2">
              <span>Overall Progress</span>
              <span>{status.accounts_completed} / {status.accounts_total} accounts ({progress}%)</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3">
              <div
                className="bg-blue-600 h-3 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            {status.current_account && (
              <p className="text-sm text-gray-500 mt-3">
                Currently processing: <span className="font-medium text-gray-700">{status.current_account}</span>
              </p>
            )}
          </div>

          {/* Log */}
          <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b">
              <h3 className="font-medium text-gray-700 text-sm">Activity Log</h3>
            </div>
            <div className="p-4 space-y-2 max-h-96 overflow-y-auto">
              {logs.map((log, i) => (
                <div key={i} className="flex items-center gap-3 text-sm">
                  {log.status === 'processing' ? (
                    <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                  ) : (
                    <span className="w-2 h-2 bg-green-500 rounded-full" />
                  )}
                  <span className="text-gray-400 text-xs">{log.time}</span>
                  <span className="text-gray-700">{log.account}</span>
                  <span className={`text-xs ${log.status === 'processing' ? 'text-blue-600' : 'text-green-600'}`}>
                    {log.status === 'processing' ? 'Processing...' : 'Complete'}
                  </span>
                </div>
              ))}
              {logs.length === 0 && (
                <p className="text-gray-400 text-sm">Waiting for research to start...</p>
              )}
            </div>
          </div>

          {/* Cancel */}
          <div className="mt-4 flex justify-end">
            <button
              onClick={() => navigate('/')}
              className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Back to Dashboard
            </button>
          </div>
        </>
      )}
    </div>
  )
}
