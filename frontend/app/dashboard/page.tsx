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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { useState, useEffect } from "react"
import { ChevronDown, Trash2, Check } from "lucide-react"
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

export default function Page() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [expandedCards, setExpandedCards] = useState<Set<number>>(new Set())
  const [showAllFields, setShowAllFields] = useState<Set<number>>(new Set())

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

          {/* Recent Transactions - Full Width */}
          <div className="flex flex-col flex-1 min-h-0">
            <Card className="flex flex-col h-full min-h-0 border-0 shadow-none">
              <CardHeader className="flex-shrink-0">
                <CardTitle>Recent Transactions</CardTitle>
                <CardDescription>Incoming transactions with risk analysis</CardDescription>
              </CardHeader>
              <CardContent className="flex-1 overflow-y-auto min-h-0">
                {transactions.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">
                    No transactions yet. Click "Load Transaction" to fetch sample transactions.
                  </p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {/* Column Headers */}
                    <div className="sticky top-0 bg-background z-10 flex items-center gap-4 px-3 py-2 text-xs font-semibold text-muted-foreground border-b">
                      <div className="flex-1 min-w-0">Merchant / Originator</div>
                      <div className="w-[200px] text-center">Status</div>
                      <div className="w-[120px] text-right">Amount</div>
                      <div className="w-4"></div>
                    </div>

                    {transactions.map((transaction, index) => {
                      const isExpanded = expandedCards.has(index)
                      const showAll = showAllFields.has(index)

                      return (
                        <div key={index} className="group">
                          {/* Compact Transaction Row */}
                          <div
                            className="flex items-center gap-4 p-3 rounded-lg bg-secondary/50 dark:bg-secondary/20 cursor-pointer transition-all hover:bg-secondary/60 dark:hover:bg-secondary/30"
                            onClick={() => toggleCard(index)}
                          >
                            {/* Left: Name and Type */}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-sm truncate">
                                  {transaction.originator_name || transaction.merchant || 'Unknown Merchant'}
                                </span>
                                <span className="text-xs text-muted-foreground">
                                  {transaction.product_type || transaction.category || 'N/A'}
                                </span>
                              </div>
                            </div>

                            {/* Center: Status Badges */}
                            <div className="w-[200px] flex items-center justify-center gap-1.5">
                              {transaction.isAnalyzing && (
                                <span className="text-xs bg-blue-500/20 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded-md animate-pulse">
                                  Analyzing
                                </span>
                              )}
                              {transaction.isTriaging && (
                                <span className="text-xs bg-purple-500/20 text-purple-700 dark:text-purple-300 px-2 py-0.5 rounded-md animate-pulse">
                                  Triaging
                                </span>
                              )}
                              {transaction.verdict?.verdict && !transaction.isAnalyzing && (
                                <span className={`text-xs px-2 py-0.5 rounded-md ${
                                  transaction.verdict.verdict === 'fail' ? 'bg-red-500/20 text-red-700 dark:text-red-300' :
                                  transaction.verdict.verdict === 'suspicious' ? 'bg-orange-500/20 text-orange-700 dark:text-orange-300' :
                                  transaction.verdict.verdict === 'pass' ? 'bg-green-500/20 text-green-700 dark:text-green-300' :
                                  'bg-gray-500/20 text-gray-700 dark:text-gray-300'
                                }`}>
                                  {transaction.verdict.verdict.toUpperCase()}
                                </span>
                              )}
                            </div>

                            {/* Right: Amount */}
                            <div className="w-[120px] text-right">
                              <div className="font-bold text-sm">
                                {transaction.currency || 'SGD'} {typeof transaction.amount === 'number' ? transaction.amount.toFixed(2) : parseFloat(transaction.amount || '0').toFixed(2)}
                              </div>
                            </div>

                            {/* Expand Indicator */}
                            <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                          </div>

                          {/* Expanded Details */}
                          {isExpanded && (
                            <div className="mt-2 ml-4 p-4 border-l-2 border-gray-200 dark:border-gray-800 space-y-4" onClick={(e) => e.stopPropagation()}>
                              {/* Risk Analysis Section */}
                              {transaction.verdict && (
                                <div className="p-3 rounded-lg bg-muted/50 space-y-2">
                                  <h4 className="text-sm font-semibold">Risk Analysis</h4>
                                  <div className="grid grid-cols-2 gap-3 text-sm">
                                    <div>
                                      <span className="text-muted-foreground">Verdict:</span>
                                      <p className="font-medium uppercase">{transaction.verdict.verdict}</p>
                                    </div>
                                    <div>
                                      <span className="text-muted-foreground">Assigned Team:</span>
                                      <p className="font-medium">{transaction.verdict.assigned_team}</p>
                                    </div>
                                    <div>
                                      <span className="text-muted-foreground">Risk Score:</span>
                                      <p className="font-medium">{transaction.verdict.risk_score?.toFixed(2) || 'N/A'}</p>
                                    </div>
                                    {transaction.verdict.rule_score !== undefined && (
                                      <div>
                                        <span className="text-muted-foreground">Rule Score:</span>
                                        <p className="font-medium">{transaction.verdict.rule_score.toFixed(2)}</p>
                                      </div>
                                    )}
                                  </div>
                                  {transaction.verdict.justification && (
                                    <div>
                                      <span className="text-muted-foreground">Justification:</span>
                                      <p className="text-sm mt-1 font-medium">{transaction.verdict.justification}</p>
                                    </div>
                                  )}
                                  {transaction.verdict.triggered_rules && transaction.verdict.triggered_rules.length > 0 && (
                                    <div>
                                      <span className="text-muted-foreground">Detected Patterns ({transaction.verdict.triggered_rules.length}):</span>
                                      <ul className="list-disc list-inside text-sm mt-1 space-y-1">
                                        {transaction.verdict.triggered_rules.map((rule: any, i) => (
                                          <li key={i} className="font-medium">
                                            <span className="font-semibold text-red-600">{rule.pattern_type || rule.rule_name || rule.name || `Pattern ${i + 1}`}</span>
                                            {rule.description && <span className="text-muted-foreground">: {rule.description}</span>}
                                            {rule.severity && <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-orange-100 text-orange-800">{rule.severity}</span>}
                                          </li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                </div>
                              )}

                              {/* AML Triage Section */}
                              {transaction.triage && (
                                <div className="p-3 rounded-lg bg-blue-50/50 dark:bg-blue-950/30 space-y-3 border border-blue-200 dark:border-blue-800">
                                  <div className="flex items-center justify-between">
                                    <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-100">Recommended Actions</h4>
                                    <span className="text-xs bg-blue-500/20 text-blue-700 dark:text-blue-300 px-2 py-1 rounded-md">
                                      {transaction.triage.screening_result.decision}
                                    </span>
                                  </div>
                                  <div className="flex flex-wrap gap-2">
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
                                            className={`text-xs transition-all duration-300 gap-1.5 ${
                                              isSelected
                                                ? 'bg-green-100/80 dark:bg-green-900/40 border-green-400 dark:border-green-600 text-green-800 dark:text-green-200 hover:bg-green-100/80 dark:hover:bg-green-900/40'
                                                : 'bg-white dark:bg-gray-900 border-blue-300 dark:border-blue-700 hover:bg-blue-50 dark:hover:bg-blue-950'
                                            }`}
                                          >
                                            {isSelected && (
                                              <Check className="h-3 w-3 animate-in zoom-in-50 duration-300" />
                                            )}
                                            {action.replace('action_', '').replace(/_/g, ' ')}
                                          </Button>
                                        )
                                      })
                                    ) : (
                                      <span className="text-xs text-muted-foreground">No actions required</span>
                                    )}
                                  </div>
                                </div>
                              )}

                              <div className="grid grid-cols-2 gap-3 text-sm pb-4 border-b">
                                <div>
                                  <span className="text-muted-foreground">Type:</span>
                                  <p className="font-medium">{transaction.product_type || transaction.category || 'N/A'}</p>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Beneficiary:</span>
                                  <p className="font-medium">{transaction.beneficiary_name || 'N/A'}</p>
                                </div>
                              </div>

                              <Collapsible open={showAll} onOpenChange={() => toggleAllFields(index)}>
                                <div className="flex items-center justify-between">
                                  <h4 className="text-sm font-semibold">All Transaction Details</h4>
                                  <CollapsibleTrigger asChild>
                                    <Button variant="ghost" size="sm" className="w-9 p-0">
                                      <ChevronDown className={`h-4 w-4 transition-transform ${showAll ? 'rotate-180' : ''}`} />
                                      <span className="sr-only">Toggle all fields</span>
                                    </Button>
                                  </CollapsibleTrigger>
                                </div>

                                <CollapsibleContent className="mt-4">
                                  <div className="grid grid-cols-2 gap-3 text-sm">
                                    {Object.entries(transaction).map(([key, value]) => {
                                      if (['merchant', 'amount', 'currency', 'category', 'timestamp', 'originator_name', 'product_type', 'booking_datetime', 'beneficiary_name', 'status', 'verdict', 'triage', 'isAnalyzing', 'isTriaging'].includes(key)) {
                                        return null
                                      }
                                      return (
                                        <div key={key} className="space-y-1">
                                          <span className="text-muted-foreground capitalize">{key.replace(/_/g, ' ')}:</span>
                                          <p className="font-medium break-all">{String(value) || 'N/A'}</p>
                                        </div>
                                      )
                                    })}
                                  </div>
                                </CollapsibleContent>
                              </Collapsible>

                              {/* Delete Button */}
                              {transaction.id && (
                                <div className="pt-4 border-t flex justify-end">
                                  <Button
                                    variant="destructive"
                                    size="sm"
                                    onClick={() => handleDeleteTransaction(transaction.id!, index)}
                                    className="gap-2"
                                  >
                                    <Trash2 className="h-4 w-4" />
                                    Delete Transaction
                                  </Button>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
