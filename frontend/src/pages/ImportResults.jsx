import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { imports, downloadBlob } from '../lib/api'

const PRIORITY_COLORS = {
  HIGH: 'bg-green-100 text-green-800',
  MEDIUM: 'bg-yellow-100 text-yellow-800',
  LOW: 'bg-gray-100 text-gray-600',
  SKIP: 'bg-red-100 text-red-700',
}

const MATCH_TYPE_COLORS = {
  EXACT: 'bg-blue-100 text-blue-800',
  PHRASE: 'bg-purple-100 text-purple-800',
  SKIP: 'bg-gray-100 text-gray-600',
  NEGATIVE: 'bg-red-100 text-red-700',
}

export default function ImportResults() {
  const { importId } = useParams()
  const navigate = useNavigate()
  const [importInfo, setImportInfo] = useState(null)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [page, setPage] = useState(1)
  const [priorityFilter, setPriorityFilter] = useState('')
  const [matchTypeFilter, setMatchTypeFilter] = useState('')
  const [sortBy, setSortBy] = useState('clicks')
  const [sortDir, setSortDir] = useState('desc')

  const fetchResults = async () => {
    setLoading(true)
    try {
      const data = await imports.results(importId, {
        page,
        per_page: 50,
        priority: priorityFilter,
        match_type: matchTypeFilter,
        sort_by: sortBy,
        sort_dir: sortDir,
      })
      setResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    imports.get(importId).then(setImportInfo).catch(() => {})
  }, [importId])

  useEffect(() => {
    fetchResults()
  }, [importId, page, priorityFilter, matchTypeFilter, sortBy, sortDir])

  const handleExport = async () => {
    try {
      const blob = await imports.export(importId)
      downloadBlob(blob, `import_${importId}_results.csv`)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleSort = (col) => {
    if (sortBy === col) {
      setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    } else {
      setSortBy(col)
      setSortDir('desc')
    }
    setPage(1)
  }

  const SortHeader = ({ col, label }) => (
    <th
      className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
      onClick={() => handleSort(col)}
    >
      <span className="flex items-center gap-1">
        {label}
        {sortBy === col && (
          <span className="text-blue-600">{sortDir === 'desc' ? '↓' : '↑'}</span>
        )}
      </span>
    </th>
  )

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Import Results</h1>
          {importInfo && (
            <p className="text-sm text-gray-500 mt-1">
              {importInfo.account_name || importInfo.file_name} — {importInfo.row_count} rows
            </p>
          )}
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleExport}
            className="px-4 py-2 text-sm bg-green-600 text-white rounded-md hover:bg-green-700"
          >
            Export CSV
          </button>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Back
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border p-4 mb-4">
        <div className="flex gap-4 items-center">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Priority</label>
            <select
              value={priorityFilter}
              onChange={(e) => { setPriorityFilter(e.target.value); setPage(1) }}
              className="border border-gray-300 rounded-md px-2 py-1.5 text-sm"
            >
              <option value="">All</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
              <option value="SKIP">SKIP</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Match Type Rec.</label>
            <select
              value={matchTypeFilter}
              onChange={(e) => { setMatchTypeFilter(e.target.value); setPage(1) }}
              className="border border-gray-300 rounded-md px-2 py-1.5 text-sm"
            >
              <option value="">All</option>
              <option value="EXACT">EXACT</option>
              <option value="PHRASE">PHRASE</option>
              <option value="SKIP">SKIP</option>
              <option value="NEGATIVE">NEGATIVE</option>
            </select>
          </div>
          {results && (
            <div className="ml-auto text-sm text-gray-500">
              {results.total} results
            </div>
          )}
        </div>
      </div>

      {/* Results Table */}
      <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
        {loading ? (
          <div className="p-12 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto" />
          </div>
        ) : results && results.items.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <SortHeader col="search_term" label="Search Term" />
                    <SortHeader col="clicks" label="Clicks" />
                    <SortHeader col="impressions" label="Impr." />
                    <SortHeader col="conversions" label="Conv." />
                    <SortHeader col="cost" label="Cost" />
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Match Type Rec.</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Reason</th>
                    <SortHeader col="relevance_score" label="Relevance" />
                    <SortHeader col="priority" label="Priority" />
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Campaign</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Ad Group Sug.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {results.items.map((item) => (
                    <tr key={item.id} className={item.is_negative_candidate ? 'bg-red-50/50' : ''}>
                      <td className="px-3 py-2 font-medium text-gray-900 max-w-xs truncate">
                        {item.search_term}
                        {item.is_duplicate && (
                          <span className="ml-1 text-xs text-orange-600">(dup)</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-gray-700">{item.clicks || 0}</td>
                      <td className="px-3 py-2 text-gray-700">{item.impressions || 0}</td>
                      <td className="px-3 py-2 text-gray-700">{item.conversions ? item.conversions.toFixed(1) : '0'}</td>
                      <td className="px-3 py-2 text-gray-700">${(item.cost || 0).toFixed(2)}</td>
                      <td className="px-3 py-2">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          MATCH_TYPE_COLORS[item.recommended_match_type] || 'bg-gray-100'
                        }`}>
                          {item.recommended_match_type}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-500 max-w-[200px] truncate">
                        {item.match_type_reason}
                      </td>
                      <td className="px-3 py-2 text-gray-700">{item.relevance_score ?? '-'}</td>
                      <td className="px-3 py-2">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          PRIORITY_COLORS[item.priority] || 'bg-gray-100'
                        }`}>
                          {item.priority}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-500 max-w-[150px] truncate">
                        {item.campaign}
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-500 max-w-[150px] truncate">
                        {item.suggested_ad_group}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {results.pages > 1 && (
              <div className="px-4 py-3 bg-gray-50 border-t flex items-center justify-between">
                <p className="text-sm text-gray-500">
                  Page {results.page} of {results.pages}
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-3 py-1 text-sm border rounded disabled:opacity-40"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage(p => Math.min(results.pages, p + 1))}
                    disabled={page === results.pages}
                    className="px-3 py-1 text-sm border rounded disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="p-12 text-center text-gray-500">
            No results found for the selected filters.
          </div>
        )}
      </div>
    </div>
  )
}
