"use client"

import { useEffect, useMemo, useState } from "react"
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
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Search,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  XCircle,
} from "lucide-react"

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
    Risk_Level?: string
    risk_score?: number | string
    Risk_Score?: number | string
    verdict?: string
    Verdict?: string
    notable_transactions?: Array<{ risk_level?: string | null; originator_name?: string | null }>
    llm_flagged_transactions?: Array<{ risk_level?: string | null; originator_name?: string | null }>
  } | null
  booking_datetime: string | null
}

const riskLevelMetadata: Record<
  string,
  {
    label: string
    textClass: string
    dividerClass: string
  }
> = {
  critical: {
    label: "Critical Risk",
    textClass: "text-red-600 dark:text-red-300",
    dividerClass: "from-red-500/20 via-transparent to-transparent",
  },
  high: {
    label: "High Risk",
    textClass: "text-orange-600 dark:text-orange-300",
    dividerClass: "from-orange-500/20 via-transparent to-transparent",
  },
  medium: {
    label: "Medium Risk",
    textClass: "text-amber-600 dark:text-amber-300",
    dividerClass: "from-amber-500/15 via-transparent to-transparent",
  },
  low: {
    label: "Low Risk",
    textClass: "text-emerald-600 dark:text-emerald-300",
    dividerClass: "from-emerald-500/15 via-transparent to-transparent",
  },
  unknown: {
    label: "Unclassified",
    textClass: "text-muted-foreground",
    dividerClass: "from-slate-500/10 via-transparent to-transparent",
  },
}

const getRiskMetadata = (riskLevel?: string | null) => {
  const normalized = riskLevel?.toLowerCase() || "unknown"
  return riskLevelMetadata[normalized] || riskLevelMetadata.unknown
}

const getActionStatusMetadata = (status: string | null) => {
  const normalized = (status || "unknown").toLowerCase()
  if (normalized === "approve" || normalized === "approved") {
    return {
      label: "Approved",
      textClass: "text-emerald-600 dark:text-emerald-300",
      icon: CheckCircle2,
    }
  }
  if (normalized === "escalate" || normalized === "escalated") {
    return {
      label: "Escalated",
      textClass: "text-amber-600 dark:text-amber-300",
      icon: AlertTriangle,
    }
  }
  if (normalized === "reject" || normalized === "rejected") {
    return {
      label: "Rejected",
      textClass: "text-red-600 dark:text-red-300",
      icon: XCircle,
    }
  }
  return {
    label: "Pending",
    textClass: "text-muted-foreground",
    icon: AlertCircle,
  }
}

const formatRelativeTime = (timestamp: string | null) => {
  if (!timestamp) {
    return null
  }
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) {
    return null
  }
  const now = new Date()
  const diffMs = date.getTime() - now.getTime()
  const diffSeconds = Math.round(diffMs / 1000)
  const absSeconds = Math.abs(diffSeconds)

  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" })

  if (absSeconds < 60) {
    return rtf.format(diffSeconds, "second")
  }
  const diffMinutes = Math.round(diffSeconds / 60)
  if (Math.abs(diffMinutes) < 60) {
    return rtf.format(diffMinutes, "minute")
  }
  const diffHours = Math.round(diffMinutes / 60)
  if (Math.abs(diffHours) < 24) {
    return rtf.format(diffHours, "hour")
  }
  const diffDays = Math.round(diffHours / 24)
  if (Math.abs(diffDays) < 7) {
    return rtf.format(diffDays, "day")
  }
  const diffWeeks = Math.round(diffDays / 7)
  if (Math.abs(diffWeeks) < 5) {
    return rtf.format(diffWeeks, "week")
  }
  const diffMonths = Math.round(diffDays / 30)
  if (Math.abs(diffMonths) < 12) {
    return rtf.format(diffMonths, "month")
  }
  const diffYears = Math.round(diffDays / 365)
  return rtf.format(diffYears, "year")
}

const parseRiskDetails = (action: Action) => {
  const verdictObj = action.verdict
  let riskLevel = verdictObj?.risk_level || verdictObj?.Risk_Level
  const riskScore = verdictObj?.risk_score ?? verdictObj?.Risk_Score

  if (!riskLevel && verdictObj?.notable_transactions?.length) {
    riskLevel = verdictObj.notable_transactions[0]?.risk_level || riskLevel
  }
  if (!riskLevel && verdictObj?.llm_flagged_transactions?.length) {
    riskLevel = verdictObj.llm_flagged_transactions[0]?.risk_level || riskLevel
  }

  return {
    riskLevel: (riskLevel || "unknown").toLowerCase(),
    riskScore,
  }
}

// Determine which column an action belongs to based on verdict and action
const getActionColumn = (action: Action): "pass" | "suspicious" | "fail" => {
  const userAction = action.user_action?.toLowerCase()

  // Extract verdict - check both direct field and nested field
  const verdictObj = action.verdict
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
  const [searchTerm, setSearchTerm] = useState("")
  const [dateFilter, setDateFilter] = useState<string>("all")

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

  const filteredActions = useMemo(() => {
    if (!actions.length) {
      return []
    }
    return actions.filter((action) => {
      const searchValue = searchTerm.trim().toLowerCase()
      if (searchValue) {
        const senderName = action.originator_name?.toLowerCase() ?? ""
        const merchantName = action.merchant?.toLowerCase() ?? ""
        const notableSenders = (action.verdict?.notable_transactions ?? [])
          .map((tx) => tx?.originator_name?.toLowerCase() ?? null)
          .filter((name): name is string => Boolean(name))
        const flaggedSenders = (action.verdict?.llm_flagged_transactions ?? [])
          .map((tx) => tx?.originator_name?.toLowerCase() ?? null)
          .filter((name): name is string => Boolean(name))
        const matchesSender =
          senderName.includes(searchValue) ||
          merchantName.includes(searchValue) ||
          notableSenders.some((name) => name.includes(searchValue)) ||
          flaggedSenders.some((name) => name.includes(searchValue))
        if (!matchesSender) {
          return false
        }
      }

      if (dateFilter !== "all") {
        const timestamp = action.user_action_timestamp || action.booking_datetime
        if (!timestamp) {
          return false
        }
        const date = new Date(timestamp)
        if (Number.isNaN(date.getTime())) {
          return false
        }
        const diffMs = Date.now() - date.getTime()
        if (dateFilter === "24h" && diffMs > 1000 * 60 * 60 * 24) {
          return false
        }
        if (dateFilter === "7d" && diffMs > 1000 * 60 * 60 * 24 * 7) {
          return false
        }
        if (dateFilter === "30d" && diffMs > 1000 * 60 * 60 * 24 * 30) {
          return false
        }
      }

      return true
    })
  }, [actions, dateFilter, searchTerm])

  // Group actions by column and then by risk level within each column
  const groupedByColumn = filteredActions.reduce((acc, action) => {
    const column = getActionColumn(action)

    const { riskLevel } = parseRiskDetails(action)

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
      id: "pass" as const,
      title: "Pass",
      icon: ShieldCheck,
      iconTint: "text-emerald-600 dark:text-emerald-300",
      iconBg: "bg-emerald-500/10 dark:bg-emerald-500/20",
    },
    {
      id: "suspicious" as const,
      title: "Suspicious",
      icon: ShieldAlert,
      iconTint: "text-amber-600 dark:text-amber-300",
      iconBg: "bg-amber-500/10 dark:bg-amber-500/20",
    },
    {
      id: "fail" as const,
      title: "Fail",
      icon: ShieldX,
      iconTint: "text-rose-600 dark:text-rose-300",
      iconBg: "bg-rose-500/10 dark:bg-rose-500/20",
    },
  ]

  const threatLevelOrder = ["critical", "high", "medium", "low", "unknown"]

  const renderActionCard = (action: Action, columnId: "pass" | "suspicious" | "fail") => {
    const { riskLevel, riskScore } = parseRiskDetails(action)
    const riskMeta = getRiskMetadata(riskLevel)
    const statusMeta = getActionStatusMetadata(action.user_action)
    const StatusIcon = statusMeta.icon
    const riskScoreValue =
      riskScore !== undefined && riskScore !== null ? Number(riskScore) : undefined
    const formattedRiskScore =
      riskScoreValue !== undefined && !Number.isNaN(riskScoreValue)
        ? riskScoreValue.toFixed(0)
        : undefined
    const timestamp = action.user_action_timestamp || action.booking_datetime
    const relativeTime = formatRelativeTime(timestamp)
    const amountDisplay = `${action.currency ? `${action.currency} ` : ""}${action.amount.toLocaleString()}`
    const originator = action.originator_name || "Unknown originator"
    const beneficiary = action.beneficiary_name || "Unknown beneficiary"
    const formattedTimestamp = timestamp ? new Date(timestamp).toLocaleString() : null
    const primaryName = action.originator_name || action.merchant || action.beneficiary_name || "Untitled action"
    const actionTaken = action.user_action
      ? action.user_action.replace(/^action_/, "").replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase())
      : null
    const columnTone = {
      pass: "bg-emerald-500/5 border-emerald-500/20 dark:bg-emerald-500/10 dark:border-emerald-500/30",
      suspicious: "bg-amber-500/5 border-amber-500/20 dark:bg-amber-500/10 dark:border-amber-500/30",
      fail: "bg-rose-500/5 border-rose-500/20 dark:bg-rose-500/10 dark:border-rose-500/30",
    }[columnId]
    const actionBadgeTone = {
      pass: "bg-emerald-500/15 border-emerald-500/40 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200",
      suspicious: "bg-amber-500/15 border-amber-500/40 text-amber-700 dark:bg-amber-500/20 dark:text-amber-200",
      fail: "bg-rose-500/15 border-rose-500/40 text-rose-700 dark:bg-rose-500/20 dark:text-rose-200",
    }[columnId]

    return (
      <div
        key={action.id}
        className={cn(
          "group relative flex flex-col rounded-xl border border-border/60 bg-card/90 p-4 shadow-sm transition-shadow duration-200 hover:shadow-md",
          columnTone,
        )}
      >
        <div className="space-y-3">
          <div className="flex flex-col gap-2.5 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0 space-y-1.5">
              <h3 className="text-sm font-semibold leading-snug text-foreground line-clamp-2">
                {primaryName}
              </h3>
            </div>
            <div className="flex flex-col items-start gap-1 text-left sm:items-end sm:text-right">
              <span className={cn("flex items-center gap-1 text-sm font-medium", statusMeta.textClass)}>
                <StatusIcon className="h-4 w-4" />
                {statusMeta.label}
              </span>
              {relativeTime && <span className="text-xs text-muted-foreground">Updated {relativeTime}</span>}
            </div>
          </div>

          <div className="grid gap-x-6 gap-y-3 text-sm text-foreground sm:grid-cols-2">
            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Sender</p>
              <p className="text-foreground">{originator}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Beneficiary</p>
              <p className="text-foreground">{beneficiary}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Amount</p>
              <p className="font-semibold">{amountDisplay}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Payment Reference</p>
              <p className="text-muted-foreground">{action.payment_id || "—"}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Risk Level</p>
              <p className={cn("font-semibold", riskMeta.textClass)}>{riskMeta.label}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Risk Score</p>
              <p className="text-foreground">{formattedRiskScore ?? "—"}</p>
            </div>
            <div className="space-y-1">
              <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Last Action</p>
              <p className="text-xs text-muted-foreground">{formattedTimestamp || "—"}</p>
            </div>
            <div className="flex flex-col items-start space-y-1 pl-0">
              <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Action Taken</p>
              {actionTaken ? (
                <Badge
                  variant="outline"
                  className={cn("self-start px-2 py-0.5 text-xs font-medium", actionBadgeTone)}
                >
                  {actionTaken}
                </Badge>
              ) : (
                <span className="self-start text-xs text-muted-foreground">No action recorded</span>
              )}
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="flex flex-col h-screen overflow-hidden">
        <header className="flex h-16 shrink-0 items-center gap-2 border-b border-border/40 bg-background/90 px-4 transition-[width,height] ease-linear backdrop-blur supports-[backdrop-filter]:bg-background/70 group-has-[[data-collapsible=icon]]/sidebar-wrapper:h-12">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 hidden h-4 sm:inline-flex" />
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
        </header>

        <div className="border-b border-border/40 bg-background/80 px-6 py-4 shadow-[inset_0_-1px_0_rgba(15,23,42,0.04)] backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-3">
                  <h1 className="text-2xl font-semibold leading-tight tracking-tight">Actions Board</h1>
                </div>
                <p className="text-sm text-muted-foreground">
                  {loading
                    ? "Loading actions..."
                    : `Showing ${filteredActions.length} of ${actions.length} ${
                        actions.length === 1 ? "action" : "actions"
                      }`}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Select value={dateFilter} onValueChange={setDateFilter}>
                  <SelectTrigger size="sm" className="min-w-[160px]">
                    <SelectValue placeholder="Date" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Dates</SelectItem>
                    <SelectItem value="24h">Last 24 hours</SelectItem>
                    <SelectItem value="7d">Last 7 days</SelectItem>
                    <SelectItem value="30d">Last 30 days</SelectItem>
                  </SelectContent>
                </Select>
                <div className="relative flex min-w-[220px] flex-1 md:w-64 lg:w-72">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={searchTerm}
                    onChange={(event) => setSearchTerm(event.target.value)}
                    placeholder="Search by sender name"
                    className="pl-9 text-sm"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-1 flex-col overflow-hidden">
          {loading ? (
            <div className="flex h-full gap-4 overflow-x-auto px-2 pb-6 pt-4 md:gap-5 md:px-6">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="flex h-full min-h-[360px] min-w-[260px] flex-1 basis-[clamp(280px,32vw,380px)] flex-col rounded-xl border border-border/60 bg-card p-4 shadow-sm"
                >
                  <div className="mb-4 flex items-center gap-3">
                    <Skeleton className="h-10 w-10 rounded-full" />
                    <div className="flex flex-col gap-2">
                      <Skeleton className="h-3 w-24 rounded-full" />
                      <Skeleton className="h-2.5 w-32 rounded-full" />
                    </div>
                    <Skeleton className="ml-auto h-6 w-10 rounded-full" />
                  </div>
                  <div className="flex-1 space-y-3">
                    {[1, 2, 3].map((card) => (
                      <Skeleton key={card} className="h-24 rounded-2xl" />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : error ? (
            <Card className="mx-6 my-4 border-red-300 dark:border-red-800">
              <CardHeader>
                <CardTitle className="text-red-600 dark:text-red-400">Error Loading Actions</CardTitle>
                <CardDescription>{error}</CardDescription>
              </CardHeader>
            </Card>
          ) : actions.length === 0 ? (
            <div className="mx-auto flex max-w-2xl flex-1 flex-col items-center justify-center gap-5 px-6 text-center">
              <div className="flex size-28 items-center justify-center rounded-full border border-dashed border-slate-300/70 bg-white/70 text-muted-foreground shadow-sm dark:border-slate-800 dark:bg-slate-950/40">
                <ShieldCheck className="h-12 w-12 text-slate-400 dark:text-slate-600" />
              </div>
              <div className="space-y-2">
                <h2 className="text-xl font-semibold tracking-tight">No actions to show (yet)</h2>
                <p className="text-sm text-muted-foreground">
                  As analysts take action on flagged transactions, this board will update automatically.
                </p>
              </div>
            </div>
          ) : filteredActions.length === 0 ? (
            <div className="mx-auto flex max-w-xl flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
              <div className="rounded-3xl border border-dashed border-slate-300/70 bg-white/70 px-6 py-5 text-sm text-muted-foreground shadow-sm dark:border-slate-700 dark:bg-slate-950/40">
                No actions match the current filters. Try widening your search or clearing the filters above.
              </div>
              <Button
                variant="ghost"
                className="gap-2 rounded-full px-4"
                onClick={() => {
                  setDateFilter("all")
                  setSearchTerm("")
                }}
              >
                Reset filters
              </Button>
            </div>
          ) : (
            <div className="relative flex h-full flex-col">
              <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.08),transparent_55%)] dark:bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.16),transparent_55%)]" />
              <div className="flex h-full gap-4 overflow-x-auto px-2 pb-6 pt-4 md:gap-5 md:px-6">
                {columns.map((column) => {
                  const columnActions = groupedByColumn[column.id] || {}
                  const sortedRiskLevels = Object.keys(columnActions)
                    .filter((riskLevel) => columnActions[riskLevel]?.length)
                    .sort((a, b) => {
                      const aIndex = threatLevelOrder.indexOf(a.toLowerCase())
                      const bIndex = threatLevelOrder.indexOf(b.toLowerCase())
                      const safeA = aIndex === -1 ? threatLevelOrder.length : aIndex
                      const safeB = bIndex === -1 ? threatLevelOrder.length : bIndex
                      return safeA - safeB
                    })
                  const totalCount = Object.values(columnActions).reduce((sum, arr) => sum + arr.length, 0)
                  const Icon = column.icon
                  const hasActions = sortedRiskLevels.length > 0

                  return (
                    <div
                      key={column.id}
                      className="flex h-full min-h-0 min-w-[260px] flex-1 basis-[clamp(280px,32vw,380px)] flex-col"
                    >
                      <div className="group/column relative flex h-full min-h-[360px] flex-col overflow-hidden rounded-xl border border-border/60 bg-card px-3 pb-3 pt-2.5">
                        <div className="sticky top-0 z-10 -mx-3 -mt-2.5 flex items-center gap-3 border-b border-border/60 bg-card px-3 py-3">
                          <span
                            className={cn(
                              "flex size-10 items-center justify-center rounded-full",
                              column.iconBg,
                              column.iconTint,
                            )}
                          >
                            <Icon className="h-5 w-5" />
                          </span>
                          <div className="flex flex-1 flex-col">
                            <span className="text-sm font-semibold text-foreground">{column.title}</span>
                            <span className="text-xs text-muted-foreground">
                              {totalCount} {totalCount === 1 ? "action" : "actions"}
                            </span>
                          </div>
                          <Badge variant="secondary" className="rounded-full px-2 py-0.5 text-[11px] font-semibold">
                            {totalCount}
                          </Badge>
                        </div>
                        <div className="flex-1 overflow-y-auto px-1 pb-2 pt-4">
                          {hasActions ? (
                            <div className="space-y-4">
                              {sortedRiskLevels.map((riskLevel) => (
                                <div key={riskLevel} className="space-y-2.5">
                                  {columnActions[riskLevel].map((action) => renderActionCard(action, column.id))}
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="flex h-full min-h-[220px] flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border/60 bg-card/70 p-6 text-center text-sm text-muted-foreground">
                              <span>No actions in this stage yet.</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
