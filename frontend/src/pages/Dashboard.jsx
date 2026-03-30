import React, { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { accounts, research } from '../lib/api'

function StatusBadge({ date }) {
  if (!date) return <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-700">Never</span>
  const days = Math.floor((Date.now() - new Date(date).getTime()) / 86400000)
  if (days > 30) return <span className="px-2 py-1 text-xs rounded-full bg-yellow-100 text-yellow-700">{days}d ago</span>
  return <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-700">{days}d ago</span>
}

function PriorityBadge({ count, type }) {
  const colors = {
    HIGH: 'bg-green-100 text-green-800',
    MEDIUM: 'bg-yellow-100 text-yellow-800',
    LOW: 'bg-gray-100 text-gray-600',
  }
  return (
    <span className={`px-2 py-0.5 text-xs rounded-full ${colors[type] || 'bg-gray-100'}`}>
      {count ?? 0}
    </span>
  )
}

export default function Dashboard() {
  const [accountList, setAccountList] = useState([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [runningAll, setRunningAll] = useState(false)
  const [runStatus, setRunStatus] = useState(null)
  const navigate = useNavigate()

  const loadAccounts = useCallback(async () => {
    try {
      const data = await accounts.list()
      setAccountList(data)
    } catch (err) {
      console.error('Failed to load accounts:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAccounts()
  }, [loadAccounts])

  // Poll research status
  useEffect(() => {
    if (!runningAll) return
    const interval = setInterval(async () => {
      try {
        const status = await research.status()
        setRunStatus(status)
        if (status.status === 'idle' || status.status === 'completed') {
          setRunningAll(false)
          setRunStatus(null)
          loadAccounts()
        }
      } catch (err) {
        console.error('Status poll error:', err)
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [runningAll, loadAccounts])

  const handleSync = async () => {
    setSyncing(true)
    try {
      await accounts.sync()
      await loadAccounts()
    } catch (err) {
      alert('Sync failed: ' + err.message)
    } finally {
      setSyncing(false)
    }
  }

  const handleRunAll = async () => {
    try {
      await research.run(null)
      setRunningAll(true)
      navigate('/research/active')
    } catch (err) {
      alert(err.message)
    }
  }

  const handleRunSingle = async (accountId) => {
    try {
      await research.run(accountId)
      navigate('/research/active')
    } catch (err) {
      alert(err.message)
    }
  }

  // Compute stats
  const totalAccounts = accountList.length
  const researchedAccounts = accountList.filter(a => a.latest_run_date).length
  const totalIdeas = accountList.reduce((sum, a) => sum + (a.ideas_count || 0), 0)
  const totalHigh = accountList.reduce((sum, a) => sum + (a.ideas_high || 0), 0)

  if (loading) {
    return <div className="flex justify-center py-20"><div className="text-gray-500">Loading accounts...</div></div>
  }

  return (
    <div>
      {/* Stats bar */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Accounts', value: totalAccounts, color: 'blue' },
          { label: 'Researched', value: researchedAccounts, color: 'green' },
          { label: 'Total Opportunities', value: totalIdeas, color: 'purple' },
          { label: 'HIGH Priority', value: totalHigh, color: 'emerald' },
        ].map(stat => (
          <div key={stat.label} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <p className="text-sm text-gray-500">{stat.label}</p>
            <p className={`text-2xl font-bold text-${stat.color}-600`}>{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Action buttons */}
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Accounts</h2>
        <div className="flex gap-3">
          <button
            onClick={handleSync}
            disabled={syncing}
            className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
          >
            {syncing ? 'Syncing...' : 'Sync from MCC'}
          </button>
          <button
            onClick={handleRunAll}
            disabled={runningAll}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {runningAll ? 'Running...' : 'Run All Accounts'}
          </button>
        </div>
      </div>

      {/* Progress bar */}
      {runStatus && runStatus.status === 'running' && (
        <div className="mb-4 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex justify-between text-sm text-blue-700 mb-2">
            <span>Processing: {runStatus.current_account || 'Starting...'}</span>
            <span>{runStatus.accounts_completed} / {runStatus.accounts_total} accounts</span>
          </div>
          <div className="w-full bg-blue-100 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all"
              style={{ width: `${runStatus.accounts_total > 0 ? (runStatus.accounts_completed / runStatus.accounts_total) * 100 : 0}%` }}
            />
          </div>
        </div>
      )}

      {/* Account table */}
      {accountList.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg shadow-sm border">
          <p className="text-gray-500 mb-4">No accounts found. Click "Sync from MCC" to load accounts from Google Ads.</p>
          <button onClick={handleSync} className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
            Sync from MCC
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-700">Account</th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">Last Run</th>
                <th className="text-center px-4 py-3 font-medium text-gray-700">Ideas</th>
                <th className="text-center px-4 py-3 font-medium text-gray-700">HIGH</th>
                <th className="text-center px-4 py-3 font-medium text-gray-700">MED</th>
                <th className="text-center px-4 py-3 font-medium text-gray-700">Approved</th>
                <th className="text-center px-4 py-3 font-medium text-gray-700">Pending</th>
                <th className="text-right px-4 py-3 font-medium text-gray-700">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {accountList.map(acct => (
                <tr key={acct.id} className={`hover:bg-gray-50 ${!acct.latest_run_date ? 'bg-red-50' : ''}`}>
                  <td className="px-4 py-3">
                    <Link to={`/accounts/${acct.id}`} className="font-medium text-blue-600 hover:underline">
                      {acct.name}
                    </Link>
                    <p className="text-xs text-gray-400">{acct.google_ads_id}</p>
                  </td>
                  <td className="px-4 py-3"><StatusBadge date={acct.latest_run_date} /></td>
                  <td className="text-center px-4 py-3">{acct.ideas_count ?? '-'}</td>
                  <td className="text-center px-4 py-3"><PriorityBadge count={acct.ideas_high} type="HIGH" /></td>
                  <td className="text-center px-4 py-3"><PriorityBadge count={acct.ideas_medium} type="MEDIUM" /></td>
                  <td className="text-center px-4 py-3">{acct.approved_count ?? 0}</td>
                  <td className="text-center px-4 py-3">{acct.pending_count ?? 0}</td>
                  <td className="text-right px-4 py-3">
                    {acct.latest_run_date ? (
                      <Link to={`/accounts/${acct.id}`} className="text-blue-600 hover:underline text-sm">
                        View Results
                      </Link>
                    ) : (
                      <button
                        onClick={() => handleRunSingle(acct.id)}
                        className="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
                      >
                        Run Research
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
