import React, { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { imports } from '../lib/api'

const STEPS = ['Upload', 'Map Columns', 'Review & Analyze']

const FILE_TYPE_OPTIONS = [
  { value: 'search_terms', label: 'Search Term Report' },
  { value: 'keywords', label: 'Account Keywords Export' },
]

const FIELD_LABELS = {
  search_term: 'Search Term',
  campaign: 'Campaign',
  ad_group: 'Ad Group',
  matched_keyword: 'Matched Keyword',
  match_type_triggered: 'Match Type',
  impressions: 'Impressions',
  clicks: 'Clicks',
  cost: 'Cost',
  conversions: 'Conversions',
  conv_rate: 'Conv. Rate',
  ctr: 'CTR',
  keyword: 'Keyword',
  match_type: 'Match Type',
  status: 'Status',
  max_cpc: 'Max CPC',
  quality_score: 'Quality Score',
  avg_cpc: 'Avg CPC',
}

export default function ImportWizard() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [fileType, setFileType] = useState('search_terms')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  // Step 1: Upload
  const [dragActive, setDragActive] = useState(false)
  const [uploadResult, setUploadResult] = useState(null)

  // Step 2: Column Mapping
  const [columnMapping, setColumnMapping] = useState({})
  const [accountName, setAccountName] = useState('')

  // Step 3: Analysis
  const [analysisResult, setAnalysisResult] = useState(null)

  const handleDrag = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true)
    else if (e.type === 'dragleave') setDragActive(false)
  }, [])

  const handleUpload = async (file) => {
    if (!file) return
    setError(null)
    setLoading(true)
    try {
      const result = await imports.upload(file, fileType)
      setUploadResult(result)
      setColumnMapping(result.column_mapping || {})
      setStep(1)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleUpload(e.dataTransfer.files[0])
    }
  }, [fileType])

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleUpload(e.target.files[0])
    }
  }

  const handleConfirm = async () => {
    if (!accountName.trim()) {
      setError('Please enter an account name')
      return
    }
    setError(null)
    setLoading(true)
    try {
      await imports.confirm({
        upload_id: uploadResult.upload_id,
        column_mapping: columnMapping,
        account_name: accountName.trim(),
      })
      setStep(2)
      // Auto-start analysis
      const result = await imports.analyze(uploadResult.upload_id)
      setAnalysisResult(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const updateMapping = (field, column) => {
    setColumnMapping(prev => ({
      ...prev,
      [field]: column || undefined,
    }))
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Import Data</h1>
        <button
          onClick={() => navigate('/')}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          Cancel
        </button>
      </div>

      {/* Stepper */}
      <div className="flex items-center mb-8">
        {STEPS.map((label, i) => (
          <React.Fragment key={label}>
            <div className="flex items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                i < step ? 'bg-green-500 text-white'
                : i === step ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-500'
              }`}>
                {i < step ? '✓' : i + 1}
              </div>
              <span className={`ml-2 text-sm ${i === step ? 'font-medium text-gray-900' : 'text-gray-500'}`}>
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`flex-1 h-0.5 mx-4 ${i < step ? 'bg-green-500' : 'bg-gray-200'}`} />
            )}
          </React.Fragment>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Step 1: Upload */}
      {step === 0 && (
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">File Type</label>
            <select
              value={fileType}
              onChange={(e) => setFileType(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              {FILE_TYPE_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          <div
            className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
              dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
            }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => document.getElementById('file-input').click()}
          >
            <input
              id="file-input"
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={handleFileInput}
              className="hidden"
            />
            {loading ? (
              <div>
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto mb-3" />
                <p className="text-sm text-gray-500">Uploading and parsing file...</p>
              </div>
            ) : (
              <>
                <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                  <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <p className="mt-2 text-sm text-gray-600">
                  <span className="font-medium text-blue-600">Click to upload</span> or drag and drop
                </p>
                <p className="mt-1 text-xs text-gray-500">CSV or XLSX up to 50MB</p>
              </>
            )}
          </div>

          <div className="mt-4 flex gap-3">
            <a
              href="/templates/search_term_report_template.csv"
              download
              className="text-xs text-blue-600 hover:underline"
            >
              Download Search Term Template
            </a>
            <a
              href="/templates/keyword_export_template.csv"
              download
              className="text-xs text-blue-600 hover:underline"
            >
              Download Keyword Template
            </a>
          </div>
        </div>
      )}

      {/* Step 2: Column Mapping */}
      {step === 1 && uploadResult && (
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow-sm border p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Column Mapping</h2>
            <p className="text-sm text-gray-500 mb-4">
              We detected {uploadResult.row_count} rows. Verify the column mapping below.
            </p>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Account Name</label>
              <input
                type="text"
                value={accountName}
                onChange={(e) => setAccountName(e.target.value)}
                placeholder="e.g. Magnolia Custom Pools"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              {Object.entries(FIELD_LABELS).map(([field, label]) => {
                const isRelevant = fileType === 'search_terms'
                  ? field in (uploadResult.column_mapping || {}) || ['search_term', 'campaign', 'ad_group', 'clicks', 'conversions', 'impressions', 'cost'].includes(field)
                  : field in (uploadResult.column_mapping || {}) || ['keyword', 'campaign', 'ad_group', 'clicks', 'conversions', 'impressions', 'cost'].includes(field)

                if (!isRelevant) return null

                return (
                  <div key={field}>
                    <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
                    <select
                      value={columnMapping[field] || ''}
                      onChange={(e) => updateMapping(field, e.target.value)}
                      className={`w-full border rounded-md px-2 py-1.5 text-sm ${
                        columnMapping[field] ? 'border-green-300 bg-green-50' : 'border-gray-300'
                      }`}
                    >
                      <option value="">-- Not mapped --</option>
                      {uploadResult.detected_columns.map(col => (
                        <option key={col} value={col}>{col}</option>
                      ))}
                    </select>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Preview */}
          <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b">
              <h3 className="font-medium text-gray-700 text-sm">Preview (first {uploadResult.preview.length} rows)</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-xs">
                <thead className="bg-gray-50">
                  <tr>
                    {uploadResult.detected_columns.map(col => (
                      <th key={col} className="px-3 py-2 text-left font-medium text-gray-500 uppercase">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {uploadResult.preview.map((row, i) => (
                    <tr key={i}>
                      {uploadResult.detected_columns.map(col => (
                        <td key={col} className="px-3 py-2 text-gray-700 whitespace-nowrap max-w-xs truncate">
                          {row[col] != null ? String(row[col]) : ''}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="flex justify-between">
            <button
              onClick={() => { setStep(0); setUploadResult(null); setError(null) }}
              className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Back
            </button>
            <button
              onClick={handleConfirm}
              disabled={loading}
              className="px-6 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Analyzing...' : 'Confirm & Analyze'}
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Analysis Results */}
      {step === 2 && (
        <div className="bg-white rounded-lg shadow-sm border p-6 text-center">
          {loading ? (
            <>
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
              <h2 className="text-lg font-medium text-gray-900">Analyzing search terms...</h2>
              <p className="text-sm text-gray-500 mt-2">
                Running match type recommendations and relevance scoring
              </p>
            </>
          ) : analysisResult ? (
            <>
              <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-lg font-medium text-gray-900">Analysis Complete</h2>
              <p className="text-sm text-gray-500 mt-2">
                {uploadResult?.row_count || 0} search terms analyzed with match type recommendations.
              </p>
              <div className="mt-6 flex justify-center gap-3">
                <button
                  onClick={() => navigate(`/imports/${analysisResult.import_id}/results`)}
                  className="px-6 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  View Results
                </button>
                <button
                  onClick={() => navigate('/')}
                  className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Back to Dashboard
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="text-gray-500">Something went wrong. Please try again.</p>
              <button
                onClick={() => { setStep(0); setError(null) }}
                className="mt-4 text-blue-600 hover:underline text-sm"
              >
                Start Over
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
