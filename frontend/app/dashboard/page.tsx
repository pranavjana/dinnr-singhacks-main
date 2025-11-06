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
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useState, useEffect } from "react"
import { ChevronDown, ChevronUp, Trash2, Check, Search, Calendar, X, ClipboardCheck } from "lucide-react"
import { api } from "@/lib/api"
import { toast } from "sonner"

interface Verdict {
  payment_id?: string
  trace_id?: string
  verdict: 'pass' | 'suspicious' | 'fail'
  assigned_team: string
  risk_score: number
  rule_score?: number
  pattern_score?: number
  llm_risk_score?: number
  justification?: string
  triggered_rules?: any[]
  detected_patterns?: any[]
  llm_flagged_transactions?: any[]
  llm_patterns?: any[]
  narrative_summary?: string
  rule_references?: string[]
  notable_transactions?: any[]
  recommended_actions?: string[]
  manual_override?: 'pass_with_review'
  override_notes?: string
}

interface TriageResult {
  screening_result: any
  triage_plan: string
}

interface Transaction {
  id?: string
  amount?: number
  currency?: string
  merchant?: string
  category?: string
  timestamp?: string
  status?: string
  verdict?: Verdict
  triage?: TriageResult
  isAnalyzing?: boolean
  isTriaging?: boolean
  user_action?: string
  user_action_timestamp?: string
  user_action_by?: string
  [key: string]: any
}

const extractSenderNames = (records: unknown): string[] => {
  if (!Array.isArray(records)) {
    return []
  }
  return records
    .map((item) => {
      if (item && typeof item === "object" && "originator_name" in item) {
        const name = (item as { originator_name?: unknown }).originator_name
        return typeof name === "string" ? name : null
      }
      return null
    })
    .filter((name): name is string => Boolean(name))
}

export default function Page() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [expandedCards, setExpandedCards] = useState<Set<number>>(new Set())
  const [showAllFields, setShowAllFields] = useState<Set<number>>(new Set())
  const [overrideReasons, setOverrideReasons] = useState<Record<string, string>>({})
  const [showOverrideReason, setShowOverrideReason] = useState<Record<string, boolean>>({})

  // Filter states
  const [dateRange, setDateRange] = useState("all")
  const [statusFilter, setStatusFilter] = useState("all")
  const [typeFilter, setTypeFilter] = useState("all")
  const [searchQuery, setSearchQuery] = useState("")

  // Sorting states
  const [sortColumn, setSortColumn] = useState<'amount' | 'risk_score' | 'status' | 'date' | null>(null)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')

  // Load existing transactions on mount
  useEffect(() => {
    loadExistingTransactions()
  }, [])

  const loadExistingTransactions = async () => {
    try {
      const response = await api.getTransactions(50)

      // Handle both old and new API response formats
      const transactionsArray = Array.isArray(response) ? response : (response as any).transactions || []

      // Convert database transactions to Transaction format
      const dbTransactions: Transaction[] = transactionsArray.map((txn: any) => ({
        ...txn.transaction_data,
        id: txn.id,
        verdict: txn.verdict,
        triage: txn.triage,
        isAnalyzing: txn.is_analyzing,
        isTriaging: txn.is_triaging,
        user_action: txn.user_action,
        user_action_timestamp: txn.user_action_timestamp,
        user_action_by: txn.user_action_by,
      }))

      setTransactions(dbTransactions)
    } catch (error) {
      console.error('Failed to load transactions:', error)
      // Don't show error to user, just start with empty list
    }
  }

  const saveTransactionToDb = async (transaction: Transaction) => {
    try {
      await api.saveTransaction({
        payment_id: transaction.payment_id,
        trace_id: transaction.trace_id,
        amount: transaction.amount,
        currency: transaction.currency,
        originator_name: transaction.originator_name,
        beneficiary_name: transaction.beneficiary_name,
        merchant: transaction.merchant,
        category: transaction.category,
        product_type: transaction.product_type,
        booking_datetime: transaction.booking_datetime,
        transaction_data: transaction,
        verdict: transaction.verdict,
        triage: transaction.triage,
        is_analyzing: transaction.isAnalyzing || false,
        is_triaging: transaction.isTriaging || false,
      })
    } catch (error) {
      console.error('Failed to save transaction:', error)
    }
  }

  const updateTransactionInDb = async (transactionId: string, updates: any) => {
    try {
      await api.updateTransaction(transactionId, updates)
    } catch (error) {
      console.error('Failed to update transaction:', error)
    }
  }

  const handleDeleteTransaction = async (transactionId: string, index: number) => {
    try {
      // Validate transaction ID
      if (!transactionId || transactionId === 'undefined') {
        toast.error("Cannot delete transaction", {
          description: "Transaction has no valid ID",
        })
        return
      }

      // Delete from database
      await api.deleteTransaction(transactionId)

      // Remove from local state
      setTransactions(prev => prev.filter((_, idx) => idx !== index))

      toast.success("Transaction deleted", {
        description: "Transaction has been removed successfully",
      })
    } catch (error) {
      console.error('Failed to delete transaction:', error)
      toast.error("Error deleting transaction", {
        description: error instanceof Error ? error.message : "Failed to delete transaction",
      })
    }
  }

  const handleActionClick = async (transactionId: string, index: number, action: string) => {
    try {
      // Update database with user action
      await updateTransactionInDb(transactionId, {
        user_action: action,
        user_action_timestamp: new Date().toISOString(),
        user_action_by: 'current_user', // Replace with actual user ID when auth is implemented
      })

      // Update local state
      setTransactions(prev =>
        prev.map((txn, idx) =>
          idx === index
            ? {
                ...txn,
                user_action: action,
                user_action_timestamp: new Date().toISOString(),
                user_action_by: 'current_user',
              }
            : txn
        )
      )

      toast.success("Action recorded", {
        description: `Action "${action.replace('action_', '').replace(/_/g, ' ')}" has been saved`,
      })
    } catch (error) {
      console.error('Failed to save action:', error)
      toast.error("Error saving action", {
        description: error instanceof Error ? error.message : "Failed to save action",
      })
    }
  }

  const getOverrideKey = (transactionId: string | undefined, index: number) =>
    transactionId ?? `index-${index}`

  const handleManualOverride = async (
    transactionId: string | undefined,
    index: number,
    reason: string
  ) => {
    if (!transactionId || transactionId === 'undefined') {
      toast.error("Cannot update transaction", {
        description: "Transaction has no valid ID",
      })
      return
    }

    const transaction = transactions[index]
    if (!transaction) {
      return
    }

    const nowIso = new Date().toISOString()
    const trimmedReason = reason.trim()
    if (!trimmedReason) {
      toast.error("Reason required", {
        description: "Please provide a reason for passing this transaction with review.",
      })
      return
    }

    const overrideNote = `Manually marked as pass with review on ${new Date().toLocaleString()}. Reason: ${trimmedReason}`

    const updatedVerdict: Verdict = {
      assigned_team: transaction.verdict?.assigned_team ?? 'Manual Review Team',
      risk_score: transaction.verdict?.risk_score ?? 0,
      ...(transaction.verdict ?? {}),
      verdict: 'pass',
      manual_override: 'pass_with_review',
      override_notes: overrideNote,
    }

    const updatedTriage: TriageResult | undefined = transaction.triage
      ? {
          ...transaction.triage,
          screening_result: {
            ...(transaction.triage?.screening_result ?? {}),
            decision: 'pass_with_review',
            override_notes: overrideNote,
          },
        }
      : {
          screening_result: {
            decision: 'pass_with_review',
            override_notes: overrideNote,
          },
          triage_plan: '',
        }

    const userAction = 'pass_with_review'

    try {
      await updateTransactionInDb(transactionId, {
        verdict: updatedVerdict,
        triage: updatedTriage,
        user_action: userAction,
        user_action_timestamp: nowIso,
        user_action_by: 'current_user',
      })

      setTransactions(prev =>
        prev.map((txn, idx) =>
          idx === index
            ? {
                ...txn,
                verdict: updatedVerdict,
                triage: updatedTriage,
                user_action: userAction,
                user_action_timestamp: nowIso,
                user_action_by: 'current_user',
              }
            : txn
        )
      )

      const overrideKey = getOverrideKey(transactionId, index)
      setOverrideReasons(prev => ({
        ...prev,
        [overrideKey]: '',
      }))
      setShowOverrideReason(prev => ({
        ...prev,
        [overrideKey]: false,
      }))

      toast.success("Transaction updated", {
        description: "Marked as pass with review.",
      })
    } catch (error) {
      console.error('Failed to override verdict:', error)
      toast.error("Error updating transaction", {
        description: error instanceof Error ? error.message : "Failed to update transaction",
      })
    }
  }

  const handlePassWithReviewClick = (transactionId: string | undefined, index: number) => {
    const overrideKey = getOverrideKey(transactionId, index)
    const isOpen = showOverrideReason[overrideKey] ?? false
    if (!isOpen) {
      setShowOverrideReason(prev => ({
        ...prev,
        [overrideKey]: true,
      }))
      return
    }

    const reason = overrideReasons[overrideKey] ?? ''
    handleManualOverride(transactionId, index, reason)
  }

  const loadTransaction = async () => {
    setIsLoading(true)
    try {
      // Fetch 5 random transactions from CSV
      const response = await fetch('/api/v1/payments/sample')
      if (!response.ok) {
        throw new Error('Failed to fetch transactions')
      }
      const fetchedTransactions = await response.json()

      // Add transactions with analyzing state and save to DB
      const transactionsWithState = fetchedTransactions.map((txn: any) => ({
        ...txn,
        isAnalyzing: true,
      }))

      // Add to the list immediately
      setTransactions(prev => [...transactionsWithState, ...prev])

      // Save each new transaction to database
      const savedTransactions = await Promise.all(
        transactionsWithState.map(async (txn: any) => {
          const response = await api.saveTransaction({
            payment_id: txn.payment_id,
            trace_id: txn.trace_id,
            amount: parseFloat(txn.amount || 0),
            currency: txn.currency || 'SGD',
            originator_name: txn.originator_name,
            beneficiary_name: txn.beneficiary_name,
            merchant: txn.merchant,
            category: txn.category,
            product_type: txn.product_type,
            booking_datetime: txn.booking_datetime,
            transaction_data: txn,
            is_analyzing: true,
          }) as any
          return { ...txn, id: response.transaction.id }
        })
      )

      // Update transactions with database IDs
      setTransactions(prev => prev.map((txn, idx) =>
        idx < savedTransactions.length ? savedTransactions[idx] : txn
      ))

      // Analyze each transaction
      for (let i = 0; i < savedTransactions.length; i++) {
        try {
          const analyzeResponse = await fetch('/api/v1/payments/analyze', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(fetchedTransactions[i]),
          })

          if (analyzeResponse.ok) {
            const verdict = await analyzeResponse.json()

            // Update the specific transaction with verdict and mark as triaging
            setTransactions(prev =>
              prev.map((txn, idx) =>
                idx === i
                  ? { ...txn, verdict, isAnalyzing: false, isTriaging: true }
                  : txn
              )
            )

            // Update transaction in database
            if (savedTransactions[i].id) {
              await updateTransactionInDb(savedTransactions[i].id, {
                verdict,
                is_analyzing: false,
                is_triaging: true,
              })
            }

            // Call triage endpoint
            try {
              const triageResponse = await fetch('/api/v1/payments/triage', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                  payment: fetchedTransactions[i],
                  analysis: verdict,
                }),
              })

              if (triageResponse.ok) {
                const triageResult = await triageResponse.json()

                // Update with triage result
                setTransactions(prev =>
                  prev.map((txn, idx) =>
                    idx === i
                      ? { ...txn, triage: triageResult, isTriaging: false }
                      : txn
                  )
                )

                // Update transaction in database
                if (savedTransactions[i].id) {
                  await updateTransactionInDb(savedTransactions[i].id, {
                    triage: triageResult,
                    is_triaging: false,
                  })
                }
              } else {
                // Mark triage as failed
                setTransactions(prev =>
                  prev.map((txn, idx) =>
                    idx === i
                      ? { ...txn, isTriaging: false }
                      : txn
                  )
                )

                // Update transaction in database
                if (savedTransactions[i].id) {
                  await updateTransactionInDb(savedTransactions[i].id, {
                    is_triaging: false,
                  })
                }
              }
            } catch (error) {
              console.error(`Error triaging transaction ${i}:`, error)
              setTransactions(prev =>
                prev.map((txn, idx) =>
                  idx === i
                    ? { ...txn, isTriaging: false }
                    : txn
                )
              )

              // Update transaction in database
              if (savedTransactions[i].id) {
                await updateTransactionInDb(savedTransactions[i].id, {
                  is_triaging: false,
                })
              }
            }
          } else {
            // Mark as failed analysis
            setTransactions(prev =>
              prev.map((txn, idx) =>
                idx === i
                  ? { ...txn, isAnalyzing: false }
                  : txn
              )
            )

            // Update transaction in database
            if (savedTransactions[i].id) {
              await updateTransactionInDb(savedTransactions[i].id, {
                is_analyzing: false,
              })
            }
          }
        } catch (error) {
          console.error(`Error analyzing transaction ${i}:`, error)
          // Mark as failed analysis
          setTransactions(prev =>
            prev.map((txn, idx) =>
              idx === i
                ? { ...txn, isAnalyzing: false }
                : txn
            )
          )

          // Update transaction in database
          if (savedTransactions[i].id) {
            await updateTransactionInDb(savedTransactions[i].id, {
              is_analyzing: false,
            })
          }
        }
      }
    } catch (error) {
      console.error('Error loading transactions:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const toggleCard = (index: number) => {
    setExpandedCards(prev => {
      const newSet = new Set(prev)
      if (newSet.has(index)) {
        newSet.delete(index)
      } else {
        newSet.add(index)
      }
      return newSet
    })
  }

  const toggleAllFields = (index: number) => {
    setShowAllFields(prev => {
      const newSet = new Set(prev)
      if (newSet.has(index)) {
        newSet.delete(index)
      } else {
        newSet.add(index)
      }
      return newSet
    })
  }

  const getRiskColor = (verdict?: string) => {
    switch (verdict) {
      case 'fail':
        return 'border-red-500 bg-red-50 dark:bg-red-950'
      case 'suspicious':
        return 'border-orange-500 bg-orange-50 dark:bg-orange-950'
      case 'pass':
        return 'border-green-500 bg-green-50 dark:bg-green-950'
      default:
        return 'border-gray-300'
    }
  }

  const getRiskBadgeColor = (verdict?: string) => {
    switch (verdict) {
      case 'fail':
        return 'bg-red-500 text-white'
      case 'suspicious':
        return 'bg-orange-500 text-white'
      case 'pass':
        return 'bg-green-500 text-white'
      default:
        return 'bg-gray-500 text-white'
    }
  }

  // Filter transactions based on current filters
  const filteredTransactions = transactions.filter(transaction => {
    // Date range filter
    if (dateRange !== "all" && transaction.booking_datetime) {
      const txnDate = new Date(transaction.booking_datetime)
      const now = new Date()
      const daysDiff = Math.floor((now.getTime() - txnDate.getTime()) / (1000 * 60 * 60 * 24))

      if (dateRange === "7days" && daysDiff > 7) return false
      if (dateRange === "30days" && daysDiff > 30) return false
      if (dateRange === "90days" && daysDiff > 90) return false
    }

    // Status filter (based on verdict)
    if (statusFilter !== "all") {
      const verdict = transaction.verdict?.verdict?.toLowerCase()
      if (statusFilter === "analyzing" && !transaction.isAnalyzing) return false
      if (statusFilter === "pass" && verdict !== "pass") return false
      if (statusFilter === "suspicious" && verdict !== "suspicious") return false
      if (statusFilter === "fail" && verdict !== "fail") return false
    }

    // Type filter
    if (typeFilter !== "all") {
      const category = transaction.category?.toLowerCase() || ""
      const productType = transaction.product_type?.toLowerCase() || ""
      if (!category.includes(typeFilter.toLowerCase()) && !productType.includes(typeFilter.toLowerCase())) {
        return false
      }
    }

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      const notableSenders = extractSenderNames(transaction.verdict?.notable_transactions)
      const flaggedSenders = extractSenderNames(transaction.verdict?.llm_flagged_transactions)
      const senderCandidates = [
        transaction.originator_name,
        transaction.merchant,
        ...notableSenders,
        ...flaggedSenders,
      ].filter((name): name is string => Boolean(name))

      if (!senderCandidates.some((name) => name.toLowerCase().includes(query))) {
        return false
      }
    }

    return true
  })

  const clearFilters = () => {
    setDateRange("all")
    setStatusFilter("all")
    setTypeFilter("all")
    setSearchQuery("")
  }

  // Handle sorting
  const handleSort = (column: 'amount' | 'risk_score' | 'status' | 'date') => {
    if (sortColumn === column) {
      // Toggle direction if clicking same column
      setSortDirection(sortDirection === 'desc' ? 'asc' : 'desc')
    } else {
      // Set new column and default to descending
      setSortColumn(column)
      setSortDirection('desc')
    }
  }

  // Apply sorting to filtered transactions
  const sortedTransactions = [...filteredTransactions].sort((a, b) => {
    if (!sortColumn) return 0

    let aValue: any
    let bValue: any

    switch (sortColumn) {
      case 'amount':
        aValue = typeof a.amount === 'number' ? a.amount : parseFloat(a.amount || '0')
        bValue = typeof b.amount === 'number' ? b.amount : parseFloat(b.amount || '0')
        break
      case 'risk_score':
        aValue = a.verdict?.risk_score ?? -1
        bValue = b.verdict?.risk_score ?? -1
        break
      case 'status':
        // Sort by verdict: fail > suspicious > pass
        const statusOrder: Record<string, number> = { fail: 3, suspicious: 2, pass: 1 }
        aValue = statusOrder[a.verdict?.verdict?.toLowerCase() || ''] ?? 0
        bValue = statusOrder[b.verdict?.verdict?.toLowerCase() || ''] ?? 0
        break
      case 'date':
        aValue = a.booking_datetime ? new Date(a.booking_datetime).getTime() : 0
        bValue = b.booking_datetime ? new Date(b.booking_datetime).getTime() : 0
        break
    }

    if (sortDirection === 'desc') {
      return bValue - aValue
    } else {
      return aValue - bValue
    }
  })

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="flex flex-col h-screen overflow-hidden">
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
                  <BreadcrumbLink href="#">
                    Dashboard
                  </BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden md:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage>Incoming Transactions</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>
        <div className="flex flex-1 flex-col p-4 pt-0 overflow-hidden">
          <div className="flex items-center justify-between mb-4 flex-shrink-0">
            <h2 className="text-2xl font-bold tracking-tight">Transaction Monitor</h2>
            <Button onClick={loadTransaction} disabled={isLoading}>
              {isLoading ? "Loading..." : "Load Transaction"}
            </Button>
          </div>

          <Separator className="mb-4" />

          {/* Content Container - consistent width for filters and list */}
          <div className="flex flex-col flex-1 min-h-0 w-full">
            {/* Filter Bar */}
            <div className="mb-2 flex-shrink-0 w-full">
              <div className="flex items-center gap-3 flex-wrap">
                {/* Date Range Selector */}
              <Select value={dateRange} onValueChange={setDateRange}>
                <SelectTrigger className="w-[180px]">
                  <Calendar className="h-4 w-4 mr-2" />
                  <SelectValue placeholder="Date range" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Time</SelectItem>
                  <SelectItem value="7days">Last 7 days</SelectItem>
                  <SelectItem value="30days">Last 30 days</SelectItem>
                  <SelectItem value="90days">Last 90 days</SelectItem>
                </SelectContent>
              </Select>

              {/* Status Filter */}
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">
                    <span className="flex items-center gap-2">
                      All <Badge variant="secondary" className="ml-auto">{transactions.length}</Badge>
                    </span>
                  </SelectItem>
                  <SelectItem value="analyzing">Analyzing</SelectItem>
                  <SelectItem value="pass">Pass</SelectItem>
                  <SelectItem value="suspicious">Suspicious</SelectItem>
                  <SelectItem value="fail">Fail</SelectItem>
                </SelectContent>
              </Select>

              {/* Type Filter */}
              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="wire_transfer">Wire Transfer</SelectItem>
                  <SelectItem value="securities_trade">Securities Trade</SelectItem>
                  <SelectItem value="cash_withdrawal">Cash Withdrawal</SelectItem>
                  <SelectItem value="cash_deposit">Cash Deposit</SelectItem>
                  <SelectItem value="fx_conversion">FX Conversion</SelectItem>
                  <SelectItem value="fund_subscription">Fund Subscription</SelectItem>
                </SelectContent>
              </Select>

              {/* Clear Filters Button */}
              {(dateRange !== "all" || statusFilter !== "all" || typeFilter !== "all" || searchQuery !== "") && (
                <Button variant="ghost" size="sm" onClick={clearFilters} className="gap-2">
                  <X className="h-4 w-4" />
                  Clear Filters
                </Button>
              )}

              {/* Results Count */}
              <div className="text-sm text-muted-foreground">
                Showing {filteredTransactions.length} of {transactions.length} transactions
              </div>

              {/* Search - Right aligned */}
              <div className="relative ml-auto">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search by sender name"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 w-[350px]"
                />
                </div>
              </div>
            </div>

            {/* Recent Transactions - Full Width */}
            <div className="flex flex-col flex-1 min-h-0 w-full overflow-y-auto rounded-lg border mt-3">
                {transactions.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">
                    No transactions yet. Click "Load Transaction" to fetch sample transactions.
                  </p>
                ) : filteredTransactions.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">
                    No transactions match your filters. Try adjusting your search criteria.
                  </p>
                ) : (
                  <div className="flex flex-col">
                    {/* Column Headers */}
                    <div className="sticky top-0 z-10 flex items-center px-4 py-3 text-xs font-semibold text-muted-foreground border-b backdrop-blur-[11.9px] bg-muted/90">
                      <div className="flex-[1.5]">ORIGINATOR</div>
                      <div className="flex-[1.2]">PAYMENT METHOD</div>
                      <div
                        className="flex-[1.2] flex items-center gap-1 cursor-pointer hover:text-foreground transition-colors"
                        onClick={() => handleSort('amount')}
                      >
                        AMOUNT
                        {sortColumn === 'amount' && (
                          sortDirection === 'desc' ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />
                        )}
                      </div>
                      <div
                        className="flex-1 flex items-center gap-1 cursor-pointer hover:text-foreground transition-colors"
                        onClick={() => handleSort('status')}
                      >
                        STATUS
                        {sortColumn === 'status' && (
                          sortDirection === 'desc' ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />
                        )}
                      </div>
                      <div
                        className="flex-1 flex items-center gap-1 cursor-pointer hover:text-foreground transition-colors"
                        onClick={() => handleSort('risk_score')}
                      >
                        <span className="-ml-[0.875rem]">RISK SCORE</span>
                        {sortColumn === 'risk_score' && (
                          sortDirection === 'desc' ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />
                        )}
                      </div>
                      <div className="flex-[1.5]">ACTIONS TAKEN</div>
                      <div
                        className="flex-[1.3] flex items-center gap-1 cursor-pointer hover:text-foreground transition-colors"
                        onClick={() => handleSort('date')}
                      >
                        DATE
                        {sortColumn === 'date' && (
                          sortDirection === 'desc' ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />
                        )}
                      </div>
                      <div className="w-8"></div>
                    </div>

                    {sortedTransactions.map((transaction, index) => {
                      const isExpanded = expandedCards.has(index)
                      const showAll = showAllFields.has(index)

                      return (
                        <div key={index} className="group border-b last:border-b-0">
                          {/* Compact Transaction Row */}
                          <div
                            className="flex items-center px-4 py-3 cursor-pointer transition-all hover:bg-muted/30"
                            onClick={() => toggleCard(index)}
                          >
                            {/* ORIGINATOR */}
                            <div className="flex-[1.5]">
                              <span className="text-sm truncate block">
                                {transaction.originator_name || transaction.merchant || 'Unknown'}
                              </span>
                            </div>

                            {/* PAYMENT METHOD */}
                            <div className="flex-[1.2]">
                              <span className="text-sm">
                                {transaction.product_type?.replace(/_/g, ' ') || 'N/A'}
                              </span>
                            </div>

                            {/* AMOUNT */}
                            <div className="flex-[1.2]">
                              <div className="font-semibold text-sm">
                                {typeof transaction.amount === 'number' ? transaction.amount.toLocaleString() : parseFloat(transaction.amount || '0').toLocaleString()} {transaction.currency || 'SGD'}
                              </div>
                            </div>

                            {/* STATUS */}
                            <div className="flex-1">
                              {transaction.isAnalyzing && (
                                <Badge variant="secondary" className="bg-blue-500/20 text-blue-700 dark:text-blue-300">
                                  Analyzing
                                </Badge>
                              )}
                              {transaction.isTriaging && (
                                <Badge variant="secondary" className="bg-purple-500/20 text-purple-700 dark:text-purple-300">
                                  Triaging
                                </Badge>
                              )}
                              {transaction.verdict?.verdict && !transaction.isAnalyzing && !transaction.isTriaging && (
                                <Badge className={
                                  transaction.verdict.verdict === 'fail' ? 'bg-red-500/20 text-red-700 dark:text-red-300 hover:bg-red-500/30' :
                                  transaction.verdict.verdict === 'suspicious' ? 'bg-orange-500/20 text-orange-700 dark:text-orange-300 hover:bg-orange-500/30' :
                                  transaction.verdict.verdict === 'pass' ? 'bg-green-500/20 text-green-700 dark:text-green-300 hover:bg-green-500/30' :
                                  'bg-gray-500/20 text-gray-700 dark:text-gray-300 hover:bg-gray-500/30'
                                }>
                                  {transaction.verdict.verdict}
                                </Badge>
                              )}
                            </div>

                            {/* ACTIVITY - Risk Score Circle */}
                            <div className="flex-1 flex items-center pl-2">
                              {transaction.verdict?.risk_score !== undefined ? (
                                <div className="relative flex items-center justify-center shrink-0">
                                  {/* Background circle */}
                                  <svg className="w-9 h-9 -rotate-90">
                                    <circle
                                      cx="18"
                                      cy="18"
                                      r="14"
                                      fill="none"
                                      stroke="hsl(var(--muted))"
                                      strokeWidth="2.5"
                                      opacity="0.3"
                                    />
                                    {/* Progress circle */}
                                    <circle
                                      cx="18"
                                      cy="18"
                                      r="14"
                                      fill="none"
                                      stroke={
                                        transaction.verdict.risk_score >= 70 ? '#dc2626' :
                                        transaction.verdict.risk_score >= 40 ? '#fb923c' :
                                        '#22c55e'
                                      }
                                      strokeWidth="2.5"
                                      strokeLinecap="round"
                                      style={{
                                        strokeDasharray: `${2 * Math.PI * 14}`,
                                        strokeDashoffset: `${2 * Math.PI * 14 * (1 - transaction.verdict.risk_score / 100)}`,
                                      }}
                                    />
                                  </svg>
                                  {/* Score text */}
                                  <span className="absolute text-xs font-semibold">
                                    {Math.round(transaction.verdict.risk_score)}
                                  </span>
                                </div>
                              ) : (
                                <span className="text-sm text-muted-foreground">N/A</span>
                              )}
                            </div>

                            {/* ACTIONS TAKEN */}
                            <div className="flex-[1.5]">
                              {transaction.user_action ? (
                                <Badge variant="outline" className="bg-green-50 dark:bg-green-950 border-green-300 dark:border-green-700 text-green-800 dark:text-green-200 text-xs">
                                  {transaction.user_action.replace('action_', '').replace(/_/g, ' ')}
                                </Badge>
                              ) : (
                                <span className="text-xs text-muted-foreground italic">No action taken</span>
                              )}
                            </div>

                            {/* DATE */}
                            <div className="flex-[1.3]">
                              <span className="text-sm text-muted-foreground">
                                {transaction.booking_datetime
                                  ? new Date(transaction.booking_datetime).toLocaleDateString('en-US', {
                                      month: 'short',
                                      day: 'numeric',
                                      year: 'numeric',
                                      hour: 'numeric',
                                      minute: '2-digit',
                                      hour12: true
                                    })
                                  : 'N/A'}
                              </span>
                            </div>

                            {/* Expand Indicator */}
                            <div className="w-8 flex justify-end shrink-0">
                              <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                            </div>
                          </div>

                          {/* Expanded Details */}
                          {isExpanded && (
                            <div className="bg-gradient-to-b from-muted/30 to-muted/10 border-t" onClick={(e) => e.stopPropagation()}>
                              <div className="p-6 space-y-6 max-w-7xl mx-auto">
                                {/* Header Section with Key Info */}
                                <div className="grid grid-cols-3 gap-4">
                                  <div className="bg-background rounded-lg p-4 border shadow-sm">
                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Transaction Type</div>
                                    <div className="text-base font-semibold">
                                      {transaction.product_type?.replace(/_/g, ' ') || transaction.category || 'N/A'}
                                    </div>
                                  </div>
                                  <div className="bg-background rounded-lg p-4 border shadow-sm">
                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Beneficiary</div>
                                    <div className="text-base font-semibold truncate">
                                      {transaction.beneficiary_name || 'N/A'}
                                    </div>
                                  </div>
                                  <div className="bg-background rounded-lg p-4 border shadow-sm">
                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Payment ID</div>
                                    <div className="text-base font-mono text-sm truncate">
                                      {transaction.payment_id || 'N/A'}
                                    </div>
                                  </div>
                                </div>

                                {/* Risk Analysis Section */}
                                {transaction.verdict && (
                                  <div className="bg-background rounded-lg border shadow-sm overflow-hidden">
                                    <div className="px-5 py-4 border-b bg-muted/50">
                                      <h4 className="text-sm font-semibold uppercase tracking-wide">Risk Analysis</h4>
                                    </div>
                                    <div className="p-5 space-y-5">
                                      {/* Risk Score Visualization */}
                                      <div className="flex items-center gap-6">
                                        <div className="relative flex items-center justify-center shrink-0">
                                          <svg className="w-24 h-24 -rotate-90">
                                            <circle
                                              cx="48"
                                              cy="48"
                                              r="40"
                                              fill="none"
                                              stroke="hsl(var(--muted))"
                                              strokeWidth="6"
                                              opacity="0.2"
                                            />
                                            <circle
                                              cx="48"
                                              cy="48"
                                              r="40"
                                              fill="none"
                                              stroke={
                                                transaction.verdict.risk_score >= 70 ? '#dc2626' :
                                                transaction.verdict.risk_score >= 40 ? '#fb923c' :
                                                '#22c55e'
                                              }
                                              strokeWidth="6"
                                              strokeLinecap="round"
                                              style={{
                                                strokeDasharray: `${2 * Math.PI * 40}`,
                                                strokeDashoffset: `${2 * Math.PI * 40 * (1 - transaction.verdict.risk_score / 100)}`,
                                              }}
                                            />
                                          </svg>
                                          <div className="absolute text-center">
                                            <div className="text-2xl font-bold">
                                              {Math.round(transaction.verdict.risk_score)}
                                            </div>
                                          </div>
                                        </div>

                                        <div className="flex-1 grid grid-cols-3 gap-4">
                                          <div className="space-y-1">
                                            <div className="text-xs text-muted-foreground uppercase tracking-wider">Verdict</div>
                                            <Badge className={
                                              transaction.verdict.verdict === 'fail' ? 'bg-red-500 hover:bg-red-600 text-white' :
                                              transaction.verdict.verdict === 'suspicious' ? 'bg-orange-500 hover:bg-orange-600 text-white' :
                                              'bg-green-500 hover:bg-green-600 text-white'
                                            }>
                                              {transaction.verdict.verdict.toUpperCase()}
                                            </Badge>
                                          </div>
                                          <div className="space-y-1">
                                            <div className="text-xs text-muted-foreground uppercase tracking-wider">Assigned Team</div>
                                            <div className="px-3 py-2 bg-muted/50 border rounded-md">
                                              <div className="text-sm font-semibold">{transaction.verdict.assigned_team}</div>
                                            </div>
                                          </div>
                                          {transaction.verdict.rule_score !== undefined && (
                                            <div className="space-y-1">
                                              <div className="text-xs text-muted-foreground uppercase tracking-wider">Rule Score</div>
                                              <div className="text-sm font-medium">{transaction.verdict.rule_score.toFixed(2)}</div>
                                            </div>
                                          )}
                                        </div>
                                      </div>

                                      {/* Justification */}
                                      {transaction.verdict.justification && (
                                        <div className="p-4 bg-muted/30 rounded-lg border">
                                          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Justification</div>
                                          <p className="text-sm leading-relaxed">{transaction.verdict.justification}</p>
                                        </div>
                                      )}

                                      {/* Detected Patterns */}
                                      {transaction.verdict.triggered_rules && transaction.verdict.triggered_rules.length > 0 && (
                                        <div>
                                          <div className="text-xs font-semibold text-foreground uppercase tracking-wider mb-3">
                                            Detected Patterns ({transaction.verdict.triggered_rules.length})
                                          </div>
                                          <div className="space-y-3">
                                            {transaction.verdict.triggered_rules.map((rule: any, i) => (
                                              <div key={i} className="p-4 bg-background border rounded-lg hover:border-foreground/20 transition-colors">
                                                <div className="flex items-start justify-between gap-4">
                                                  <div className="flex-1 space-y-2">
                                                    <div className="flex items-center gap-2">
                                                      <div className="w-1.5 h-1.5 rounded-full bg-foreground/40"></div>
                                                      <div className="font-semibold text-sm text-foreground">
                                                        {rule.pattern_type || rule.rule_name || rule.name || `Pattern ${i + 1}`}
                                                      </div>
                                                    </div>
                                                    {rule.description && (
                                                      <div className="text-sm text-muted-foreground leading-relaxed pl-3.5">
                                                        {rule.description}
                                                      </div>
                                                    )}
                                                  </div>
                                                  {rule.severity && (
                                                    <Badge className={`text-xs font-medium shrink-0 ${
                                                      rule.severity.toLowerCase() === 'critical' || rule.severity.toLowerCase() === 'high'
                                                        ? 'bg-red-500/20 text-red-700 dark:text-red-300 hover:bg-red-500/30'
                                                        : rule.severity.toLowerCase() === 'medium'
                                                        ? 'bg-orange-500/20 text-orange-700 dark:text-orange-300 hover:bg-orange-500/30'
                                                        : 'bg-green-500/20 text-green-700 dark:text-green-300 hover:bg-green-500/30'
                                                    }`}>
                                                      {rule.severity}
                                                    </Badge>
                                                  )}
                                                </div>
                                              </div>
                                            ))}
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}

                                {/* AML Triage Section */}
                                {transaction.triage && (
                                  <div className={`rounded-lg border shadow-sm overflow-hidden transition-colors ${
                                    transaction.user_action
                                      ? 'bg-green-100/60 dark:bg-green-950/30 border-green-300 dark:border-green-800'
                                      : 'bg-background'
                                  }`}>
                                    <div className={`px-5 py-4 border-b ${
                                      transaction.user_action
                                        ? 'border-green-300 dark:border-green-800'
                                        : ''
                                    }`}>
                                      <div className="flex items-center justify-between">
                                        <h4 className={`text-sm font-semibold uppercase tracking-wide ${
                                          transaction.user_action
                                            ? 'text-green-800 dark:text-green-100'
                                            : ''
                                        }`}>
                                          Recommended Actions
                                        </h4>
                                        <div className="flex items-center gap-2">
                                          {transaction.user_action && (
                                            <Badge className="bg-green-500/20 text-green-700 dark:text-green-300 hover:bg-green-500/30 border-transparent">
                                              Action Taken
                                            </Badge>
                                          )}
                                          <Badge variant="outline" className="bg-muted/50 border-muted-foreground/20 text-foreground text-xs font-medium">
                                            {transaction.triage.screening_result.decision}
                                          </Badge>
                                        </div>
                                      </div>
                                    </div>
                                    <div className="p-5">
                                      <div className="flex flex-wrap gap-2.5">
                                        {transaction.triage.screening_result.action_ids && transaction.triage.screening_result.action_ids.length > 0 ? (
                                          transaction.triage.screening_result.action_ids.map((action: string, i: number) => {
                                            const isSelected = transaction.user_action === action
                                            return (
                                              <Button
                                                key={i}
                                                variant="outline"
                                                size="sm"
                                                onClick={() => transaction.id && handleActionClick(transaction.id, index, action)}
                                                disabled={!transaction.id}
                                                className={`text-xs font-medium transition-all duration-200 gap-1.5 ${
                                                  isSelected
                                                    ? 'bg-green-500/20 text-green-700 dark:text-green-300 border-transparent hover:bg-green-500/30'
                                                    : 'bg-background hover:bg-muted/50 border-muted-foreground/30 hover:border-foreground/50'
                                                }`}
                                              >
                                                {isSelected && (
                                                  <Check className="h-3 w-3" />
                                                )}
                                                {action.replace('action_', '').replace(/_/g, ' ')}
                                              </Button>
                                            )
                                          })
                                        ) : (
                                          <span className="text-sm text-muted-foreground italic">No actions required</span>
                                        )}
                                      </div>

                                      <div className="mt-4 p-4 border rounded-lg bg-muted/20 space-y-3">
                                        <div className="text-xs text-muted-foreground uppercase tracking-wider">
                                          Manual Override
                                        </div>
                                        {transaction.verdict?.override_notes && (
                                          <p className="text-xs text-muted-foreground italic">
                                            Last override: {transaction.verdict.override_notes}
                                          </p>
                                        )}
                                        <Button
                                          variant="outline"
                                          size="sm"
                                          onClick={() => handlePassWithReviewClick(transaction.id, index)}
                                          disabled={!transaction.id}
                                          className="gap-1.5 border-emerald-500/50 text-emerald-700 hover:bg-emerald-500/10"
                                        >
                                          <ClipboardCheck className="h-4 w-4" />
                                          {showOverrideReason[getOverrideKey(transaction.id, index)] ? 'Confirm Pass with Review' : 'Pass with Review'}
                                        </Button>
                                        {showOverrideReason[getOverrideKey(transaction.id, index)] && (
                                          <div className="space-y-2">
                                            <Textarea
                                              rows={4}
                                              value={overrideReasons[getOverrideKey(transaction.id, index)] ?? ""}
                                              onChange={(event) =>
                                                setOverrideReasons(prev => ({
                                                  ...prev,
                                                  [getOverrideKey(transaction.id, index)]: event.target.value,
                                                }))
                                              }
                                              placeholder="Provide the reason this transaction should pass with review."
                                              className="min-h-[120px] w-full"
                                            />
                                            <p className="text-xs text-muted-foreground">
                                              Add context explaining why the transaction can proceed.
                                            </p>
                                          </div>
                                        )}
                                      </div>

                                      {transaction.user_action && (
                                        <div className="mt-4 pt-4 border-t border-green-300 dark:border-green-800">
                                          <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => transaction.id && handleActionClick(transaction.id, index, '')}
                                            className="text-xs font-medium bg-red-500/20 text-red-700 dark:text-red-300 border-transparent hover:bg-red-500/30"
                                          >
                                            <X className="h-3 w-3 mr-1" />
                                            Remove Action
                                          </Button>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}

                                {/* All Transaction Details - Collapsible */}
                                <Collapsible open={showAll} onOpenChange={() => toggleAllFields(index)}>
                                  <div className="bg-background rounded-lg border shadow-sm overflow-hidden">
                                    <CollapsibleTrigger asChild>
                                      <button className="w-full px-5 py-4 flex items-center justify-between hover:bg-muted/30 transition-colors">
                                        <h4 className="text-sm font-semibold uppercase tracking-wide">All Transaction Details</h4>
                                        <ChevronDown className={`h-4 w-4 transition-transform ${showAll ? 'rotate-180' : ''}`} />
                                      </button>
                                    </CollapsibleTrigger>

                                    <CollapsibleContent>
                                      <div className="px-5 pb-5 pt-2 border-t">
                                        <div className="grid grid-cols-2 gap-4">
                                          {Object.entries(transaction).map(([key, value]) => {
                                            if (['merchant', 'amount', 'currency', 'category', 'timestamp', 'originator_name', 'product_type', 'booking_datetime', 'beneficiary_name', 'status', 'verdict', 'triage', 'isAnalyzing', 'isTriaging', 'user_action', 'user_action_timestamp', 'user_action_by', 'id', 'payment_id'].includes(key)) {
                                              return null
                                            }
                                            return (
                                              <div key={key} className="space-y-1 p-3 rounded-lg bg-muted/30">
                                                <div className="text-xs text-muted-foreground uppercase tracking-wider capitalize">
                                                  {key.replace(/_/g, ' ')}
                                                </div>
                                                <div className="text-sm font-medium break-all">{String(value) || 'N/A'}</div>
                                              </div>
                                            )
                                          })}
                                        </div>
                                      </div>
                                    </CollapsibleContent>
                                  </div>
                                </Collapsible>

                                {/* Delete Button */}
                                {transaction.id && (
                                  <div className="flex justify-end">
                                    <Button
                                      variant="destructive"
                                      size="sm"
                                      onClick={() => handleDeleteTransaction(transaction.id!, index)}
                                      className="gap-2 shadow-sm"
                                    >
                                      <Trash2 className="h-4 w-4" />
                                      Delete Transaction
                                    </Button>
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
            </div>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
