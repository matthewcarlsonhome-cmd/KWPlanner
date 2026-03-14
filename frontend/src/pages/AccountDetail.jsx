import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { accounts, results, decisions, research, exportApi, downloadBlob } from '../lib/api'

function ScoreBadge({ priority, score }) {
  const colors = {
    HIGH: 'bg-green-100 text-green-800 border-green-200',
    MEDIUM: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    LOW: 'bg-gray-100 text-gray-600 border-gray-200',
    SKIP: 'bg-red-100 text-red-700 border-red-200',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full border ${colors[priority] || colors.LOW}`}>
      {score} {priority}
    </span>
  )
}

function DecisionBadge({ status }) {
  if (!status) return <span className="text-xs text-gray-400">Pending</span>
  const map = {
    approved: { text: 'Approved', cls: 'text-green-700 bg-green-50' },
    rejected: { text: 'Rejected', cls: 'text-red-700 bg-red-50' },
    watchlist: { text: 'Watchlist', cls: 'text-blue-700 bg-blue-50' },
    implemented: { text: 'Implemented', cls: 'text-purple-700 bg-purple-50' },
  }
  const info = map[status] || { text: status, cls: 'text-gray-600' }
  return <span className={`text-xs px-2 py-0.5 rounded-full ${info.cls}`}>{info.text}</span>
}

function MiniSparkline({ volumes }) {
  if (!volumes || volumes.length === 0) return <span className="text-gray-400 text-xs">-</span>
  const vals = volumes.map(v => v.searches || 0)
  const max = Math.max(...vals, 1)
  return (
    <div className="flex items-end gap-px h-6">
      {vals.map((v, i) => (
        <div
          key={i}
          className="w-1.5 bg-blue-400 rounded-t"
          style={{ height: `${(v / max) * 100}%`, minHeight: '1px' }}
          title={`Month ${i + 1}: ${v}`}
        />
      ))}
    </div>
  )
}

export default function AccountDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [account, setAccount] = useState(null)
  const [ideas, setIdeas] = useState({ items: [], total: 0, page: 1, per_page: 50, pages: 0 })
  const [seeds, setSeeds] = useState([])
  const [negatives, setNegatives] = useState([])
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('opportunities')
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [filters, setFilters] = useState({ priority: '', search: '', sort: 'score', page: 1 })
  const [selectedIdea, setSelectedIdea] = useState(null)

  const loadAccount = useCallback(async () => {
    try {
      const data = await accounts.get(id)
      setAccount(data)
      setRuns(data.runs || [])
    } catch (err) {
      console.error(err)
    }
  }, [id])

  const loadIdeas = useCallback(async () => {
    try {
      const data = await results.get(id, {
        priority: filters.priority,
        search: filters.search,
        sort: filters.sort,
        page: filters.page,
        per_page: 50,
      })
      setIdeas(data)
    } catch (err) {
      console.error(err)
    }
  }, [id, filters])

  useEffect(() => {
    Promise.all([
      loadAccount(),
      loadIdeas(),
      results.seeds(id).then(setSeeds).catch(() => setSeeds([])),
      results.negatives(id).then(setNegatives).catch(() => setNegatives([])),
    ]).finally(() => setLoading(false))
  }, [loadAccount, loadIdeas, id])

  useEffect(() => {
    if (!loading) loadIdeas()
  }, [filters, loadIdeas, loading])

  const handleDecision = async (ideaIds, decision) => {
    try {
      await decisions.create({
        keyword_idea_ids: ideaIds,
        decision,
        decided_by: 'team@sspdigital.com',
      })
      setSelectedIds(new Set())
      loadIdeas()
    } catch (err) {
      alert('Failed: ' + err.message)
    }
  }

  const toggleSelect = (ideaId) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(ideaId)) next.delete(ideaId)
      else next.add(ideaId)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === ideas.items.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(ideas.items.map(i => i.id)))
    }
  }

  const handleExportCSV = async () => {
    try {
      const blob = await exportApi.googleAdsEditor({
        account_id: parseInt(id),
        priority: ['HIGH', 'MEDIUM'],
        format: 'csv',
      })
      downloadBlob(blob, `${account?.name || 'keywords'}_gads_editor.csv`)
    } catch (err) {
      alert('Export failed: ' + err.message)
    }
  }

  const handleExportExcel = async () => {
    try {
      const blob = await exportApi.allAccounts({
        format: 'xlsx',
        priority: ['HIGH', 'MEDIUM'],
      })
      downloadBlob(blob, 'keyword_research_all_accounts.xlsx')
    } catch (err) {
      alert('Export failed: ' + err.message)
    }
  }

  const handleRunResearch = async () => {
    try {
      await research.run(parseInt(id))
      navigate('/research/active')
    } catch (err) {
      alert(err.message)
    }
  }

  if (loading) return <div className="flex justify-center py-20 text-gray-500">Loading...</div>
  if (!account) return <div className="text-center py-20 text-red-500">Account not found</div>

  const tabs = [
    { key: 'opportunities', label: 'Opportunities', count: ideas.total },
    { key: 'seeds', label: 'Seeds', count: seeds.length },
    { key: 'negatives', label: 'Negatives', count: negatives.length },
    { key: 'history', label: 'History', count: runs.length },
    { key: 'export', label: 'Export' },
  ]

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{account.name}</h1>
            <p className="text-sm text-gray-500">
              CID: {account.google_ads_id}
              {account.avg_cpc && <> | Avg CPC: ${Number(account.avg_cpc).toFixed(2)}</>}
              {account.monthly_budget && <> | Budget: ${Number(account.monthly_budget).toFixed(0)}/mo</>}
            </p>
          </div>
          <button
            onClick={handleRunResearch}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Run Research
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <div className="flex gap-6">
          {tabs.map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
              {tab.count !== undefined && (
                <span className="ml-2 px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">{tab.count}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Opportunities tab */}
      {activeTab === 'opportunities' && (
        <div className="flex gap-6">
          <div className="flex-1">
            {/* Filters */}
            <div className="flex gap-3 mb-4 items-center">
              <select
                value={filters.priority}
                onChange={e => setFilters(f => ({ ...f, priority: e.target.value, page: 1 }))}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="">All Priorities</option>
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="LOW">LOW</option>
                <option value="SKIP">SKIP</option>
              </select>
              <input
                type="text"
                placeholder="Search keywords..."
                value={filters.search}
                onChange={e => setFilters(f => ({ ...f, search: e.target.value, page: 1 }))}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm flex-1"
              />
              <select
                value={filters.sort}
                onChange={e => setFilters(f => ({ ...f, sort: e.target.value }))}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="score">Sort by Score</option>
                <option value="volume">Sort by Volume</option>
                <option value="cpc">Sort by CPC</option>
                <option value="competition">Sort by Competition</option>
              </select>
            </div>

            {/* Bulk actions */}
            {selectedIds.size > 0 && (
              <div className="flex gap-2 mb-3 items-center bg-blue-50 border border-blue-200 rounded-lg px-4 py-2">
                <span className="text-sm text-blue-700">{selectedIds.size} selected</span>
                <button onClick={() => handleDecision([...selectedIds], 'approved')}
                  className="px-3 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700">Approve All</button>
                <button onClick={() => handleDecision([...selectedIds], 'rejected')}
                  className="px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700">Reject All</button>
                <button onClick={() => handleDecision([...selectedIds], 'watchlist')}
                  className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700">Watchlist</button>
              </div>
            )}

            {/* Results table */}
            <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="px-3 py-2 text-left">
                      <input type="checkbox" checked={selectedIds.size === ideas.items.length && ideas.items.length > 0}
                        onChange={toggleSelectAll} className="rounded" />
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-gray-700">Score</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-700">Keyword</th>
                    <th className="px-3 py-2 text-right font-medium text-gray-700">Vol</th>
                    <th className="px-3 py-2 text-center font-medium text-gray-700">Comp</th>
                    <th className="px-3 py-2 text-right font-medium text-gray-700">Est. CPC</th>
                    <th className="px-3 py-2 text-center font-medium text-gray-700">Trend</th>
                    <th className="px-3 py-2 text-center font-medium text-gray-700">Status</th>
                    <th className="px-3 py-2 text-right font-medium text-gray-700">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {ideas.items.map(idea => {
                    const estCpc = idea.low_cpc_micros && idea.high_cpc_micros
                      ? ((idea.low_cpc_micros + idea.high_cpc_micros) / 2 / 1000000).toFixed(2)
                      : '-'
                    return (
                      <tr key={idea.id} className={`hover:bg-gray-50 cursor-pointer ${selectedIdea?.id === idea.id ? 'bg-blue-50' : ''}`}
                        onClick={() => setSelectedIdea(idea)}>
                        <td className="px-3 py-2" onClick={e => e.stopPropagation()}>
                          <input type="checkbox" checked={selectedIds.has(idea.id)}
                            onChange={() => toggleSelect(idea.id)} className="rounded" />
                        </td>
                        <td className="px-3 py-2"><ScoreBadge priority={idea.priority} score={idea.total_score} /></td>
                        <td className="px-3 py-2 font-medium text-gray-900">{idea.keyword_text}</td>
                        <td className="px-3 py-2 text-right text-gray-600">{idea.avg_monthly_searches?.toLocaleString() || '-'}</td>
                        <td className="px-3 py-2 text-center text-gray-600">{idea.competition || '-'}</td>
                        <td className="px-3 py-2 text-right text-gray-600">${estCpc}</td>
                        <td className="px-3 py-2 text-center"><MiniSparkline volumes={idea.monthly_volumes} /></td>
                        <td className="px-3 py-2 text-center"><DecisionBadge status={idea.decision_status} /></td>
                        <td className="px-3 py-2 text-right" onClick={e => e.stopPropagation()}>
                          <div className="flex gap-1 justify-end">
                            <button onClick={() => handleDecision([idea.id], 'approved')}
                              className="px-2 py-1 text-xs text-green-700 bg-green-50 rounded hover:bg-green-100">Approve</button>
                            <button onClick={() => handleDecision([idea.id], 'rejected')}
                              className="px-2 py-1 text-xs text-red-700 bg-red-50 rounded hover:bg-red-100">Reject</button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                  {ideas.items.length === 0 && (
                    <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-500">No keyword ideas found. Run research to generate ideas.</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {ideas.pages > 1 && (
              <div className="flex justify-between items-center mt-4">
                <span className="text-sm text-gray-500">
                  Showing {(ideas.page - 1) * ideas.per_page + 1}-{Math.min(ideas.page * ideas.per_page, ideas.total)} of {ideas.total}
                </span>
                <div className="flex gap-2">
                  <button disabled={ideas.page <= 1} onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}
                    className="px-3 py-1 text-sm border rounded disabled:opacity-50">Previous</button>
                  <button disabled={ideas.page >= ideas.pages} onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}
                    className="px-3 py-1 text-sm border rounded disabled:opacity-50">Next</button>
                </div>
              </div>
            )}
          </div>

          {/* Sidebar detail */}
          {selectedIdea && (
            <div className="w-80 bg-white rounded-lg shadow-sm border p-4 self-start sticky top-6">
              <div className="flex justify-between items-start mb-3">
                <h3 className="font-semibold text-gray-900 text-sm">{selectedIdea.keyword_text}</h3>
                <button onClick={() => setSelectedIdea(null)} className="text-gray-400 hover:text-gray-600 text-lg">&times;</button>
              </div>
              <ScoreBadge priority={selectedIdea.priority} score={selectedIdea.total_score} />

              <div className="mt-4 space-y-3 text-sm">
                <div>
                  <p className="text-gray-500">Score Breakdown</p>
                  <div className="grid grid-cols-2 gap-2 mt-1">
                    <div className="bg-gray-50 rounded p-2">
                      <p className="text-xs text-gray-400">Volume</p>
                      <p className="font-medium">{selectedIdea.volume_score}/25</p>
                    </div>
                    <div className="bg-gray-50 rounded p-2">
                      <p className="text-xs text-gray-400">Competition</p>
                      <p className="font-medium">{selectedIdea.competition_score}/25</p>
                    </div>
                    <div className="bg-gray-50 rounded p-2">
                      <p className="text-xs text-gray-400">CPC</p>
                      <p className="font-medium">{selectedIdea.cpc_score}/25</p>
                    </div>
                    <div className="bg-gray-50 rounded p-2">
                      <p className="text-xs text-gray-400">Relevance</p>
                      <p className="font-medium">{selectedIdea.relevance_score}/25</p>
                    </div>
                  </div>
                </div>

                <div>
                  <p className="text-gray-500">Details</p>
                  <dl className="mt-1 space-y-1">
                    <div className="flex justify-between"><dt className="text-gray-400">Monthly Searches</dt><dd>{selectedIdea.avg_monthly_searches?.toLocaleString()}</dd></div>
                    <div className="flex justify-between"><dt className="text-gray-400">Competition</dt><dd>{selectedIdea.competition} ({selectedIdea.competition_index})</dd></div>
                    <div className="flex justify-between"><dt className="text-gray-400">Relevance</dt><dd>{selectedIdea.relevance_category?.replace('_', ' ')}</dd></div>
                    <div className="flex justify-between"><dt className="text-gray-400">Match Type</dt><dd>{selectedIdea.suggested_match_type}</dd></div>
                    <div className="flex justify-between"><dt className="text-gray-400">Ad Group</dt><dd className="text-right max-w-32 truncate">{selectedIdea.suggested_ad_group}</dd></div>
                    <div className="flex justify-between"><dt className="text-gray-400">Seasonal</dt><dd>{selectedIdea.is_seasonal ? `Peaks ${selectedIdea.peak_month}` : 'Steady'}</dd></div>
                  </dl>
                </div>

                {selectedIdea.monthly_volumes && (
                  <div>
                    <p className="text-gray-500 mb-1">12-Month Trend</p>
                    <MiniSparkline volumes={selectedIdea.monthly_volumes} />
                  </div>
                )}

                <div className="flex gap-2 pt-2 border-t">
                  <button onClick={() => handleDecision([selectedIdea.id], 'approved')}
                    className="flex-1 px-3 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700">Approve</button>
                  <button onClick={() => handleDecision([selectedIdea.id], 'rejected')}
                    className="flex-1 px-3 py-2 text-sm bg-red-600 text-white rounded hover:bg-red-700">Reject</button>
                  <button onClick={() => handleDecision([selectedIdea.id], 'watchlist')}
                    className="flex-1 px-3 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700">Watch</button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Seeds tab */}
      {activeTab === 'seeds' && (
        <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Keyword</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Match Type</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Conversions</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Clicks</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Cost</th>
                <th className="px-4 py-2 text-center font-medium text-gray-700">QS</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Campaign</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Ad Group</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {seeds.map(s => (
                <tr key={s.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium">{s.keyword}</td>
                  <td className="px-4 py-2 text-gray-600">{s.match_type}</td>
                  <td className="px-4 py-2 text-right">{s.conversions}</td>
                  <td className="px-4 py-2 text-right">{s.clicks}</td>
                  <td className="px-4 py-2 text-right">${s.cost?.toFixed(2)}</td>
                  <td className="px-4 py-2 text-center">{s.quality_score || '-'}</td>
                  <td className="px-4 py-2 text-gray-600">{s.campaign}</td>
                  <td className="px-4 py-2 text-gray-600">{s.ad_group}</td>
                </tr>
              ))}
              {seeds.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-500">No seeds. Run research first.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Negatives tab */}
      {activeTab === 'negatives' && (
        <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Keyword</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Reason</th>
                <th className="px-4 py-2 text-center font-medium text-gray-700">Scope</th>
                <th className="px-4 py-2 text-center font-medium text-gray-700">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {negatives.map(n => (
                <tr key={n.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium text-red-700">{n.keyword_text}</td>
                  <td className="px-4 py-2 text-gray-600">{n.reason}</td>
                  <td className="px-4 py-2 text-center">{n.suggested_scope}</td>
                  <td className="px-4 py-2 text-center">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      n.decided === 'approved' ? 'bg-green-50 text-green-700' :
                      n.decided === 'rejected' ? 'bg-red-50 text-red-700' :
                      'bg-gray-100 text-gray-600'}`}>{n.decided}</span>
                  </td>
                </tr>
              ))}
              {negatives.length === 0 && (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-500">No negative keyword candidates.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* History tab */}
      {activeTab === 'history' && (
        <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Run Date</th>
                <th className="px-4 py-2 text-center font-medium text-gray-700">Status</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Seeds</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Ideas</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">HIGH</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">MED</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">LOW</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {runs.map(r => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2">{r.started_at ? new Date(r.started_at).toLocaleString() : '-'}</td>
                  <td className="px-4 py-2 text-center">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      r.status === 'completed' ? 'bg-green-100 text-green-700' :
                      r.status === 'running' ? 'bg-blue-100 text-blue-700' :
                      'bg-red-100 text-red-700'}`}>{r.status}</span>
                  </td>
                  <td className="px-4 py-2 text-right">{r.seed_count ?? '-'}</td>
                  <td className="px-4 py-2 text-right">{r.ideas_generated ?? '-'}</td>
                  <td className="px-4 py-2 text-right">{r.ideas_high ?? '-'}</td>
                  <td className="px-4 py-2 text-right">{r.ideas_medium ?? '-'}</td>
                  <td className="px-4 py-2 text-right">{r.ideas_low ?? '-'}</td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-500">No research runs yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Export tab */}
      {activeTab === 'export' && (
        <div className="bg-white rounded-lg shadow-sm border p-6 max-w-lg">
          <h3 className="font-semibold text-gray-900 mb-4">Export Options</h3>
          <div className="space-y-4">
            <button onClick={handleExportCSV}
              className="w-full flex items-center justify-between px-4 py-3 border rounded-lg hover:bg-gray-50">
              <div>
                <p className="font-medium text-gray-900">Google Ads Editor CSV</p>
                <p className="text-sm text-gray-500">Ready to import into Google Ads Editor</p>
              </div>
              <span className="text-blue-600 text-sm">Download</span>
            </button>
            <button onClick={handleExportExcel}
              className="w-full flex items-center justify-between px-4 py-3 border rounded-lg hover:bg-gray-50">
              <div>
                <p className="font-medium text-gray-900">Excel Workbook</p>
                <p className="text-sm text-gray-500">Multi-tab workbook with all accounts</p>
              </div>
              <span className="text-blue-600 text-sm">Download</span>
            </button>
            <button onClick={async () => {
              try {
                const blob = await exportApi.negatives(parseInt(id))
                downloadBlob(blob, `${account?.name}_negatives.csv`)
              } catch (err) { alert(err.message) }
            }}
              className="w-full flex items-center justify-between px-4 py-3 border rounded-lg hover:bg-gray-50">
              <div>
                <p className="font-medium text-gray-900">Negative Keywords CSV</p>
                <p className="text-sm text-gray-500">Negative keyword candidates for import</p>
              </div>
              <span className="text-blue-600 text-sm">Download</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
