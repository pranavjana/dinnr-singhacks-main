'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Upload, FileText, CheckCircle, XCircle, AlertCircle, Shield, Search, Eye, Zap } from 'lucide-react'

// TypeScript interfaces matching backend models
interface FormatAnalysis {
  word_count: number
  spell_error_rate: number
  double_space_count: number
  tab_count: number
  headers_found: string[]
  missing_sections: string[]
  section_coverage: number
  extracted_text?: string
}

interface ExifData {
  present: boolean
  camera_make?: string
  camera_model?: string
  software?: string
  datetime?: string
  anomalies: string[]
}

interface AuthenticityCheck {
  applicable: boolean
  exif?: ExifData
  phash?: {
    hash_value: string
    duplicates_found: any[]
    similarity_scores: number[]
  }
  ela?: {
    mean_score: number
    variance: number
    anomaly_detected: boolean
    confidence: number
  }
  ai_generation?: {
    likelihood: number
    indicators: string[]
    confidence: string
  }
}

interface RiskJustification {
  category: string
  severity: number
  reason: string
  evidence?: any
}

interface RiskAssessment {
  overall_score: number
  risk_level: string
  format_risk: number
  authenticity_risk: number
  justifications: RiskJustification[]
}

interface ComprehensiveResult {
  format_analysis: FormatAnalysis
  authenticity_check?: AuthenticityCheck
  risk_assessment: RiskAssessment
}

export default function DocumentUploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [docType, setDocType] = useState<string>('contract')
  const [subtype, setSubtype] = useState<string>('')
  const [subtypes, setSubtypes] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ComprehensiveResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showText, setShowText] = useState(false)

  useEffect(() => {
    handleDocTypeChange(docType)
  }, [])

  const handleDocTypeChange = async (newDocType: string) => {
    setDocType(newDocType)
    setSubtype('')
    setSubtypes([])

    try {
      const response = await fetch(`/api/v1/documents/templates/${newDocType}`)
      if (response.ok) {
        const data = await response.json()
        setSubtypes(data.subtypes || [])
        if (data.subtypes && data.subtypes.length > 0) {
          setSubtype(data.subtypes[0])
        }
      }
    } catch (err) {
      console.error('Failed to fetch subtypes:', err)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      const validTypes = ['.pdf', '.docx', '.png', '.jpg', '.jpeg']
      const fileExt = '.' + selectedFile.name.split('.').pop()?.toLowerCase()

      if (!validTypes.includes(fileExt)) {
        setError('Invalid file type. Please upload PDF, DOCX, PNG, or JPG files.')
        setFile(null)
        return
      }

      setFile(selectedFile)
      setError(null)
      setResult(null)
    }
  }

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file first')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('doc_type', docType)
      if (subtype) {
        formData.append('subtype', subtype)
      }

      const response = await fetch('/api/v1/documents/upload', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Upload failed')
      }

      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  const getRiskColor = (level: string) => {
    if (level === "Low") return "bg-green-500"
    if (level === "Med") return "bg-yellow-500"
    return "bg-red-500"
  }

  const highlightText = (text: string, format: FormatAnalysis) => {
    if (!text) return null

    // Simple highlighting for demo - mark double spaces
    const parts = text.split('  ')
    return (
      <div className="whitespace-pre-wrap font-mono text-sm">
        {parts.map((part, idx) => (
          <span key={idx}>
            {part}
            {idx < parts.length - 1 && (
              <span className="bg-yellow-200 dark:bg-yellow-900">  </span>
            )}
          </span>
        ))}
      </div>
    )
  }

  return (
    <div className="container mx-auto py-8 px-4 max-w-6xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Document Validator Pro</h1>
        <p className="text-muted-foreground">
          Comprehensive document validation with format analysis, authenticity checks, and risk scoring
        </p>
      </div>

      {/* Upload Section */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Upload Document</CardTitle>
          <CardDescription>
            Supported formats: PDF, DOCX, PNG, JPG (max 10MB)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Document Type</label>
            <Select value={docType} onValueChange={handleDocTypeChange}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="contract">Contract</SelectItem>
                <SelectItem value="report">Report</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {subtypes.length > 0 && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Document Subtype</label>
              <Select value={subtype} onValueChange={setSubtype}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {subtypes.map((st) => (
                    <SelectItem key={st} value={st}>
                      {st.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="space-y-2">
            <label className="text-sm font-medium">File</label>
            <div className="flex items-center gap-4">
              <input
                type="file"
                onChange={handleFileChange}
                accept=".pdf,.docx,.png,.jpg,.jpeg"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm file:border-0 file:bg-transparent file:text-sm file:font-medium"
              />
            </div>
            {file && (
              <p className="text-sm text-muted-foreground flex items-center gap-2">
                <FileText className="h-4 w-4" />
                {file.name} ({(file.size / 1024).toFixed(1)} KB)
              </p>
            )}
          </div>

          <Button
            onClick={handleUpload}
            disabled={!file || loading}
            className="w-full"
          >
            {loading ? (
              <>Analyzing...</>
            ) : (
              <>
                <Upload className="mr-2 h-4 w-4" />
                Analyze Document
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {result && (
        <div className="space-y-6">
          {/* Risk Score Banner */}
          <Card className={`border-2 ${result.risk_assessment.risk_level === 'Low' ? 'border-green-500' : result.risk_assessment.risk_level === 'Med' ? 'border-yellow-500' : 'border-red-500'}`}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-6 w-6" />
                  Overall Risk Assessment
                </CardTitle>
                <Badge className={`${getRiskColor(result.risk_assessment.risk_level)} text-white text-lg px-4 py-2`}>
                  {result.risk_assessment.risk_level} Risk
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div>
                  <p className="text-sm text-muted-foreground">Overall Score</p>
                  <p className="text-2xl font-bold">{result.risk_assessment.overall_score.toFixed(1)}/100</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Format Risk</p>
                  <p className="text-2xl font-bold">{result.risk_assessment.format_risk.toFixed(1)}/100</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Authenticity Risk</p>
                  <p className="text-2xl font-bold">{result.risk_assessment.authenticity_risk.toFixed(1)}/100</p>
                </div>
              </div>

              {result.risk_assessment.justifications.length > 0 && (
                <div>
                  <h4 className="font-semibold mb-2">Risk Justifications:</h4>
                  <div className="space-y-2">
                    {result.risk_assessment.justifications.slice(0, 5).map((just, idx) => (
                      <div key={idx} className="flex items-start gap-2 text-sm">
                        <Badge variant="outline" className="mt-0.5">
                          Severity: {just.severity}
                        </Badge>
                        <span>[{just.category}] {just.reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Format Analysis */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Format Analysis
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div>
                  <p className="text-sm text-muted-foreground">Word Count</p>
                  <p className="text-xl font-bold">{result.format_analysis.word_count}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Spelling Error Rate</p>
                  <p className="text-xl font-bold">{(result.format_analysis.spell_error_rate * 100).toFixed(1)}%</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Double Spaces</p>
                  <p className="text-xl font-bold">{result.format_analysis.double_space_count}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Section Coverage</p>
                  <p className="text-xl font-bold">{(result.format_analysis.section_coverage * 100).toFixed(0)}%</p>
                </div>
              </div>

              {result.format_analysis.missing_sections.length > 0 && (
                <div className="mb-4">
                  <h4 className="font-semibold mb-2">Missing Sections:</h4>
                  <div className="flex flex-wrap gap-2">
                    {result.format_analysis.missing_sections.map((section, idx) => (
                      <Badge key={idx} variant="destructive">
                        <XCircle className="h-3 w-3 mr-1" />
                        {section}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {result.format_analysis.extracted_text && (
                <div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowText(!showText)}
                    className="mb-2"
                  >
                    <Eye className="h-4 w-4 mr-2" />
                    {showText ? 'Hide' : 'Show'} Extracted Text
                  </Button>
                  {showText && (
                    <div className="max-h-64 overflow-y-auto border rounded p-4 bg-muted/50">
                      {highlightText(result.format_analysis.extracted_text, result.format_analysis)}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Authenticity Check */}
          {result.authenticity_check?.applicable && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Search className="h-5 w-5" />
                  Authenticity & Tamper Detection
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* EXIF */}
                {result.authenticity_check.exif && (
                  <div>
                    <h4 className="font-semibold mb-2">EXIF Metadata</h4>
                    <Badge className={result.authenticity_check.exif.present ? "bg-green-500" : "bg-red-500"}>
                      {result.authenticity_check.exif.present ? "Present" : "Missing"}
                    </Badge>
                    {result.authenticity_check.exif.anomalies.length > 0 && (
                      <div className="mt-2 text-sm text-red-600">
                        Anomalies: {result.authenticity_check.exif.anomalies.join(', ')}
                      </div>
                    )}
                  </div>
                )}

                {/* Duplicates */}
                {result.authenticity_check.phash && result.authenticity_check.phash.duplicates_found.length > 0 && (
                  <div>
                    <h4 className="font-semibold mb-2">Duplicate Detection</h4>
                    <Badge variant="destructive">
                      {result.authenticity_check.phash.duplicates_found.length} duplicates found
                    </Badge>
                  </div>
                )}

                {/* ELA */}
                {result.authenticity_check.ela && (
                  <div>
                    <h4 className="font-semibold mb-2">Tampering Detection (ELA)</h4>
                    <Badge className={result.authenticity_check.ela.anomaly_detected ? "bg-red-500" : "bg-green-500"}>
                      {result.authenticity_check.ela.anomaly_detected ? "Tampering Detected" : "No Tampering"}
                    </Badge>
                    <p className="text-sm text-muted-foreground mt-1">
                      Confidence: {(result.authenticity_check.ela.confidence * 100).toFixed(0)}%
                    </p>
                  </div>
                )}

                {/* AI Generation */}
                {result.authenticity_check.ai_generation && result.authenticity_check.ai_generation.likelihood > 0.3 && (
                  <div>
                    <h4 className="font-semibold mb-2">AI Generation Detection</h4>
                    <Badge className={result.authenticity_check.ai_generation.likelihood > 0.6 ? "bg-red-500" : "bg-yellow-500"}>
                      <Zap className="h-3 w-3 mr-1" />
                      {(result.authenticity_check.ai_generation.likelihood * 100).toFixed(0)}% likelihood
                    </Badge>
                    {result.authenticity_check.ai_generation.indicators.length > 0 && (
                      <div className="mt-2 text-sm">
                        Indicators: {result.authenticity_check.ai_generation.indicators.join(', ')}
                      </div>
                    )}
                  </div>
                )}

                {/* Reverse Image Search */}
                {result.authenticity_check.reverse_search && result.authenticity_check.reverse_search.total_matches > 0 && (
                  <div>
                    <h4 className="font-semibold mb-2">Reverse Image Search</h4>
                    <Badge className={
                      result.authenticity_check.reverse_search.authenticity_risk === "High" ? "bg-red-500" :
                      result.authenticity_check.reverse_search.authenticity_risk === "Med" ? "bg-yellow-500" : "bg-green-500"
                    }>
                      <Search className="h-3 w-3 mr-1" />
                      {result.authenticity_check.reverse_search.total_matches} matches found
                    </Badge>

                    {result.authenticity_check.reverse_search.exact_matches.length > 0 && (
                      <div className="mt-2">
                        <p className="text-sm font-medium">Exact Matches:</p>
                        <ul className="text-sm text-muted-foreground list-disc list-inside">
                          {result.authenticity_check.reverse_search.exact_matches.slice(0, 3).map((match, idx) => (
                            <li key={idx}>
                              <a href={match.url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">
                                {match.page_title || match.url}
                              </a>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {result.authenticity_check.reverse_search.partial_matches.length > 0 && (
                      <div className="mt-2">
                        <p className="text-sm font-medium">Similar Images:</p>
                        <ul className="text-sm text-muted-foreground list-disc list-inside">
                          {result.authenticity_check.reverse_search.partial_matches.slice(0, 3).map((match, idx) => (
                            <li key={idx}>
                              <a href={match.url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">
                                {match.page_title || match.url}
                              </a>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
