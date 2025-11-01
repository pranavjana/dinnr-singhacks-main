"use client"

import { useEffect, useState } from "react"
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { AlertCircle, CheckCircle2, AlertTriangle, XCircle, Clock, ShieldCheck, ShieldAlert, ShieldX } from "lucide-react"

interface Action {
  id: string
  payment_id: string | null
  amount: number
  currency: string
  originator_name: string | null
  beneficiary_name: string | null
  merchant: string | null
  user_action: string | null
  user_action_timestamp: string | null
  user_action_by: string | null
  verdict: {
    risk_level?: string
    risk_score?: number
    verdict?: string
  } | null
  booking_datetime: string | null
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"

const getThreatLevelColor = (riskLevel: string | undefined) => {
  // Muted secondary color for all risk levels
  return "bg-secondary/50 dark:bg-secondary/20 border-secondary/60 dark:border-secondary/40 hover:border-secondary/80 dark:hover:border-secondary/60"
}

const getThreatIcon = (riskLevel: string | undefined) => {
  switch (riskLevel?.toLowerCase()) {
    case "critical":
    case "high":
      return <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
    case "medium":
      return <AlertTriangle className="h-4 w-4 text-orange-600 dark:text-orange-400" />
    case "low":
      return <AlertCircle className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
    default:
      return <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
  }
}

const getActionBadgeVariant = (action: string | null): "default" | "destructive" | "secondary" | "outline" => {
  switch (action?.toLowerCase()) {
    case "approve":
    case "approved":
      return "default"
    case "reject":
    case "rejected":
      return "destructive"
    case "escalate":
    case "escalated":
      return "secondary"
    default:
      return "outline"
  }
}

// Determine which column an action belongs to based on verdict and action
const getActionColumn = (action: Action): "pass" | "suspicious" | "fail" => {
  const userAction = action.user_action?.toLowerCase()

  // Extract verdict - check both direct field and nested field
  const verdictObj = action.verdict as any
  const verdict = (verdictObj?.verdict || verdictObj?.Verdict)?.toLowerCase()
  const riskLevel = (verdictObj?.risk_level || verdictObj?.Risk_Level)?.toLowerCase()

  // User action takes precedence
  if (userAction === "approve" || userAction === "approved") {
    return "pass"
  }
  if (userAction === "reject" || userAction === "rejected") {
    return "fail"
  }
  if (userAction === "escalate" || userAction === "escalated") {
    return "suspicious"
  }

  // Fall back to verdict field
  if (verdict === "pass") {
    return "pass"
  }
  if (verdict === "fail") {
    return "fail"
  }
  if (verdict === "suspicious" || verdict === "review") {
    return "suspicious"
  }

  // Fall back to risk level
  if (riskLevel === "low" || riskLevel === "unknown") {
    return "pass"
  }
  if (riskLevel === "critical" || riskLevel === "high") {
    return "fail"
  }
  if (riskLevel === "medium") {
    return "suspicious"
  }

  return "suspicious"
}

export default function ActionsPage() {
  const [actions, setActions] = useState<Action[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchActions = async () => {
      try {
        const response = await fetch(`/api/v1/transactions?has_action=true`)
        if (!response.ok) {
          throw new Error("Failed to fetch actions")
        }
        const data = await response.json()

        // Handle both array and object response formats
        const actionsArray = Array.isArray(data) ? data : data.transactions || []

        // Sort by user_action_timestamp (most recent first)
        const sortedData = actionsArray.sort((a: Action, b: Action) => {
          const timeA = a.user_action_timestamp ? new Date(a.user_action_timestamp).getTime() : 0
          const timeB = b.user_action_timestamp ? new Date(b.user_action_timestamp).getTime() : 0
          return timeB - timeA
        })
        setActions(sortedData)
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred")
      } finally {
        setLoading(false)
      }
    }

    fetchActions()
  }, [])

  // Group actions by column and then by risk level within each column
  const groupedByColumn = actions.reduce((acc, action) => {
    const column = getActionColumn(action)

    // Extract risk level from notable_transactions or llm_flagged_transactions
    const verdictObj = action.verdict as any
    let riskLevel = verdictObj?.risk_level || verdictObj?.Risk_Level

    // If not found directly, check in notable_transactions
    if (!riskLevel && verdictObj?.notable_transactions?.length > 0) {
      riskLevel = verdictObj.notable_transactions[0].risk_level
    }

    // If not found, check in llm_flagged_transactions
    if (!riskLevel && verdictObj?.llm_flagged_transactions?.length > 0) {
      riskLevel = verdictObj.llm_flagged_transactions[0].risk_level
    }

    // Normalize to lowercase
    riskLevel = (riskLevel || "unknown").toLowerCase()

    if (!acc[column]) {
      acc[column] = {}
    }
    if (!acc[column][riskLevel]) {
      acc[column][riskLevel] = []
    }
    acc[column][riskLevel].push(action)

    return acc
  }, {} as Record<string, Record<string, Action[]>>)

  const columns = [
    {
      id: "pass",
      title: "Pass",
      icon: <ShieldCheck className="h-5 w-5" />,
      bgColor: "bg-green-50 dark:bg-green-950/20",
      textColor: "text-green-700 dark:text-green-400",
    },
    {
      id: "suspicious",
      title: "Suspicious",
      icon: <ShieldAlert className="h-5 w-5" />,
      bgColor: "bg-orange-50 dark:bg-orange-950/20",
      textColor: "text-orange-700 dark:text-orange-400",
    },
    {
      id: "fail",
      title: "Fail",
      icon: <ShieldX className="h-5 w-5" />,
      bgColor: "bg-red-50 dark:bg-red-950/20",
      textColor: "text-red-700 dark:text-red-400",
    },
  ]

  const threatLevelOrder = ["critical", "high", "medium", "low", "unknown"]

  const renderActionCard = (action: Action) => {
    // Extract risk level and score
    const verdictObj = action.verdict as any
    let riskLevel = verdictObj?.risk_level || verdictObj?.Risk_Level
    let riskScore = verdictObj?.risk_score || verdictObj?.Risk_Score

    // Check in notable_transactions if not found
    if (!riskLevel && verdictObj?.notable_transactions?.length > 0) {
      riskLevel = verdictObj.notable_transactions[0].risk_level
    }
    if (!riskLevel && verdictObj?.llm_flagged_transactions?.length > 0) {
      riskLevel = verdictObj.llm_flagged_transactions[0].risk_level
    }

    return (
      <Card
        key={action.id}
        className={`${getThreatLevelColor(riskLevel)} transition-all hover:shadow-md mb-2 p-3`}
      >
        <div className="space-y-2">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-1.5 flex-1 min-w-0">
              {getThreatIcon(riskLevel)}
              <h3 className="text-xs font-semibold truncate">
                {action.merchant || action.beneficiary_name || "Unknown"}
              </h3>
            </div>
            <Badge variant={getActionBadgeVariant(action.user_action)} className="shrink-0 text-[10px] px-1.5 py-0">
              {action.user_action || "N/A"}
            </Badge>
          </div>

          <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[10px]">
            <div className="flex justify-between col-span-2">
              <span className="text-muted-foreground">Amount:</span>
              <span className="font-semibold">{action.currency} {action.amount.toLocaleString()}</span>
            </div>
            {riskScore !== undefined && (
              <div className="flex justify-between col-span-2">
                <span className="text-muted-foreground">Risk Score:</span>
                <span className="font-semibold">{typeof riskScore === 'number' ? riskScore : parseFloat(riskScore)}</span>
              </div>
            )}
          </div>

          {action.user_action_timestamp && (
            <div className="flex items-center gap-1 text-[10px] text-muted-foreground pt-1.5 border-t">
              <Clock className="h-2.5 w-2.5" />
              <span className="truncate">{new Date(action.user_action_timestamp).toLocaleString()}</span>
            </div>
          )}
        </div>
      </Card>
    )
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
                  <BreadcrumbPage>Actions</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>

        <div className="flex flex-1 flex-col p-4 pt-0 overflow-hidden">
          <div className="flex items-center justify-between mb-4 flex-shrink-0">
            <div>
              <h1 className="text-3xl font-bold">Actions Board</h1>
              <p className="text-muted-foreground">
                {loading ? "Loading..." : `${actions.length} ${actions.length === 1 ? "action" : "actions"} taken`}
              </p>
            </div>
          </div>

          {loading ? (
            <div className="grid gap-4 md:grid-cols-3">
              {[1, 2, 3].map((i) => (
                <Card key={i}>
                  <CardHeader>
                    <Skeleton className="h-6 w-[120px]" />
                  </CardHeader>
                  <CardContent>
                    <Skeleton className="h-40 w-full" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : error ? (
            <Card className="border-red-300 dark:border-red-800">
              <CardHeader>
                <CardTitle className="text-red-600 dark:text-red-400">Error Loading Actions</CardTitle>
                <CardDescription>{error}</CardDescription>
              </CardHeader>
            </Card>
          ) : actions.length === 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>No Actions Yet</CardTitle>
                <CardDescription>
                  No actions have been taken on any transactions yet. Actions will appear here when you approve,
                  reject, or escalate transactions.
                </CardDescription>
              </CardHeader>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-3 flex-1 min-h-0">
              {columns.map((column) => {
                const columnActions = groupedByColumn[column.id] || {}
                // Filter out unknown risk level
                const sortedRiskLevels = Object.keys(columnActions)
                  .filter((riskLevel) => riskLevel.toLowerCase() !== "unknown")
                  .sort((a, b) => threatLevelOrder.indexOf(a.toLowerCase()) - threatLevelOrder.indexOf(b.toLowerCase()))
                const totalCount = Object.values(columnActions).reduce((sum, arr) => sum + arr.length, 0)

                return (
                  <div key={column.id} className="flex flex-col min-h-0">
                    <Card className="flex flex-col h-full min-h-0">
                      <CardHeader className="border-b pb-3 flex-shrink-0">
                        <div className="flex items-center gap-3">
                          <div className={column.textColor}>{column.icon}</div>
                          <CardTitle className="text-base font-semibold">{column.title}</CardTitle>
                          <Badge variant="secondary" className="ml-auto">
                            {totalCount}
                          </Badge>
                        </div>
                      </CardHeader>
                      <CardContent className="flex-1 pt-4 overflow-y-auto min-h-0">
                        {sortedRiskLevels.length === 0 ? (
                          <div className="text-center py-8 text-muted-foreground text-sm">
                            No actions in this category
                          </div>
                        ) : (
                          <div className="space-y-0">
                            {sortedRiskLevels.map((riskLevel) => (
                              <div key={riskLevel}>
                                {columnActions[riskLevel].map(renderActionCard)}
                              </div>
                            ))}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
