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
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { RefreshCw, Shield, CheckCircle, XCircle, AlertCircle, Download, ChevronDown, Check, Filter } from "lucide-react"
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
  const [expandedPendingRules, setExpandedPendingRules] = useState<Set<string>>(new Set())
  const [approvingRules, setApprovingRules] = useState<Set<string>>(new Set())

  // Filter states for current rules
  const [filterRuleType, setFilterRuleType] = useState<string>('all')
  const [filterJurisdiction, setFilterJurisdiction] = useState<string>('all')
  const [filterRegulator, setFilterRegulator] = useState<string>('all')

  // Filter states for pending rules
  const [pendingFilterRuleType, setPendingFilterRuleType] = useState<string>('all')
  const [pendingFilterJurisdiction, setPendingFilterJurisdiction] = useState<string>('all')
  const [pendingFilterRegulator, setPendingFilterRegulator] = useState<string>('all')

  // Load existing rules and audit trail on mount
  useEffect(() => {
    loadRules()
    loadAuditTrail()
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

  const loadAuditTrail = async () => {
    try {
      const response = await api.getAuditTrail(100) as { entries: any[] }

      // Convert database entries to AuditLogEntry format
      const entries: AuditLogEntry[] = response.entries.map(entry => ({
        id: entry.id,
        timestamp: new Date(entry.timestamp),
        dateUpdated: entry.date_updated ? new Date(entry.date_updated) : new Date(entry.timestamp),
        action: entry.action,
        user: entry.user_name,
        rulesCreated: entry.rules_created,
        rulesUpdated: entry.rules_updated,
        status: entry.status as 'success' | 'failed',
        details: entry.details || ''
      }))

      setAuditLog(entries)
    } catch (error) {
      console.error('Failed to load audit trail:', error)
      // Don't show error toast for audit trail loading failure
    }
  }

  const saveAuditEntry = async (entry: Omit<AuditLogEntry, 'id'>) => {
    try {
      await api.createAuditEntry({
        action: entry.action,
        user_name: entry.user,
        rules_created: entry.rulesCreated,
        rules_updated: entry.rulesUpdated,
        status: entry.status,
        details: entry.details
      })
    } catch (error) {
      console.error('Failed to save audit entry:', error)
      // Don't show error toast, just log it
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

  const togglePendingRule = (ruleId: string) => {
    setExpandedPendingRules(prev => {
      const newSet = new Set(prev)
      if (newSet.has(ruleId)) {
        newSet.delete(ruleId)
      } else {
        newSet.add(ruleId)
      }
      return newSet
    })
  }

  const handleApproveRule = async (rule: ComplianceRule) => {
    setApprovingRules(prev => new Set(prev).add(rule.id))
    try {
      await api.validateRule(rule.id, 'User') // You can replace 'User' with actual user name

      toast.success("Rule approved", {
        description: `${rule.rule_type} has been added to active rules`,
      })

      // Add to audit log and save to database
      const approvalAuditEntry: AuditLogEntry = {
        id: crypto.randomUUID(),
        timestamp: new Date(),
        dateUpdated: new Date(),
        action: 'Rule Approval',
        user: 'User',
        rulesCreated: 0,
        rulesUpdated: 1,
        status: 'success',
        details: `Approved ${rule.rule_type} rule (${rule.jurisdiction})`
      }
      setAuditLog(prev => [approvalAuditEntry, ...prev])
      await saveAuditEntry(approvalAuditEntry)

      // Reload rules to reflect the change
      await loadRules()
    } catch (error) {
      console.error('Failed to approve rule:', error)
      toast.error("Error approving rule", {
        description: error instanceof Error ? error.message : "Failed to validate rule",
      })
    } finally {
      setApprovingRules(prev => {
        const newSet = new Set(prev)
        newSet.delete(rule.id)
        return newSet
      })
    }
  }

  // Get unique values for filters
  const getUniqueRuleTypes = () => {
    const types = new Set(rules.filter(r => r.validation_status === 'validated').map(r => r.rule_type))
    return Array.from(types).sort()
  }

  const getUniqueJurisdictions = () => {
    const jurisdictions = new Set(rules.filter(r => r.validation_status === 'validated').map(r => r.jurisdiction))
    return Array.from(jurisdictions).sort()
  }

  const getUniqueRegulators = () => {
    const regulators = new Set(rules.filter(r => r.validation_status === 'validated').map(r => r.regulator))
    return Array.from(regulators).sort()
  }

  // Filter rules
  const getFilteredRules = () => {
    return rules
      .filter(r => r.validation_status === 'validated')
      .filter(r => filterRuleType === 'all' || r.rule_type === filterRuleType)
      .filter(r => filterJurisdiction === 'all' || r.jurisdiction === filterJurisdiction)
      .filter(r => filterRegulator === 'all' || r.regulator === filterRegulator)
  }

  const clearFilters = () => {
    setFilterRuleType('all')
    setFilterJurisdiction('all')
    setFilterRegulator('all')
  }

  // Get unique values for pending filters
  const getUniquePendingRuleTypes = () => {
    const types = new Set(rules.filter(r => r.validation_status === 'pending').map(r => r.rule_type))
    return Array.from(types).sort()
  }

  const getUniquePendingJurisdictions = () => {
    const jurisdictions = new Set(rules.filter(r => r.validation_status === 'pending').map(r => r.jurisdiction))
    return Array.from(jurisdictions).sort()
  }

  const getUniquePendingRegulators = () => {
    const regulators = new Set(rules.filter(r => r.validation_status === 'pending').map(r => r.regulator))
    return Array.from(regulators).sort()
  }

  // Filter pending rules
  const getFilteredPendingRules = () => {
    return rules
      .filter(r => r.validation_status === 'pending')
      .filter(r => pendingFilterRuleType === 'all' || r.rule_type === pendingFilterRuleType)
      .filter(r => pendingFilterJurisdiction === 'all' || r.jurisdiction === pendingFilterJurisdiction)
      .filter(r => pendingFilterRegulator === 'all' || r.regulator === pendingFilterRegulator)
  }

  const clearPendingFilters = () => {
    setPendingFilterRuleType('all')
    setPendingFilterJurisdiction('all')
    setPendingFilterRegulator('all')
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
        
        // Add to audit log and save to database
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
        await saveAuditEntry(newAuditEntry)

        toast.success("Rules generated successfully", {
          description: `Extracted ${totalRulesCreated} new rules from ${response.successful} document(s)`,
        })

        // Reload rules to show the new ones
        await loadRules()
      } else {
        // Add failed audit entry and save to database
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
        await saveAuditEntry(failedAuditEntry)

        toast.error("Rule extraction completed with errors", {
          description: `Failed to extract rules from ${response.failed} document(s)`,
        })
      }
    } catch (error) {
      // Add error audit entry and save to database
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
      await saveAuditEntry(errorAuditEntry)

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
              ) : rules.filter(r => r.validation_status === 'validated').length === 0 ? (
                <div className="rounded-lg border bg-card p-6">
                  <h3 className="text-lg font-semibold mb-4">Active Compliance Rules</h3>
                  <p className="text-muted-foreground">
                    No compliance rules found. Click "Generate Updated Rules" to fetch the latest regulatory requirements.
                  </p>
                </div>
              ) : (
                <>
                  {/* Filter Section */}
                  <div className="flex items-center gap-3 w-full">
                    <Select value={filterRuleType} onValueChange={setFilterRuleType}>
                      <SelectTrigger className="h-9 flex-1">
                        <SelectValue placeholder="All types" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Types</SelectItem>
                        {getUniqueRuleTypes().map(type => (
                          <SelectItem key={type} value={type}>{type}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    <Select value={filterJurisdiction} onValueChange={setFilterJurisdiction}>
                      <SelectTrigger className="h-9 flex-1">
                        <SelectValue placeholder="All jurisdictions" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Jurisdictions</SelectItem>
                        {getUniqueJurisdictions().map(jurisdiction => (
                          <SelectItem key={jurisdiction} value={jurisdiction}>{jurisdiction}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    <Select value={filterRegulator} onValueChange={setFilterRegulator}>
                      <SelectTrigger className="h-9 flex-1">
                        <SelectValue placeholder="All regulators" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Regulators</SelectItem>
                        {getUniqueRegulators().map(regulator => (
                          <SelectItem key={regulator} value={regulator}>{regulator}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    {(filterRuleType !== 'all' || filterJurisdiction !== 'all' || filterRegulator !== 'all') && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={clearFilters}
                        className="text-xs h-9 whitespace-nowrap"
                      >
                        Clear Filters
                      </Button>
                    )}
                  </div>

                  {/* Rules List */}
                  <div className="space-y-3">
                    {getFilteredRules().length === 0 ? (
                      <div className="rounded-lg border bg-card p-6 text-center">
                        <p className="text-muted-foreground">No rules match the selected filters.</p>
                      </div>
                    ) : (
                      getFilteredRules().map((rule) => (
                        <div key={rule.id} className="rounded-lg border bg-card p-4">
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <CheckCircle className="h-5 w-5 text-green-500" />
                              <h4 className="font-semibold">{rule.rule_type}</h4>
                              <span className="text-xs bg-green-500/20 text-green-700 dark:text-green-300 px-2 py-1 rounded-md">
                                {rule.jurisdiction}
                              </span>
                            </div>
                          </div>
                          <p className="text-sm text-muted-foreground mb-2">{rule.source_text}</p>
                          <div className="flex gap-2 text-xs text-muted-foreground">
                            <span>Regulator: {rule.regulator}</span>
                            {rule.circular_number && <span>• {rule.circular_number}</span>}
                            {rule.effective_date && <span>• Effective: {new Date(rule.effective_date).toLocaleDateString()}</span>}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </>
              )}
            </TabsContent>

            <TabsContent value="pending" className="space-y-4 min-w-0">
              {isLoadingRules ? (
                <div className="rounded-lg border bg-card p-6">
                  <p className="text-muted-foreground">Loading rules...</p>
                </div>
              ) : rules.filter(r => r.validation_status === 'pending').length === 0 ? (
                <div className="rounded-lg border bg-card p-6">
                  <h3 className="text-lg font-semibold mb-4">Pending Rule Updates</h3>
                  <p className="text-muted-foreground">
                    No pending compliance rule updates at this time.
                  </p>
                </div>
              ) : (
                <>
                  {/* Filter Section */}
                  <div className="flex items-center gap-3 w-full">
                    <Select value={pendingFilterRuleType} onValueChange={setPendingFilterRuleType}>
                      <SelectTrigger className="h-9 flex-1">
                        <SelectValue placeholder="All types" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Types</SelectItem>
                        {getUniquePendingRuleTypes().map(type => (
                          <SelectItem key={type} value={type}>{type}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    <Select value={pendingFilterJurisdiction} onValueChange={setPendingFilterJurisdiction}>
                      <SelectTrigger className="h-9 flex-1">
                        <SelectValue placeholder="All jurisdictions" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Jurisdictions</SelectItem>
                        {getUniquePendingJurisdictions().map(jurisdiction => (
                          <SelectItem key={jurisdiction} value={jurisdiction}>{jurisdiction}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    <Select value={pendingFilterRegulator} onValueChange={setPendingFilterRegulator}>
                      <SelectTrigger className="h-9 flex-1">
                        <SelectValue placeholder="All regulators" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Regulators</SelectItem>
                        {getUniquePendingRegulators().map(regulator => (
                          <SelectItem key={regulator} value={regulator}>{regulator}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    {(pendingFilterRuleType !== 'all' || pendingFilterJurisdiction !== 'all' || pendingFilterRegulator !== 'all') && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={clearPendingFilters}
                        className="text-xs h-9 whitespace-nowrap"
                      >
                        Clear Filters
                      </Button>
                    )}
                  </div>

                  {/* Pending Rules List */}
                  <div className="space-y-3">
                    {getFilteredPendingRules().length === 0 ? (
                      <div className="rounded-lg border bg-card p-6 text-center">
                        <p className="text-muted-foreground">No pending rules match the selected filters.</p>
                      </div>
                    ) : (
                      getFilteredPendingRules().map((rule) => {
                        const isExpanded = expandedPendingRules.has(rule.id)
                        const isApproving = approvingRules.has(rule.id)
                        const preview = rule.source_text.length > 100 ? rule.source_text.substring(0, 100) + '...' : rule.source_text

                        return (
                          <Collapsible
                            key={rule.id}
                            open={isExpanded}
                            onOpenChange={() => togglePendingRule(rule.id)}
                          >
                            <div className="rounded-lg border bg-card hover:border-gray-400 dark:hover:border-gray-600 transition-colors">
                              <div className="w-full p-4">
                                <div className="flex items-start justify-between gap-3">
                                  <div className="flex items-start gap-3 flex-1 min-w-0">
                                    <AlertCircle className="h-5 w-5 text-orange-500 flex-shrink-0 mt-0.5" />
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center gap-2 mb-1">
                                        <h4 className="font-semibold">{rule.rule_type}</h4>
                                        <span className="text-xs bg-orange-500/20 text-orange-700 dark:text-orange-300 px-2 py-1 rounded-md">
                                          {rule.jurisdiction}
                                        </span>
                                      </div>
                                      <CollapsibleTrigger className="w-full text-left">
                                        <p className={`text-sm text-muted-foreground ${isExpanded ? '' : 'truncate'}`}>
                                          {isExpanded ? rule.source_text : preview}
                                        </p>
                                      </CollapsibleTrigger>
                                    </div>
                                  </div>
                                  <CollapsibleTrigger>
                                    <ChevronDown className={`h-5 w-5 text-muted-foreground transition-transform flex-shrink-0 ${isExpanded ? 'rotate-180' : ''}`} />
                                  </CollapsibleTrigger>
                                </div>
                              </div>

                            <CollapsibleContent>
                              <div className="px-4 pb-4 space-y-4 border-t pt-4">

                                <div className="grid grid-cols-2 gap-4 text-sm">
                                  <div>
                                    <span className="text-muted-foreground">Regulator:</span>
                                    <p className="font-medium">{rule.regulator}</p>
                                  </div>
                                  {rule.circular_number && (
                                    <div>
                                      <span className="text-muted-foreground">Circular Number:</span>
                                      <p className="font-medium">{rule.circular_number}</p>
                                    </div>
                                  )}
                                  {rule.effective_date && (
                                    <div>
                                      <span className="text-muted-foreground">Effective Date:</span>
                                      <p className="font-medium">{new Date(rule.effective_date).toLocaleDateString()}</p>
                                    </div>
                                  )}
                                </div>

                                <div className="flex gap-2 pt-2">
                                  <Button
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      handleApproveRule(rule)
                                    }}
                                    disabled={isApproving}
                                    className="gap-2"
                                    size="sm"
                                  >
                                    {isApproving ? (
                                      <>
                                        <RefreshCw className="h-4 w-4 animate-spin" />
                                        Approving...
                                      </>
                                    ) : (
                                      <>
                                        <Check className="h-4 w-4" />
                                        Approve Rule
                                      </>
                                    )}
                                  </Button>
                                </div>
                              </div>
                            </CollapsibleContent>
                          </div>
                        </Collapsible>
                        )
                      })
                    )}
                  </div>
                </>
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
