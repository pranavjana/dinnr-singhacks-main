"use client"

import { AppSidebar } from "@/components/app-sidebar"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { MultiStepLoader } from "@/components/ui/multi-step-loader"
import { RefreshCw, Shield, CheckCircle, XCircle, AlertCircle, Download } from "lucide-react"
import { useState, useEffect } from "react"
import { api } from "@/lib/api"
import type {
  ComplianceRule,
  ComplianceRulesResponse,
  BatchExtractionResponse
} from "@/types/rules"
import { toast } from "sonner"

const loadingStates = [
  { text: "Initializing rule extraction workflow..." },
  { text: "Retrieving regulatory documents from database..." },
  { text: "Analyzing document embeddings..." },
  { text: "Extracting threshold rules..." },
  { text: "Extracting deadline requirements..." },
  { text: "Extracting EDD trigger conditions..." },
  { text: "Validating extracted compliance rules..." },
  { text: "Checking for duplicate rules..." },
  { text: "Storing rules in database..." },
  { text: "Finalizing rule extraction..." },
]

type AuditLogEntry = {
  id: string
  timestamp: Date
  dateUpdated?: Date
  action: string
  user: string
  rulesCreated: number
  rulesUpdated: number
  status: 'success' | 'failed'
  details: string
}

export default function RulesPage() {
  const [isGenerating, setIsGenerating] = useState(false)
  const [rules, setRules] = useState<ComplianceRule[]>([])
  const [isLoadingRules, setIsLoadingRules] = useState(false)
  const [lastExtractionResult, setLastExtractionResult] = useState<BatchExtractionResponse | null>(null)
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([])

  // Load existing rules on mount
  useEffect(() => {
    loadRules()
  }, [])

  const loadRules = async () => {
    setIsLoadingRules(true)
    try {
      const response = await api.getComplianceRules({
        active_only: true,
        limit: 100,
      }) as ComplianceRulesResponse

      setRules(response.rules)
    } catch (error) {
      console.error('Failed to load rules:', error)
      toast.error("Error loading rules", {
        description: error instanceof Error ? error.message : "Failed to fetch compliance rules",
      })
    } finally {
      setIsLoadingRules(false)
    }
  }

  const downloadAuditCSV = () => {
    if (auditLog.length === 0) {
      toast.error("No audit data available", {
        description: "Generate rules first to create audit history",
      })
      return
    }

    const headers = ['Timestamp', 'Date Updated', 'Action', 'User', 'Rules Created', 'Rules Updated', 'Status', 'Details']
    const csvContent = [
      headers.join(','),
      ...auditLog.map(entry => [
        entry.timestamp.toISOString(),
        (entry.dateUpdated || entry.timestamp).toISOString(),
        entry.action,
        entry.user,
        entry.rulesCreated,
        entry.rulesUpdated,
        entry.status,
        `"${entry.details.replace(/"/g, '""')}"`
      ].join(','))
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)
    link.setAttribute('href', url)
    link.setAttribute('download', `audit-trail-${new Date().toISOString().split('T')[0]}.csv`)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)

    toast.success("Audit trail downloaded", {
      description: "CSV file has been downloaded successfully",
    })
  }

  const handleGenerateRules = async () => {
    setIsGenerating(true)
    try {
      // For demo purposes, we'll use a hardcoded document ID from your setup
      // In production, you'd fetch all document IDs from the database first
      const demoDocumentId = "2da2a71d-643c-4e4c-bdec-61a9a1d79054"

      toast.info("Starting rule extraction", {
        description: "Processing regulatory documents...",
      })

      const response = await api.extractRulesBatch({
        document_ids: [demoDocumentId],
        jurisdiction: "SG",
        target_rule_types: ["threshold", "deadline", "edd_trigger"],
      }) as BatchExtractionResponse

      setLastExtractionResult(response)

      if (response.successful > 0) {
        const totalRulesCreated = response.results.reduce((sum, r) => sum + r.rules_created, 0)
        const totalCost = response.results.reduce((sum, r) => sum + r.cost_usd, 0)
        
        // Add to audit log
        const newAuditEntry: AuditLogEntry = {
          id: crypto.randomUUID(),
          timestamp: new Date(),
          dateUpdated: new Date(),
          action: 'Rule Extraction',
          user: 'System',
          rulesCreated: totalRulesCreated,
          rulesUpdated: 0,
          status: 'success',
          details: `Successfully extracted ${totalRulesCreated} rules from ${response.successful} document(s). Jurisdiction: SG, Types: threshold, deadline, edd_trigger`
        }
        setAuditLog(prev => [newAuditEntry, ...prev])

        toast.success("Rules generated successfully", {
          description: `Extracted ${totalRulesCreated} new rules from ${response.successful} document(s)`,
        })

        // Reload rules to show the new ones
        await loadRules()
      } else {
        // Add failed audit entry
        const failedAuditEntry: AuditLogEntry = {
          id: crypto.randomUUID(),
          timestamp: new Date(),
          dateUpdated: new Date(),
          action: 'Rule Extraction',
          user: 'System',
          rulesCreated: 0,
          rulesUpdated: 0,
          status: 'failed',
          details: `Failed to extract rules from ${response.failed} document(s)`
        }
        setAuditLog(prev => [failedAuditEntry, ...prev])

        toast.error("Rule extraction completed with errors", {
          description: `Failed to extract rules from ${response.failed} document(s)`,
        })
      }
    } catch (error) {
      // Add error audit entry
      const errorAuditEntry: AuditLogEntry = {
        id: crypto.randomUUID(),
        timestamp: new Date(),
        dateUpdated: new Date(),
        action: 'Rule Extraction',
        user: 'System',
        rulesCreated: 0,
        rulesUpdated: 0,
        status: 'failed',
        details: `Error: ${error instanceof Error ? error.message : 'Unknown error occurred'}`
      }
      setAuditLog(prev => [errorAuditEntry, ...prev])

      console.error('Failed to generate rules:', error)
      toast.error("Error generating rules", {
        description: error instanceof Error ? error.message : "Failed to extract rules from documents",
      })
    } finally {
      setIsGenerating(false)
    }
  }

  return (
    <>
      <MultiStepLoader 
        loadingStates={loadingStates} 
        loading={isGenerating} 
        duration={4000}
        loop={false}
      />
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
        <header className="flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
          <div className="flex items-center gap-2 px-4">
            <SidebarTrigger className="-ml-1" />
            <Separator
              orientation="vertical"
              className="mr-2 data-[orientation=vertical]:h-4"
            />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem className="hidden md:block">
                  <BreadcrumbLink href="/dashboard">
                    Dashboard
                  </BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden md:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage>Compliance Rules</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>
        <div className="flex flex-1 flex-col gap-4 p-4 pt-0 min-w-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield className="h-6 w-6" />
              <h1 className="text-2xl font-bold">Compliance Rules</h1>
            </div>
            <Button
              onClick={handleGenerateRules}
              disabled={isGenerating}
              className="gap-2"
            >
              <RefreshCw className={`h-4 w-4 ${isGenerating ? 'animate-spin' : ''}`} />
              {isGenerating ? 'Generating...' : 'Generate Updated Rules'}
            </Button>
          </div>

          <Tabs defaultValue="current" className="w-full min-w-0">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="current">Current Rules</TabsTrigger>
              <TabsTrigger value="pending">Pending Updates</TabsTrigger>
              <TabsTrigger value="history">History</TabsTrigger>
            </TabsList>

            <TabsContent value="current" className="space-y-4 min-w-0">
              {isLoadingRules ? (
                <div className="rounded-lg border bg-card p-6">
                  <p className="text-muted-foreground">Loading rules...</p>
                </div>
              ) : rules.length === 0 ? (
                <div className="rounded-lg border bg-card p-6">
                  <h3 className="text-lg font-semibold mb-4">Active Compliance Rules</h3>
                  <p className="text-muted-foreground">
                    No compliance rules found. Click "Generate Updated Rules" to fetch the latest regulatory requirements.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {rules.filter(r => r.validation_status === 'validated').map((rule) => (
                    <div key={rule.id} className="rounded-lg border bg-card p-4">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <CheckCircle className="h-5 w-5 text-green-500" />
                          <h4 className="font-semibold">{rule.rule_type}</h4>
                          <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded">
                            {rule.jurisdiction}
                          </span>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          Confidence: {(rule.extraction_confidence * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground mb-2">{rule.source_text}</p>
                      <div className="flex gap-2 text-xs text-muted-foreground">
                        <span>Regulator: {rule.regulator}</span>
                        {rule.circular_number && <span>• {rule.circular_number}</span>}
                        {rule.effective_date && <span>• Effective: {new Date(rule.effective_date).toLocaleDateString()}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="pending" className="space-y-4 min-w-0">
              {isLoadingRules ? (
                <div className="rounded-lg border bg-card p-6">
                  <p className="text-muted-foreground">Loading rules...</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {rules.filter(r => r.validation_status === 'pending').length === 0 ? (
                    <div className="rounded-lg border bg-card p-6">
                      <h3 className="text-lg font-semibold mb-4">Pending Rule Updates</h3>
                      <p className="text-muted-foreground">
                        No pending compliance rule updates at this time.
                      </p>
                    </div>
                  ) : (
                    rules.filter(r => r.validation_status === 'pending').map((rule) => (
                      <div key={rule.id} className="rounded-lg border bg-card p-4">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <AlertCircle className="h-5 w-5 text-yellow-500" />
                            <h4 className="font-semibold">{rule.rule_type}</h4>
                            <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded">
                              {rule.jurisdiction}
                            </span>
                          </div>
                          <span className="text-xs text-muted-foreground">
                            Confidence: {(rule.extraction_confidence * 100).toFixed(1)}%
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground mb-2">{rule.source_text}</p>
                        <div className="flex gap-2 text-xs text-muted-foreground">
                          <span>Regulator: {rule.regulator}</span>
                          {rule.circular_number && <span>• {rule.circular_number}</span>}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </TabsContent>

            <TabsContent value="history" className="space-y-4 min-w-0">
              <div className="rounded-lg border bg-card overflow-hidden">
                <div className="p-6 flex items-center justify-between border-b">
                  <div>
                    <h3 className="text-lg font-semibold">Audit Trail</h3>
                    <p className="text-sm text-muted-foreground">Complete history of all rule extraction activities</p>
                  </div>
                  <Button
                    onClick={downloadAuditCSV}
                    disabled={auditLog.length === 0}
                    variant="outline"
                    className="gap-2"
                  >
                    <Download className="h-4 w-4" />
                    Download CSV
                  </Button>
                </div>
                
                {auditLog.length === 0 ? (
                  <div className="p-6">
                    <p className="text-muted-foreground text-center">
                      No audit history available. Generate rules to create audit trail entries.
                    </p>
                  </div>
                ) : (
                  <div className="w-full">
                    <table className="w-full caption-bottom text-sm">
                      <thead className="[&_tr]:border-b">
                        <tr className="hover:bg-muted/50 data-[state=selected]:bg-muted border-b transition-colors">
                          <th className="text-foreground h-10 px-2 text-left align-middle font-medium w-[140px]">Timestamp</th>
                          <th className="text-foreground h-10 px-2 text-left align-middle font-medium w-[140px]">Date Updated</th>
                          <th className="text-foreground h-10 px-2 text-left align-middle font-medium w-[100px]">Action</th>
                          <th className="text-foreground h-10 px-2 text-left align-middle font-medium w-[80px]">User</th>
                          <th className="text-foreground h-10 px-2 text-right align-middle font-medium w-[80px]">Created</th>
                          <th className="text-foreground h-10 px-2 text-right align-middle font-medium w-[80px]">Updated</th>
                          <th className="text-foreground h-10 px-2 text-left align-middle font-medium w-[90px]">Status</th>
                          <th className="text-foreground h-10 px-2 text-left align-middle font-medium">Details</th>
                        </tr>
                      </thead>
                      <tbody className="[&_tr:last-child]:border-0">
                        {auditLog.map((entry) => (
                          <tr key={entry.id} className="hover:bg-muted/50 data-[state=selected]:bg-muted border-b transition-colors">
                            <td className="p-2 align-middle font-mono text-xs">
                              <div className="break-words">
                                {entry.timestamp.toLocaleString()}
                              </div>
                            </td>
                            <td className="p-2 align-middle font-mono text-xs">
                              <div className="break-words">
                                {(entry.dateUpdated || entry.timestamp).toLocaleString()}
                              </div>
                            </td>
                            <td className="p-2 align-middle font-medium">
                              <div className="break-words">{entry.action}</div>
                            </td>
                            <td className="p-2 align-middle">
                              <div className="break-words">{entry.user}</div>
                            </td>
                            <td className="p-2 align-middle text-right">{entry.rulesCreated}</td>
                            <td className="p-2 align-middle text-right">{entry.rulesUpdated}</td>
                            <td className="p-2 align-middle">
                              <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                                entry.status === 'success'
                                  ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                  : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                              }`}>
                                {entry.status === 'success' ? (
                                  <CheckCircle className="h-3 w-3" />
                                ) : (
                                  <XCircle className="h-3 w-3" />
                                )}
                                {entry.status}
                              </span>
                            </td>
                            <td className="p-2 align-middle">
                              <div className="text-sm text-muted-foreground break-words">
                                {entry.details}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </SidebarInset>
    </SidebarProvider>
    </>
  )
}
