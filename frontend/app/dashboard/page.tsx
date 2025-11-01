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
import { useState } from "react"
import { ChevronDown } from "lucide-react"

interface Verdict {
  payment_id: string
  trace_id: string
  verdict: 'pass' | 'suspicious' | 'fail'
  assigned_team: string
  risk_score: number
  rule_score: number
  pattern_score: number
  llm_risk_score?: number
  justification: string
  triggered_rules: any[]
  detected_patterns: any[]
  llm_flagged_transactions?: any[]
  llm_patterns?: any[]
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
  isAnalyzing?: boolean
  [key: string]: any
}

export default function Page() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [expandedCards, setExpandedCards] = useState<Set<number>>(new Set())
  const [showAllFields, setShowAllFields] = useState<Set<number>>(new Set())

  const loadTransaction = async () => {
    setIsLoading(true)
    try {
      // Fetch 5 random transactions from CSV
      const response = await fetch('/api/v1/payments/sample')
      if (!response.ok) {
        throw new Error('Failed to fetch transactions')
      }
      const fetchedTransactions = await response.json()

      // Add transactions with analyzing state
      const transactionsWithState = fetchedTransactions.map((txn: any) => ({
        ...txn,
        isAnalyzing: true,
      }))

      // Add to the list immediately
      setTransactions(prev => [...transactionsWithState, ...prev])

      // Analyze each transaction
      for (let i = 0; i < fetchedTransactions.length; i++) {
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

            // Update the specific transaction with verdict
            setTransactions(prev =>
              prev.map((txn, idx) =>
                idx === i
                  ? { ...txn, verdict, isAnalyzing: false }
                  : txn
              )
            )
          } else {
            // Mark as failed analysis
            setTransactions(prev =>
              prev.map((txn, idx) =>
                idx === i
                  ? { ...txn, isAnalyzing: false }
                  : txn
              )
            )
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
        <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold tracking-tight">Transaction Monitor</h2>
            <Button onClick={loadTransaction} disabled={isLoading}>
              {isLoading ? "Loading..." : "Load Transaction"}
            </Button>
          </div>

          {/* Recent Transactions - Full Width */}
          <div className="flex flex-col gap-4">
            <Card className="flex flex-col">
              <CardHeader>
                <CardTitle>Recent Transactions</CardTitle>
                <CardDescription>Incoming transactions with risk analysis</CardDescription>
              </CardHeader>
              <CardContent className="flex-1 overflow-auto">
                {transactions.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">
                    No transactions yet. Click "Load Transaction" to fetch sample transactions.
                  </p>
                ) : (
                  <div className="flex flex-col gap-3">
                    {transactions.map((transaction, index) => {
                      const isExpanded = expandedCards.has(index)
                      const showAll = showAllFields.has(index)

                      return (
                        <Card
                          key={index}
                          className={`cursor-pointer hover:shadow-md transition-shadow border-2 ${getRiskColor(transaction.verdict?.verdict)}`}
                          onClick={() => toggleCard(index)}
                        >
                        <CardHeader>
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <CardTitle className="text-sm font-medium text-muted-foreground">
                                  Incoming Transaction
                                </CardTitle>
                                {transaction.isAnalyzing && (
                                  <span className="text-xs bg-blue-500 text-white px-2 py-0.5 rounded-full animate-pulse">
                                    Analyzing...
                                  </span>
                                )}
                                {transaction.verdict && transaction.verdict.verdict && (
                                  <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${getRiskBadgeColor(transaction.verdict.verdict)}`}>
                                    {transaction.verdict.verdict.toUpperCase()}
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center justify-between">
                                <span className="text-xl font-semibold">
                                  {transaction.originator_name || transaction.merchant || 'Unknown Merchant'}
                                </span>
                              </div>
                            </div>
                            <div className="flex flex-col items-end gap-1">
                              <span className="text-xl font-bold">
                                {transaction.currency || '$'}{typeof transaction.amount === 'number' ? transaction.amount.toFixed(2) : parseFloat(transaction.amount || '0').toFixed(2)}
                              </span>
                              {transaction.verdict && (
                                <span className="text-xs text-muted-foreground">
                                  Score: {transaction.verdict.risk_score.toFixed(1)}
                                </span>
                              )}
                            </div>
                          </div>
                        </CardHeader>

                        {isExpanded && (
                          <CardContent onClick={(e) => e.stopPropagation()}>
                            <div className="space-y-4">
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
                                      <p className="font-medium">{transaction.verdict.risk_score.toFixed(2)}</p>
                                    </div>
                                    <div>
                                      <span className="text-muted-foreground">Rule Score:</span>
                                      <p className="font-medium">{transaction.verdict.rule_score.toFixed(2)}</p>
                                    </div>
                                  </div>
                                  {transaction.verdict.justification && (
                                    <div>
                                      <span className="text-muted-foreground">Justification:</span>
                                      <p className="text-sm mt-1 font-medium">{transaction.verdict.justification}</p>
                                    </div>
                                  )}
                                  {transaction.verdict.triggered_rules && transaction.verdict.triggered_rules.length > 0 && (
                                    <div>
                                      <span className="text-muted-foreground">Triggered Rules ({transaction.verdict.triggered_rules.length}):</span>
                                      <ul className="list-disc list-inside text-sm mt-1">
                                        {transaction.verdict.triggered_rules.map((rule: any, i) => (
                                          <li key={i} className="font-medium">{rule.rule_name || rule.name || `Rule ${i + 1}`}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                </div>
                              )}

                              <div className="grid grid-cols-2 gap-3 text-sm pb-4 border-b">
                                <div>
                                  <span className="text-muted-foreground">Type:</span>
                                  <p className="font-medium">{transaction.product_type || transaction.category || 'N/A'}</p>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Date:</span>
                                  <p className="font-medium">{transaction.booking_datetime || transaction.timestamp || 'N/A'}</p>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Beneficiary:</span>
                                  <p className="font-medium">{transaction.beneficiary_name || 'N/A'}</p>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Status:</span>
                                  <p className="font-medium capitalize">{transaction.status || 'N/A'}</p>
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
                                      if (['merchant', 'amount', 'currency', 'category', 'timestamp', 'originator_name', 'product_type', 'booking_datetime', 'beneficiary_name', 'status', 'verdict', 'isAnalyzing'].includes(key)) {
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
                            </div>
                          </CardContent>
                        )}
                      </Card>
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
