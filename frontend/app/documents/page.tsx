'use client'

import { useState, useEffect } from 'react'
import { AppSidebar } from '@/components/app-sidebar'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Separator } from '@/components/ui/separator'
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Upload, FileText, CheckCircle, XCircle, AlertCircle, Shield, Search, Eye, Zap, Filter, Paperclip, ArrowUp, Download, FileCheck, ChevronDown, ChevronUp } from 'lucide-react'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

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
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [selectedDocType, setSelectedDocType] = useState('all')
  const [selectedDate, setSelectedDate] = useState('all')
  const [selectedStaff, setSelectedStaff] = useState('all')
  const [selectedRegion, setSelectedRegion] = useState('all')
  const [isDragging, setIsDragging] = useState(false)
  const [filePreview, setFilePreview] = useState<string | null>(null)
  const [auditTrail, setAuditTrail] = useState<any[]>([])
  const [loadingAudit, setLoadingAudit] = useState(false)
  const [isRiskAssessmentExpanded, setIsRiskAssessmentExpanded] = useState(true)
  const [isFormatAnalysisExpanded, setIsFormatAnalysisExpanded] = useState(true)
  const [isAuthenticityExpanded, setIsAuthenticityExpanded] = useState(true)
  const [selectedAuditDoc, setSelectedAuditDoc] = useState<any>(null)
  const [showAuditDetail, setShowAuditDetail] = useState(false)

  useEffect(() => {
    handleDocTypeChange(docType)
    fetchAuditTrail()
  }, [])

  const fetchAuditTrail = async () => {
    setLoadingAudit(true)
    try {
      const response = await fetch('/api/v1/documents/audit')
      if (response.ok) {
        const data = await response.json()
        setAuditTrail(data.data || [])
      }
    } catch (err) {
      console.error('Failed to fetch audit trail:', err)
    } finally {
      setLoadingAudit(false)
    }
  }

  const saveToAuditTrail = async (analysisResult: ComprehensiveResult, fileName: string, fileSize: number, fileType: string) => {
    try {
      await fetch('/api/v1/documents/audit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          document_name: fileName,
          document_type: fileType.split('/')[1] || 'unknown',
          file_size_kb: (fileSize / 1024),
          uploaded_by: 'Helen Derinlacs',
          overall_risk_score: analysisResult.risk_assessment.overall_score,
          risk_level: analysisResult.risk_assessment.risk_level,
          format_risk: analysisResult.risk_assessment.format_risk,
          authenticity_risk: analysisResult.risk_assessment.authenticity_risk,
          word_count: analysisResult.format_analysis.word_count,
          spell_error_rate: analysisResult.format_analysis.spell_error_rate,
          section_coverage: analysisResult.format_analysis.section_coverage,
          status: 'Complete',
          doc_subtype: subtype,
          risk_justifications: analysisResult.risk_assessment.justifications,
          format_analysis: analysisResult.format_analysis,
          authenticity_check: analysisResult.authenticity_check
        })
      })
      // Refresh audit trail
      fetchAuditTrail()
    } catch (err) {
      console.error('Failed to save to audit trail:', err)
    }
  }

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
        setFilePreview(null)
        return
      }

      setFile(selectedFile)
      setError(null)
      setResult(null)

      // Create preview for images
      if (['.png', '.jpg', '.jpeg'].includes(fileExt)) {
        const reader = new FileReader()
        reader.onloadend = () => {
          setFilePreview(reader.result as string)
        }
        reader.readAsDataURL(selectedFile)
      } else if (fileExt === '.pdf') {
        // For PDFs, create an object URL
        const objectUrl = URL.createObjectURL(selectedFile)
        setFilePreview(objectUrl)
      } else {
        setFilePreview(null)
      }
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const droppedFile = e.dataTransfer.files?.[0]
    if (droppedFile) {
      const validTypes = ['.pdf', '.docx', '.png', '.jpg', '.jpeg']
      const fileExt = '.' + droppedFile.name.split('.').pop()?.toLowerCase()

      if (!validTypes.includes(fileExt)) {
        setError('Invalid file type. Please upload PDF, DOCX, PNG, or JPG files.')
        setFile(null)
        setFilePreview(null)
        return
      }

      setFile(droppedFile)
      setError(null)
      setResult(null)

      // Create preview for images
      if (['.png', '.jpg', '.jpeg'].includes(fileExt)) {
        const reader = new FileReader()
        reader.onloadend = () => {
          setFilePreview(reader.result as string)
        }
        reader.readAsDataURL(droppedFile)
      } else if (fileExt === '.pdf') {
        // For PDFs, create an object URL
        const objectUrl = URL.createObjectURL(droppedFile)
        setFilePreview(objectUrl)
      } else {
        setFilePreview(null)
      }
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

      // Save to audit trail
      if (file) {
        await saveToAuditTrail(data, file.name, file.size, file.type)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  const getRiskColor = (level: string) => {
    if (level === "Low") return "bg-green-500"
    if (level === "Med") return "bg-yellow-500/50 text-yellow-950 dark:text-yellow-50 border border-yellow-500/70"
    return "bg-red-500"
  }

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="flex flex-col h-screen overflow-hidden">
        <header className="flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-[[data-collapsible=icon]]/sidebar-wrapper:h-12">
          <div className="flex items-center gap-2 px-4">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mr-2 h-4" />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem className="hidden md:block">
                  <BreadcrumbLink href="/dashboard">Dashboard</BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden md:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage>Documents</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>

        <div className="flex-1 flex flex-col p-4 pt-0 overflow-y-auto">
          <div className="mb-6 flex items-center justify-between">
            <h1 className="text-2xl font-bold tracking-tight">Document Validator</h1>
          </div>

          {/* Document Type Selection */}
          <div className="mb-6">
            <div className="flex items-center gap-3">
              {/* Document Type Filter */}
              <Select value={docType} onValueChange={handleDocTypeChange}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Document Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="contract">Contract</SelectItem>
                  <SelectItem value="report">Report</SelectItem>
                </SelectContent>
              </Select>

              {/* Subtype Filter */}
              <Select
                value={subtype}
                onValueChange={setSubtype}
                disabled={subtypes.length === 0}
              >
                <SelectTrigger className="w-[220px]">
                  <SelectValue placeholder={subtypes.length === 0 ? "Loading..." : "Select Subtype"} />
                </SelectTrigger>
                <SelectContent>
                  {subtypes.map((st) => (
                    <SelectItem key={st} value={st} className="capitalize">
                      {st.replace(/_/g, ' ')}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {subtype && (
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-primary/10 border border-primary/20">
                  <FileText className="h-3.5 w-3.5 text-primary" />
                  <span className="text-sm font-medium text-primary capitalize">{docType}</span>
                  <span className="text-primary/60">•</span>
                  <span className="text-sm font-medium text-primary capitalize">{subtype.replace(/_/g, ' ')}</span>
                </div>
              )}
            </div>
          </div>

          {/* Upload Box or Preview */}
          {!file ? (
            <div
              className={`mb-6 border-2 border-dashed rounded-lg p-16 text-center transition-colors ${
                isDragging
                  ? 'border-primary bg-primary/5'
                  : 'border-muted-foreground/25 hover:border-muted-foreground/50'
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <div className="flex flex-col items-center gap-4">
                <div className="relative">
                  <Upload className="h-16 w-16 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground mb-2">
                    Drop your documents here, or{' '}
                    <label className="text-primary hover:underline cursor-pointer">
                      click to browse
                      <input
                        type="file"
                        onChange={handleFileChange}
                        accept=".pdf,.docx,.png,.jpg,.jpeg"
                        className="hidden"
                      />
                    </label>
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="mb-6">
              <Card>
                <CardContent className="p-6">
                  {/* File info header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-start gap-3">
                      <FileText className="h-8 w-8 text-primary flex-shrink-0 mt-1" />
                      <div className="flex-1 min-w-0">
                        <h3 className="text-lg font-semibold truncate">{file.name}</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                          {(file.size / 1024).toFixed(1)} KB • {file.type || 'Unknown type'}
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setFile(null)
                        setFilePreview(null)
                        setResult(null)
                        setError(null)
                      }}
                    >
                      Remove
                    </Button>
                  </div>

                  {/* File preview */}
                  <div className="mt-4">
                    {filePreview && file.type.startsWith('image/') && (
                      <div className="border rounded-lg overflow-hidden bg-muted/30">
                        <img
                          src={filePreview}
                          alt="Document preview"
                          className="w-full h-auto max-h-96 object-contain"
                        />
                      </div>
                    )}
                    {filePreview && file.type === 'application/pdf' && (
                      <div className="border rounded-lg overflow-hidden bg-muted/30">
                        <iframe
                          src={filePreview}
                          className="w-full h-96"
                          title="PDF preview"
                        />
                      </div>
                    )}
                    {!filePreview && (
                      <div className="border-2 border-dashed rounded-lg p-8 text-center bg-muted/30">
                        <FileText className="h-16 w-16 text-muted-foreground mx-auto mb-2" />
                        <p className="text-sm text-muted-foreground">
                          Preview not available for this file type
                        </p>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {!result && (
                <div className="mt-4 flex justify-center">
                  <Button
                    onClick={handleUpload}
                    disabled={loading}
                    size="lg"
                    className="w-full md:w-auto"
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
                </div>
              )}
            </div>
          )}

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {result && (
        <div className="space-y-6">
          {/* Risk Score Banner */}
          <div className="rounded-xl border bg-muted/40 overflow-hidden">
            {/* Header Section */}
            <button
              onClick={() => setIsRiskAssessmentExpanded(!isRiskAssessmentExpanded)}
              className="w-full px-6 py-5 border-b bg-muted/50 hover:bg-muted/60 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="text-left">
                    <h3 className="text-lg font-semibold">Overall Risk Assessment</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Last analyzed {new Date().toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Badge className={`${getRiskColor(result.risk_assessment.risk_level)} px-4 py-1.5 text-sm font-medium`}>
                    {result.risk_assessment.risk_level} Risk
                  </Badge>
                  {isRiskAssessmentExpanded ? (
                    <ChevronUp className="h-5 w-5 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-muted-foreground" />
                  )}
                </div>
              </div>
            </button>

            {/* Metrics Grid */}
            {isRiskAssessmentExpanded && (
              <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="group relative overflow-hidden rounded-lg border bg-background p-5 transition-all hover:shadow-sm">
                  <div className="mb-3">
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Overall Score</p>
                      <div className="flex items-baseline gap-1">
                        <span className="text-3xl font-bold tracking-tight">{result.risk_assessment.overall_score.toFixed(1)}</span>
                        <span className="text-sm text-muted-foreground">/100</span>
                      </div>
                    </div>
                  </div>
                  <div className="h-1 w-full bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all ${
                        result.risk_assessment.risk_level === 'Low'
                          ? 'bg-green-500'
                          : result.risk_assessment.risk_level === 'Med'
                          ? 'bg-yellow-500'
                          : 'bg-red-500'
                      }`}
                      style={{ width: `${result.risk_assessment.overall_score}%` }}
                    />
                  </div>
                </div>

                <div className="group relative overflow-hidden rounded-lg border bg-background p-5 transition-all hover:shadow-sm">
                  <div className="mb-3">
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Format Risk</p>
                      <div className="flex items-baseline gap-1">
                        <span className="text-3xl font-bold tracking-tight">{result.risk_assessment.format_risk.toFixed(1)}</span>
                        <span className="text-sm text-muted-foreground">/100</span>
                      </div>
                    </div>
                  </div>
                  <div className="h-1 w-full bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all ${
                        result.risk_assessment.format_risk < 30
                          ? 'bg-green-500'
                          : result.risk_assessment.format_risk < 60
                          ? 'bg-yellow-500'
                          : 'bg-red-500'
                      }`}
                      style={{ width: `${result.risk_assessment.format_risk}%` }}
                    />
                  </div>
                </div>

                <div className="group relative overflow-hidden rounded-lg border bg-background p-5 transition-all hover:shadow-sm">
                  <div className="mb-3">
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Authenticity Risk</p>
                      <div className="flex items-baseline gap-1">
                        <span className="text-3xl font-bold tracking-tight">{result.risk_assessment.authenticity_risk.toFixed(1)}</span>
                        <span className="text-sm text-muted-foreground">/100</span>
                      </div>
                    </div>
                  </div>
                  <div className="h-1 w-full bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all ${
                        result.risk_assessment.authenticity_risk < 30
                          ? 'bg-green-500'
                          : result.risk_assessment.authenticity_risk < 60
                          ? 'bg-yellow-500'
                          : 'bg-red-500'
                      }`}
                      style={{ width: `${result.risk_assessment.authenticity_risk}%` }}
                    />
                  </div>
                </div>
              </div>

              {result.risk_assessment.justifications.length > 0 && (
                <div className="rounded-lg border bg-background p-5">
                  <div className="flex items-center gap-2 mb-4 pb-3 border-b">
                    <div className="p-1.5 rounded-md bg-orange-500/10">
                      <AlertCircle className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold">Risk Factors Detected</h4>
                      <p className="text-xs text-muted-foreground">{result.risk_assessment.justifications.length} issues identified</p>
                    </div>
                  </div>
                  <div className="space-y-3">
                    {result.risk_assessment.justifications.slice(0, 5).map((just, idx) => (
                      <div
                        key={idx}
                        className="flex items-start gap-3 py-2 px-3 rounded-lg"
                      >
                        <div className="flex-shrink-0 mt-1.5">
                          <div className="h-1.5 w-1.5 rounded-full bg-orange-500" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-medium text-orange-600 dark:text-orange-400 uppercase tracking-wider">{just.category}</span>
                            <span className="text-xs text-muted-foreground">•</span>
                            <span className="text-xs text-muted-foreground">Severity: {just.severity || 'Medium'}</span>
                          </div>
                          <p className="text-sm text-foreground leading-relaxed">{just.reason}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              </div>
            )}
          </div>

          {/* Format Analysis */}
          <div className="rounded-xl border bg-muted/40 overflow-hidden">
            {/* Header Section */}
            <button
              onClick={() => setIsFormatAnalysisExpanded(!isFormatAnalysisExpanded)}
              className="w-full px-6 py-5 border-b bg-muted/50 hover:bg-muted/60 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="text-left">
                    <h3 className="text-lg font-semibold">Format Analysis</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Document structure and formatting quality metrics
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {isFormatAnalysisExpanded ? (
                    <ChevronUp className="h-5 w-5 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-muted-foreground" />
                  )}
                </div>
              </div>
            </button>

            {/* Metrics Content */}
            {isFormatAnalysisExpanded && (
              <div className="p-6">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  <div className="group relative overflow-hidden rounded-lg border bg-background p-5 transition-all hover:shadow-sm">
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Word Count</p>
                      <div className="flex items-baseline gap-1">
                        <span className="text-3xl font-bold tracking-tight">{result.format_analysis.word_count}</span>
                      </div>
                    </div>
                  </div>

                  <div className="group relative overflow-hidden rounded-lg border bg-background p-5 transition-all hover:shadow-sm">
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Spelling Errors</p>
                      <div className="flex items-baseline gap-1">
                        <span className="text-3xl font-bold tracking-tight">{(result.format_analysis.spell_error_rate * 100).toFixed(1)}</span>
                        <span className="text-sm text-muted-foreground">%</span>
                      </div>
                    </div>
                  </div>

                  <div className="group relative overflow-hidden rounded-lg border bg-background p-5 transition-all hover:shadow-sm">
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Double Spaces</p>
                      <div className="flex items-baseline gap-1">
                        <span className="text-3xl font-bold tracking-tight">{result.format_analysis.double_space_count}</span>
                      </div>
                    </div>
                  </div>

                  <div className="group relative overflow-hidden rounded-lg border bg-background p-5 transition-all hover:shadow-sm">
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Section Coverage</p>
                      <div className="flex items-baseline gap-1">
                        <span className="text-3xl font-bold tracking-tight">{(result.format_analysis.section_coverage * 100).toFixed(0)}</span>
                        <span className="text-sm text-muted-foreground">%</span>
                      </div>
                    </div>
                  </div>
                </div>

                {result.format_analysis.missing_sections.length > 0 && (
                  <div className="rounded-lg border bg-background p-5 mb-6">
                    <div className="flex items-center gap-2 mb-4 pb-3 border-b">
                      <div className="p-1.5 rounded-md bg-red-500/10">
                        <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold">Missing Sections</h4>
                        <p className="text-xs text-muted-foreground">{result.format_analysis.missing_sections.length} sections not found</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {result.format_analysis.missing_sections.map((section, idx) => (
                        <Badge key={idx} className="bg-red-500/20 text-red-700 dark:text-red-300 border-red-500/30">
                          {section}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {result.format_analysis.extracted_text && (
                  <div className="rounded-lg border bg-background p-5">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowText(!showText)}
                      className="mb-3"
                    >
                      <Eye className="h-4 w-4 mr-2" />
                      {showText ? 'Hide' : 'Show'} Extracted Text
                    </Button>
                    {showText && (
                      <div className="max-h-64 overflow-y-auto border rounded-lg p-4 bg-muted/30 mt-3 whitespace-pre-wrap font-mono text-sm">
                        {result.format_analysis.extracted_text}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Authenticity Check */}
          {result.authenticity_check?.applicable && (
            <div className="rounded-xl border bg-muted/40 overflow-hidden">
              {/* Header Section */}
              <button
                onClick={() => setIsAuthenticityExpanded(!isAuthenticityExpanded)}
                className="w-full px-6 py-5 border-b bg-muted/50 hover:bg-muted/60 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="text-left">
                      <h3 className="text-lg font-semibold">Authenticity & Tamper Detection</h3>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Image metadata and manipulation analysis
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {isAuthenticityExpanded ? (
                      <ChevronUp className="h-5 w-5 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-5 w-5 text-muted-foreground" />
                    )}
                  </div>
                </div>
              </button>

              {/* Content */}
              {isAuthenticityExpanded && (
                <div className="p-6 space-y-4">
                  {/* EXIF Metadata */}
                  {result.authenticity_check.exif && (
                    <div className="rounded-lg border bg-background p-5">
                      <div className="flex items-center gap-2 mb-3 pb-3 border-b">
                        <div className={`p-1.5 rounded-md ${result.authenticity_check.exif.present ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
                          <FileText className={`h-4 w-4 ${result.authenticity_check.exif.present ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`} />
                        </div>
                        <div>
                          <h4 className="text-sm font-semibold">EXIF Metadata</h4>
                          <p className="text-xs text-muted-foreground">Image metadata information</p>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <Badge className={result.authenticity_check.exif.present ? "bg-green-500/20 text-green-700 dark:text-green-300 border-green-500/30" : "bg-red-500/20 text-red-700 dark:text-red-300 border-red-500/30"}>
                          {result.authenticity_check.exif.present ? "Present" : "Missing"}
                        </Badge>
                        {result.authenticity_check.exif.anomalies.length > 0 && (
                          <div className="mt-3 p-3 rounded-md bg-red-500/10">
                            <p className="text-sm font-medium text-red-700 dark:text-red-300">Anomalies Detected:</p>
                            <p className="text-sm text-muted-foreground mt-1">{result.authenticity_check.exif.anomalies.join(', ')}</p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Duplicate Detection */}
                  {result.authenticity_check.phash && result.authenticity_check.phash.duplicates_found.length > 0 && (
                    <div className="rounded-lg border bg-background p-5">
                      <div className="flex items-center gap-2 mb-3 pb-3 border-b">
                        <div className="p-1.5 rounded-md bg-red-500/10">
                          <AlertCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
                        </div>
                        <div>
                          <h4 className="text-sm font-semibold">Duplicate Detection</h4>
                          <p className="text-xs text-muted-foreground">Perceptual hash analysis</p>
                        </div>
                      </div>
                      <Badge variant="destructive">
                        {result.authenticity_check.phash.duplicates_found.length} duplicates found
                      </Badge>
                    </div>
                  )}

                  {/* Tampering Detection (ELA) */}
                  {result.authenticity_check.ela && (
                    <div className="rounded-lg border bg-background p-5">
                      <div className="flex items-center gap-2 mb-3 pb-3 border-b">
                        <div className={`p-1.5 rounded-md ${result.authenticity_check.ela.anomaly_detected ? 'bg-red-500/10' : 'bg-green-500/10'}`}>
                          <Shield className={`h-4 w-4 ${result.authenticity_check.ela.anomaly_detected ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`} />
                        </div>
                        <div>
                          <h4 className="text-sm font-semibold">Tampering Detection (ELA)</h4>
                          <p className="text-xs text-muted-foreground">Error level analysis</p>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <Badge className={result.authenticity_check.ela.anomaly_detected ? "bg-red-500/20 text-red-700 dark:text-red-300 border-red-500/30" : "bg-green-500/20 text-green-700 dark:text-green-300 border-green-500/30"}>
                          {result.authenticity_check.ela.anomaly_detected ? "Tampering Detected" : "No Tampering"}
                        </Badge>
                        <p className="text-sm text-muted-foreground">
                          Confidence: <span className="font-medium text-foreground">{(result.authenticity_check.ela.confidence * 100).toFixed(0)}%</span>
                        </p>
                      </div>
                    </div>
                  )}

                  {/* AI Generation Detection */}
                  {result.authenticity_check.ai_generation && result.authenticity_check.ai_generation.likelihood > 0.3 && (
                    <div className="rounded-lg border bg-background p-5">
                      <div className="flex items-center gap-2 mb-3 pb-3 border-b">
                        <div className={`p-1.5 rounded-md ${result.authenticity_check.ai_generation.likelihood > 0.6 ? 'bg-red-500/10' : 'bg-yellow-500/10'}`}>
                          <Zap className={`h-4 w-4 ${result.authenticity_check.ai_generation.likelihood > 0.6 ? 'text-red-600 dark:text-red-400' : 'text-yellow-600 dark:text-yellow-400'}`} />
                        </div>
                        <div>
                          <h4 className="text-sm font-semibold">AI Generation Detection</h4>
                          <p className="text-xs text-muted-foreground">Machine learning analysis</p>
                        </div>
                      </div>
                      <div className="space-y-3">
                        <Badge className={result.authenticity_check.ai_generation.likelihood > 0.6 ? "bg-red-500/20 text-red-700 dark:text-red-300 border-red-500/30" : "bg-yellow-500/20 text-yellow-700 dark:text-yellow-300 border-yellow-500/30"}>
                          {(result.authenticity_check.ai_generation.likelihood * 100).toFixed(0)}% likelihood
                        </Badge>
                        {result.authenticity_check.ai_generation.indicators.length > 0 && (
                          <div className="p-3 rounded-md bg-muted/50">
                            <p className="text-sm font-medium mb-2">Indicators:</p>
                            <div className="flex flex-wrap gap-2">
                              {result.authenticity_check.ai_generation.indicators.map((indicator, idx) => (
                                <Badge key={idx} variant="outline" className="text-xs">
                                  {indicator}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Reverse Image Search */}
                  {result.authenticity_check.reverse_search && result.authenticity_check.reverse_search.total_matches > 0 && (
                    <div className="rounded-lg border bg-background p-5">
                      <div className="flex items-center gap-2 mb-3 pb-3 border-b">
                        <div className={`p-1.5 rounded-md ${
                          result.authenticity_check.reverse_search.authenticity_risk === "High" ? 'bg-red-500/10' :
                          result.authenticity_check.reverse_search.authenticity_risk === "Med" ? 'bg-yellow-500/10' : 'bg-green-500/10'
                        }`}>
                          <Search className={`h-4 w-4 ${
                            result.authenticity_check.reverse_search.authenticity_risk === "High" ? 'text-red-600 dark:text-red-400' :
                            result.authenticity_check.reverse_search.authenticity_risk === "Med" ? 'text-yellow-600 dark:text-yellow-400' : 'text-green-600 dark:text-green-400'
                          }`} />
                        </div>
                        <div>
                          <h4 className="text-sm font-semibold">Reverse Image Search</h4>
                          <p className="text-xs text-muted-foreground">Internet image matching</p>
                        </div>
                      </div>
                      <div className="space-y-3">
                        <Badge className={
                          result.authenticity_check.reverse_search.authenticity_risk === "High" ? "bg-red-500/20 text-red-700 dark:text-red-300 border-red-500/30" :
                          result.authenticity_check.reverse_search.authenticity_risk === "Med" ? "bg-yellow-500/20 text-yellow-700 dark:text-yellow-300 border-yellow-500/30" : "bg-green-500/20 text-green-700 dark:text-green-300 border-green-500/30"
                        }>
                          {result.authenticity_check.reverse_search.total_matches} matches found
                        </Badge>

                        {result.authenticity_check.reverse_search.exact_matches.length > 0 && (
                          <div className="p-3 rounded-md bg-muted/50">
                            <p className="text-sm font-semibold mb-2">Exact Matches:</p>
                            <ul className="space-y-1">
                              {result.authenticity_check.reverse_search.exact_matches.slice(0, 3).map((match, idx) => (
                                <li key={idx} className="text-sm">
                                  <a href={match.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 hover:underline">
                                    {match.page_title || match.url}
                                  </a>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {result.authenticity_check.reverse_search.partial_matches.length > 0 && (
                          <div className="p-3 rounded-md bg-muted/50">
                            <p className="text-sm font-semibold mb-2">Similar Images:</p>
                            <ul className="space-y-1">
                              {result.authenticity_check.reverse_search.partial_matches.slice(0, 3).map((match, idx) => (
                                <li key={idx} className="text-sm">
                                  <a href={match.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 hover:underline">
                                    {match.page_title || match.url}
                                  </a>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

          {/* Document Audit Trail Table */}
          <div className="mt-8">
            <div className="mb-6">
              <h2 className="text-2xl font-bold">Documents</h2>
              <Separator className="mt-4" />
            </div>

            {/* Search and Filter Bar */}
            <div className="mb-4 w-full">
              <div className="flex items-center gap-3 flex-wrap">
                {/* Document Type Filter */}
                <Select value={selectedDocType} onValueChange={setSelectedDocType}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Document Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="pdf">PDF</SelectItem>
                    <SelectItem value="docx">DOCX</SelectItem>
                    <SelectItem value="png">PNG</SelectItem>
                    <SelectItem value="jpg">JPG</SelectItem>
                    <SelectItem value="jpeg">JPEG</SelectItem>
                  </SelectContent>
                </Select>

                {/* Date Filter */}
                <Select value={selectedDate} onValueChange={setSelectedDate}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Date" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Dates</SelectItem>
                    <SelectItem value="today">Today</SelectItem>
                    <SelectItem value="week">This Week</SelectItem>
                    <SelectItem value="month">This Month</SelectItem>
                  </SelectContent>
                </Select>

                {/* Type Filter */}
                <Select value={selectedStaff} onValueChange={setSelectedStaff}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="msa">MSA</SelectItem>
                    <SelectItem value="sow">SOW</SelectItem>
                    <SelectItem value="nda">NDA</SelectItem>
                    <SelectItem value="amendment">Amendment</SelectItem>
                    <SelectItem value="aml_investigation_report">AML Investigation Report</SelectItem>
                    <SelectItem value="risk_assessment_report">Risk Assessment Report</SelectItem>
                    <SelectItem value="operational_periodic_report">Operational Periodic Report</SelectItem>
                    <SelectItem value="board_pack_summary">Board Pack Summary</SelectItem>
                  </SelectContent>
                </Select>

                {/* Risk Level Filter */}
                <Select value={selectedCategory} onValueChange={setSelectedCategory}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Risk Level" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Risk Levels</SelectItem>
                    <SelectItem value="low">Low Risk</SelectItem>
                    <SelectItem value="med">Medium Risk</SelectItem>
                    <SelectItem value="high">High Risk</SelectItem>
                  </SelectContent>
                </Select>

                {/* Results Count */}
                <div className="text-sm text-muted-foreground">
                  Showing {auditTrail.filter(doc => {
                    let matches = true
                    if (selectedDocType !== 'all' && doc.document_type !== selectedDocType) matches = false
                    if (selectedStaff !== 'all' && doc.doc_subtype !== selectedStaff) matches = false
                    if (selectedCategory !== 'all' && doc.risk_level.toLowerCase() !== selectedCategory.toLowerCase()) matches = false
                    if (selectedDate !== 'all') {
                      const docDate = new Date(doc.upload_date)
                      const now = new Date()
                      if (selectedDate === 'today' && docDate.toDateString() !== now.toDateString()) matches = false
                      if (selectedDate === 'week') {
                        const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
                        if (docDate < weekAgo) matches = false
                      }
                      if (selectedDate === 'month') {
                        const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
                        if (docDate < monthAgo) matches = false
                      }
                    }
                    if (searchQuery) {
                      const query = searchQuery.toLowerCase()
                      const matchesSearch = doc.document_name.toLowerCase().includes(query) ||
                                          doc.document_type.toLowerCase().includes(query) ||
                                          doc.uploaded_by.toLowerCase().includes(query) ||
                                          doc.risk_level.toLowerCase().includes(query)
                      if (!matchesSearch) matches = false
                    }
                    return matches
                  }).length} of {auditTrail.length} documents
                </div>

                {/* Search - Right aligned */}
                <div className="relative ml-auto">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search documents..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10 w-[300px]"
                  />
                </div>
              </div>
            </div>

            <div>
              {loadingAudit ? (
                <div className="text-center py-8 text-muted-foreground">
                  Loading audit trail...
                </div>
              ) : auditTrail.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No documents analyzed yet. Upload a document to get started.
                </div>
              ) : (() => {
                // Apply filters
                const filteredAuditTrail = auditTrail.filter(doc => {
                  let matches = true
                  if (selectedDocType !== 'all' && doc.document_type !== selectedDocType) matches = false
                  if (selectedStaff !== 'all' && doc.doc_subtype !== selectedStaff) matches = false
                  if (selectedCategory !== 'all' && doc.risk_level.toLowerCase() !== selectedCategory.toLowerCase()) matches = false
                  if (selectedDate !== 'all') {
                    const docDate = new Date(doc.upload_date)
                    const now = new Date()
                    if (selectedDate === 'today' && docDate.toDateString() !== now.toDateString()) matches = false
                    if (selectedDate === 'week') {
                      const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
                      if (docDate < weekAgo) matches = false
                    }
                    if (selectedDate === 'month') {
                      const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
                      if (docDate < monthAgo) matches = false
                    }
                  }
                  if (searchQuery) {
                    const query = searchQuery.toLowerCase()
                    const matchesSearch = doc.document_name.toLowerCase().includes(query) ||
                                        doc.document_type.toLowerCase().includes(query) ||
                                        (doc.doc_subtype && doc.doc_subtype.toLowerCase().includes(query)) ||
                                        doc.risk_level.toLowerCase().includes(query)
                    if (!matchesSearch) matches = false
                  }
                  return matches
                })

                return filteredAuditTrail.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No documents match your filters. Try adjusting your search criteria.
                  </div>
                ) : (
                  <div className="border rounded-lg overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[50px]">
                            <input type="checkbox" className="rounded" />
                          </TableHead>
                          <TableHead>Document Name</TableHead>
                          <TableHead>Document Type</TableHead>
                          <TableHead>Document Date</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Region</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Risk Level</TableHead>
                          <TableHead className="text-right">Operation</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filteredAuditTrail.map((doc) => (
                        <TableRow key={doc.id}>
                          <TableCell>
                            <input type="checkbox" className="rounded" />
                          </TableCell>
                          <TableCell className="font-medium">{doc.document_name}</TableCell>
                          <TableCell className="capitalize">{doc.document_type}</TableCell>
                          <TableCell>
                            {new Date(doc.upload_date).toLocaleDateString('en-US', {
                              day: '2-digit',
                              month: '2-digit',
                              year: 'numeric'
                            })}
                          </TableCell>
                          <TableCell className="capitalize">{doc.doc_subtype || '-'}</TableCell>
                          <TableCell>-</TableCell>
                          <TableCell>
                            <Badge className="bg-green-500/20 text-green-700 dark:text-green-300 border-green-500/30">
                              {doc.status}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Badge className={getRiskColor(doc.risk_level)}>
                              {doc.risk_level} Risk
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex justify-end gap-2">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() => {
                                  setSelectedAuditDoc(doc)
                                  setShowAuditDetail(true)
                                }}
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                              <Button variant="ghost" size="icon" className="h-8 w-8">
                                <FileCheck className="h-4 w-4" />
                              </Button>
                              <Button variant="ghost" size="icon" className="h-8 w-8">
                                <AlertCircle className="h-4 w-4" />
                              </Button>
                              <Button variant="ghost" size="icon" className="h-8 w-8">
                                <Download className="h-4 w-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
                )
              })()}

              {auditTrail.length > 0 && (
                <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
                  <div>1-{Math.min(auditTrail.length, 10)} of {auditTrail.length} documents</div>
                  <div className="flex items-center gap-2">
                    <span>You're on page</span>
                    <Select defaultValue="1">
                      <SelectTrigger className="w-16 h-8">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="1">1</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                      →
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Audit Document Detail Dialog */}
        <Dialog open={showAuditDetail} onOpenChange={setShowAuditDetail}>
          <DialogContent className="!max-w-[80vw] max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <FileCheck className="h-5 w-5" />
                Document Risk Assessment
              </DialogTitle>
              <DialogDescription>
                Detailed analysis for {selectedAuditDoc?.document_name}
              </DialogDescription>
            </DialogHeader>

            {selectedAuditDoc && (
              <div className="space-y-6 mt-4">
                {/* Risk Assessment Summary */}
                <div className="rounded-xl border bg-muted/40 overflow-hidden">
                  <div className="px-6 py-5 border-b bg-muted/50">
                    <div className="flex items-center justify-between">
                      <div className="text-left">
                        <h3 className="text-lg font-semibold">Overall Risk Assessment</h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Last analyzed {new Date(selectedAuditDoc.upload_date).toLocaleDateString()}
                        </p>
                      </div>
                      <Badge className={`${getRiskColor(selectedAuditDoc.risk_level)} px-4 py-1.5 text-sm font-medium`}>
                        {selectedAuditDoc.risk_level} Risk
                      </Badge>
                    </div>
                  </div>

                  {/* Metrics Grid */}
                  <div className="p-6">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                      <div className="group relative overflow-hidden rounded-lg border bg-background p-5 transition-all hover:shadow-sm">
                        <div className="mb-3">
                          <div>
                            <p className="text-xs font-medium text-muted-foreground mb-1">Overall Score</p>
                            <div className="flex items-baseline gap-1">
                              <span className="text-3xl font-bold tracking-tight">{selectedAuditDoc.overall_risk_score?.toFixed(1)}</span>
                              <span className="text-sm text-muted-foreground">/100</span>
                            </div>
                          </div>
                        </div>
                        <div className="h-1 w-full bg-muted rounded-full overflow-hidden">
                          <div
                            className={`h-full transition-all ${
                              selectedAuditDoc.risk_level === 'Low'
                                ? 'bg-green-500'
                                : selectedAuditDoc.risk_level === 'Med'
                                ? 'bg-yellow-500'
                                : 'bg-red-500'
                            }`}
                            style={{ width: `${selectedAuditDoc.overall_risk_score}%` }}
                          />
                        </div>
                      </div>

                      <div className="group relative overflow-hidden rounded-lg border bg-background p-5 transition-all hover:shadow-sm">
                        <div className="mb-3">
                          <div>
                            <p className="text-xs font-medium text-muted-foreground mb-1">Format Risk</p>
                            <div className="flex items-baseline gap-1">
                              <span className="text-3xl font-bold tracking-tight">{selectedAuditDoc.format_risk?.toFixed(1)}</span>
                              <span className="text-sm text-muted-foreground">/100</span>
                            </div>
                          </div>
                        </div>
                        <div className="h-1 w-full bg-muted rounded-full overflow-hidden">
                          <div
                            className={`h-full transition-all ${
                              selectedAuditDoc.format_risk < 30
                                ? 'bg-green-500'
                                : selectedAuditDoc.format_risk < 60
                                ? 'bg-yellow-500'
                                : 'bg-red-500'
                            }`}
                            style={{ width: `${selectedAuditDoc.format_risk}%` }}
                          />
                        </div>
                      </div>

                      <div className="group relative overflow-hidden rounded-lg border bg-background p-5 transition-all hover:shadow-sm">
                        <div className="mb-3">
                          <div>
                            <p className="text-xs font-medium text-muted-foreground mb-1">Authenticity Risk</p>
                            <div className="flex items-baseline gap-1">
                              <span className="text-3xl font-bold tracking-tight">{selectedAuditDoc.authenticity_risk?.toFixed(1)}</span>
                              <span className="text-sm text-muted-foreground">/100</span>
                            </div>
                          </div>
                        </div>
                        <div className="h-1 w-full bg-muted rounded-full overflow-hidden">
                          <div
                            className={`h-full transition-all ${
                              selectedAuditDoc.authenticity_risk < 30
                                ? 'bg-green-500'
                                : selectedAuditDoc.authenticity_risk < 60
                                ? 'bg-yellow-500'
                                : 'bg-red-500'
                            }`}
                            style={{ width: `${selectedAuditDoc.authenticity_risk}%` }}
                          />
                        </div>
                      </div>
                    </div>

                    {/* Risk Factors */}
                    {selectedAuditDoc.risk_justifications && selectedAuditDoc.risk_justifications.length > 0 && (
                      <div className="rounded-lg border bg-background p-5">
                        <div className="flex items-center gap-2 mb-4 pb-3 border-b">
                          <div className="p-1.5 rounded-md bg-orange-500/10">
                            <AlertCircle className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                          </div>
                          <div>
                            <h4 className="text-sm font-semibold">Risk Factors Detected</h4>
                            <p className="text-xs text-muted-foreground">{selectedAuditDoc.risk_justifications.length} issues identified</p>
                          </div>
                        </div>
                        <div className="space-y-3">
                          {selectedAuditDoc.risk_justifications.slice(0, 5).map((just: any, idx: number) => (
                            <div key={idx} className="flex items-start gap-3 py-2 px-3 rounded-lg">
                              <div className="flex-shrink-0 mt-1.5">
                                <div className="h-1.5 w-1.5 rounded-full bg-orange-500" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="text-xs font-medium text-orange-600 dark:text-orange-400 uppercase tracking-wider">{just.category}</span>
                                  <span className="text-xs text-muted-foreground">•</span>
                                  <span className="text-xs text-muted-foreground">Severity: {just.severity || 'Medium'}</span>
                                </div>
                                <p className="text-sm text-foreground leading-relaxed">{just.reason}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Document Info */}
                <div className="rounded-lg border bg-background p-4">
                  <h4 className="text-sm font-semibold mb-3">Document Information</h4>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">Document Name</p>
                      <p className="font-medium">{selectedAuditDoc.document_name}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Document Type</p>
                      <p className="font-medium capitalize">{selectedAuditDoc.document_type}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">File Size</p>
                      <p className="font-medium">{selectedAuditDoc.file_size_kb?.toFixed(2)} KB</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Uploaded By</p>
                      <p className="font-medium">{selectedAuditDoc.uploaded_by}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Upload Date</p>
                      <p className="font-medium">{new Date(selectedAuditDoc.upload_date).toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Status</p>
                      <Badge className="bg-green-500/20 text-green-700 dark:text-green-300 border-green-500/30">
                        {selectedAuditDoc.status}
                      </Badge>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </SidebarInset>
    </SidebarProvider>
  )
}
