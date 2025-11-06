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
import { Badge } from "@/components/ui/badge"
import { RefreshCw, Shield, CheckCircle, XCircle, AlertCircle, Download, ChevronDown, Check } from "lucide-react"
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

const SMALL_WORDS = new Set([
  "and",
  "or",
  "for",
  "the",
  "a",
  "an",
  "of",
  "to",
  "with",
  "in",
  "on",
  "at",
  "by",
  "from",
  "into",
  "onto",
  "as",
  "vs",
  "per",
  "than",
  "over",
  "under",
])

const ACRONYM_WORDS: Record<string, string> = {
  aml: "AML",
  cft: "CFT",
  edd: "EDD",
  ctr: "CTR",
  str: "STR",
  fatf: "FATF",
  mas: "MAS",
  kyc: "KYC",
}

const normalizeWhitespace = (value: string) => value.replace(/\s+/g, " ").trim()

const splitWords = (value: string) =>
  value
    .replace(/[_\u2013\u2014-]/g, " ")
    .split(" ")
    .filter(Boolean)

const isAcronym = (value: string) => {
  const lettersOnly = value.replace(/[^A-Za-z]/g, "")
  return lettersOnly.length > 1 && lettersOnly === lettersOnly.toUpperCase()
}

const formatToTitleCase = (value: string) => {
  const words = splitWords(value)
  if (words.length === 0) {
    return ""
  }

  return words
    .map((word, index) => {
      if (isAcronym(word)) {
        return word
      }
      const lower = word.toLowerCase()
      if (ACRONYM_WORDS[lower]) {
        return ACRONYM_WORDS[lower]
      }
      if (index !== 0 && SMALL_WORDS.has(lower)) {
        return lower
      }
      return lower.charAt(0).toUpperCase() + lower.slice(1)
    })
    .join(" ")
}

const formatDisplayList = (items: string[]) => {
  if (items.length === 0) {
    return ""
  }
  if (items.length === 1) {
    return items[0]
  }
  if (items.length === 2) {
    return `${items[0]} and ${items[1]}`
  }
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`
}

const asString = (value: unknown): string | undefined => {
  if (typeof value === "string") {
    const trimmed = value.trim()
    return trimmed.length ? trimmed : undefined
  }
  if (typeof value === "number" && !Number.isNaN(value)) {
    return String(value)
  }
  return undefined
}

const asNumber = (value: unknown): number | undefined => {
  if (typeof value === "number" && !Number.isNaN(value)) {
    return value
  }
  if (typeof value === "string") {
    const parsed = Number(value.replace(/,/g, ""))
    return Number.isNaN(parsed) ? undefined : parsed
  }
  return undefined
}

const asStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .map((item) => {
      if (typeof item === "string") {
        const trimmed = item.trim()
        return trimmed.length ? trimmed : undefined
      }
      if (typeof item === "number" && !Number.isNaN(item)) {
        return String(item)
      }
      return undefined
    })
    .filter((item): item is string => Boolean(item))
}

const getDetailString = (details: Record<string, unknown>, keys: string[]) => {
  for (const key of keys) {
    const value = asString(details[key])
    if (value) {
      return value
    }
  }
  return undefined
}

const getDetailNumber = (details: Record<string, unknown>, keys: string[]) => {
  for (const key of keys) {
    const value = asNumber(details[key])
    if (value !== undefined) {
      return value
    }
  }
  return undefined
}

const getDetailList = (details: Record<string, unknown>, keys: string[]) => {
  for (const key of keys) {
    const list = asStringArray(details[key])
    if (list.length) {
      return list
    }
  }
  return []
}

const formatNumberValue = (value: number) =>
  new Intl.NumberFormat("en-US", {
    maximumFractionDigits: Number.isInteger(value) ? 0 : 2,
  }).format(value)

const finalizeTitle = (title: string) => {
  let cleaned = normalizeWhitespace(title)

  if (!cleaned) {
    return ""
  }

  cleaned = cleaned.replace(/\s*([,:;])\s*/g, "$1 ").trim()

  const words = cleaned.split(" ")
  if (words.length > 12) {
    cleaned = words.slice(0, 12).join(" ").replace(/[,:;]+$/, "")
    cleaned += "…"
  }

  if (cleaned.length > 90) {
    cleaned = cleaned.slice(0, 87).replace(/\s\S*$/, "")
    cleaned = cleaned.replace(/[,:;]+$/, "")
    cleaned += "…"
  }

  return cleaned || "Compliance Rule"
}

const DEADLINE_VERB_TO_NOUN: Record<string, string> = {
  provide: "Provision of",
  submit: "Submission of",
  furnish: "Furnishing of",
  file: "Filing of",
  report: "Reporting of",
  notify: "Notification to",
  deliver: "Delivery of",
  disclose: "Disclosure of",
  obtain: "Obtaining of",
  maintain: "Maintenance of",
  retain: "Retention of",
  ensure: "Ensuring of",
  conduct: "Conduct of",
  perform: "Performance of",
  escalate: "Escalation of",
  implement: "Implementation of",
  keep: "Keeping of",
  verify: "Verification of",
  review: "Review of",
}

const simplifyObjectPhrase = (phrase: string | undefined) => {
  if (!phrase) {
    return ""
  }

  let simplified = normalizeWhitespace(phrase)
  simplified = simplified.replace(/^(?:the|a|an)\s+/i, "")
  simplified = simplified.replace(/set out in [^,.;]+/gi, "")
  simplified = simplified.replace(/as set out in [^,.;]+/gi, "")
  simplified = simplified.replace(/as required under [^,.;]+/gi, "")
  simplified = simplified.replace(/pursuant to [^,.;]+/gi, "")
  simplified = simplified.replace(/in accordance with [^,.;]+/gi, "")
  simplified = simplified.replace(/paragraph\s+\w+(?:\.\w+)*/gi, "")
  simplified = simplified.replace(/subparagraph\s+\w+(?:\.\w+)*/gi, "")
  simplified = simplified.replace(/clause\s+\w+(?:\.\w+)*/gi, "")
  simplified = simplified.replace(/for such information/gi, "for information")
  simplified = simplified.replace(
    /value transfer originator information and value transfer beneficiary information/gi,
    "Transfer Information"
  )
  simplified = simplified.replace(/value transfer (?:originator|beneficiary) information/gi, "Transfer Information")
  simplified = simplified.replace(/\s{2,}/g, " ").trim()
  simplified = simplified.replace(/^(?:such|that)\s+/i, "")
  return simplified
}

const convertVerbPhraseToNounTitle = (phrase: string | undefined) => {
  if (!phrase) {
    return ""
  }

  let trimmed = normalizeWhitespace(phrase)
  trimmed = trimmed.replace(
    /^(?:the\s+(?:institution|bank|ordering institution)|a\s+bank|financial\s+institution)\s+(?:shall|must|should)\s+/i,
    ""
  )
  trimmed = trimmed.replace(/^(?:shall|must|should)\s+/i, "")
  trimmed = trimmed.replace(/^(?:ensure that\s+)/i, "ensure ")
  trimmed = trimmed.replace(/^(?:to\s+)/i, "")

  const words = trimmed.split(" ")
  const verb = words[0]?.toLowerCase() ?? ""
  const rest = words.slice(1).join(" ").trim()

  const mapped = DEADLINE_VERB_TO_NOUN[verb]
  if (mapped) {
    const object = simplifyObjectPhrase(rest)
    const objectTitle = object ? formatToTitleCase(object) : ""
    return `${mapped}${objectTitle ? ` ${objectTitle}` : ""}`.trim()
  }

  return formatToTitleCase(trimmed)
}

const formatTimeLabel = (label: string | undefined) => {
  if (!label) {
    return undefined
  }

  let cleaned = normalizeWhitespace(label)
  cleaned = cleaned.replace(/^(?:within|no later than|not later than|by)\s+/i, "")
  cleaned = cleaned.replace(/\b(\d+)\s*business day(s)?\b/gi, (_, num) => {
    const count = Number(num)
    return `${num} Business Day${count === 1 ? "" : "s"}`
  })
  cleaned = cleaned.replace(/\b(\d+)\s*calendar day(s)?\b/gi, (_, num) => {
    const count = Number(num)
    return `${num} Calendar Day${count === 1 ? "" : "s"}`
  })
  cleaned = cleaned.replace(/\b(\d+)\s*working day(s)?\b/gi, (_, num) => {
    const count = Number(num)
    return `${num} Working Day${count === 1 ? "" : "s"}`
  })
  cleaned = cleaned.replace(/\b(\d+)\s*day(s)?\b/gi, (_, num) => {
    const count = Number(num)
    return `${num} Day${count === 1 ? "" : "s"}`
  })

  return formatToTitleCase(cleaned)
}

const formatTriggerSegment = (text: string, keyword: string) => {
  let cleaned = normalizeWhitespace(text)
  cleaned = cleaned.replace(/^(?:a|an|the)\s+/i, "")
  cleaned = cleaned.replace(/\bsuch\s+/gi, "")
  cleaned = cleaned.replace(/\bfor such information\b/gi, "for information")
  cleaned = cleaned.replace(/\bby the\b/gi, "by")
  cleaned = cleaned.replace(/\bintermediary institution\b/gi, "Intermediary Institution")
  const title = formatToTitleCase(cleaned)
  if (!title) {
    return ""
  }

  if (keyword === "after") {
    return `After ${title}`
  }

  if (keyword === "upon" || keyword === "of") {
    return `Upon ${title}`
  }

  return `${formatToTitleCase(keyword)} ${title}`
}

const extractDeadlineTitleFromSource = (rule: ComplianceRule, timeLabel?: string) => {
  if (!rule.source_text) {
    return null
  }

  const match = rule.source_text.match(
    /\bshall\s+([^.,;]+?)(?:\s+within|\s+no later than|\s+not later than|\s+by)\s+([^.,;]+)/i
  )

  if (!match) {
    return null
  }

  const actionPhrase = match[1]
  const rawTime = match[2]
  const remainderIndex = (match.index ?? 0) + match[0].length
  const remainder = rule.source_text.slice(remainderIndex)
  const triggerMatch = remainder.match(/\b(of|after|upon)\s+([^.,;]+)/i)

  const actionTitle = convertVerbPhraseToNounTitle(actionPhrase)
  if (!actionTitle) {
    return null
  }

  const timeTitle = formatTimeLabel(timeLabel ?? rawTime)
  const triggerTitle = triggerMatch ? formatTriggerSegment(triggerMatch[2], triggerMatch[1].toLowerCase()) : ""

  const parts: string[] = [actionTitle]
  if (timeTitle) {
    parts.push(`Within ${timeTitle}`)
  }
  if (triggerTitle) {
    parts.push(triggerTitle)
  }

  return parts.join(" ")
}

const buildThresholdTitle = (rule: ComplianceRule): string | null => {
  const details = rule.rule_details
  if (!details) {
    return null
  }

  const detailRecord = details as Record<string, unknown>
  const amount = getDetailNumber(detailRecord, ["amount", "threshold_value", "threshold_amount"])
  const currency = getDetailString(detailRecord, ["currency"])
  const transactionType = getDetailString(detailRecord, ["transaction_type"])
  const appliesTo = getDetailList(detailRecord, ["applies_to"])
  const conditions = getDetailList(detailRecord, ["conditions"])

  if (
    amount === undefined &&
    !currency &&
    !transactionType &&
    appliesTo.length === 0 &&
    conditions.length === 0
  ) {
    return null
  }

  const amountText =
    amount !== undefined ? `${currency ? `${currency.toUpperCase()} ` : ""}${formatNumberValue(amount)}` : ""
  const transactionLabel = formatToTitleCase(transactionType ?? "Transactions")
  const audience = appliesTo.length
    ? formatToTitleCase(formatDisplayList(appliesTo.slice(0, 2).map((item) => item.replace(/[_-]/g, " "))))
    : ""
  const condition = conditions.length
    ? formatToTitleCase(conditions[0].replace(/[_-]/g, " "))
    : ""

  const audienceText = audience ? ` for ${audience}` : ""
  const amountSegment = amountText ? ` Over ${amountText}` : ""
  const conditionSegment = !amountText && condition ? ` When ${condition}` : ""

  const title = `${transactionLabel}${audienceText}${amountSegment || conditionSegment}`
    .replace(/\s{2,}/g, " ")
    .trim()

  if (!title) {
    return null
  }

  const ensured = title.toLowerCase().includes("threshold") ? title : `${title} Threshold`
  return finalizeTitle(ensured)
}

const buildDeadlineTitle = (rule: ComplianceRule): string | null => {
  const details = rule.rule_details
  if (!details) {
    return null
  }

  const detailRecord = details as Record<string, unknown>
  const deadlineDays = getDetailNumber(detailRecord, ["deadline_days"])
  const deadlineBusinessDays =
    typeof detailRecord["deadline_business_days"] === "boolean"
      ? (detailRecord["deadline_business_days"] as boolean)
      : undefined
  const triggerEvent = getDetailString(detailRecord, ["trigger_event"])
  const timeLabel =
    deadlineDays !== undefined
      ? `${deadlineDays} ${deadlineBusinessDays ? "Business Days" : "Days"}`
      : getDetailString(detailRecord, ["deadline_text"])

  const sourceDerived = extractDeadlineTitleFromSource(rule, timeLabel)
  if (sourceDerived) {
    return finalizeTitle(sourceDerived)
  }

  const filingType = getDetailString(detailRecord, ["filing_type"])
  const actionPhrase =
    filingType && filingType.toLowerCase() !== "other"
      ? filingType
      : rule.description || getDetailString(detailRecord, ["requirement", "action"]) || ""

  if (!actionPhrase && !timeLabel && !triggerEvent) {
    return null
  }

  const actionTitle = convertVerbPhraseToNounTitle(actionPhrase) || "Compliance Deadline"
  const formattedTime = formatTimeLabel(timeLabel)
  const defaultTriggerKeyword = triggerEvent && /request/i.test(triggerEvent) ? "upon" : "after"
  const triggerTitle = triggerEvent ? formatTriggerSegment(triggerEvent, defaultTriggerKeyword) : ""

  const parts: string[] = [actionTitle]
  if (formattedTime) {
    parts.push(`Within ${formattedTime}`)
  }
  if (!formattedTime && deadlineDays !== undefined) {
    const fallbackTime = formatTimeLabel(`${deadlineDays} ${deadlineBusinessDays ? "Business Days" : "Days"}`)
    if (fallbackTime) {
      parts.push(`Within ${fallbackTime}`)
    }
  }
  if (triggerTitle) {
    parts.push(triggerTitle)
  }

  return finalizeTitle(parts.join(" "))
}

const buildEddTitle = (rule: ComplianceRule): string | null => {
  const details = rule.rule_details
  if (!details) {
    return null
  }

  const detailRecord = details as Record<string, unknown>
  const category = getDetailString(detailRecord, ["trigger_category"])
  const relationships = getDetailList(detailRecord, ["relationship_types"])
  const measures = getDetailList(detailRecord, ["enhanced_measures"])
  const approvals = getDetailList(detailRecord, ["required_approvals"])
  const pepTier = getDetailString(detailRecord, ["pep_tier"])

  if (!category && relationships.length === 0 && measures.length === 0 && approvals.length === 0 && !pepTier) {
    return null
  }

  const categoryMap: Record<string, string> = {
    pep: "PEP Relationships",
    high_risk_jurisdiction: "High-Risk Jurisdictions",
    high_risk_customer: "High-Risk Customers",
    complex_structure: "Complex Structures",
    unusual_activity: "Unusual Activity",
  }

  const categoryLabel = category ? categoryMap[category.toLowerCase()] ?? formatToTitleCase(category) : ""
  const relationshipsLabel = relationships.length
    ? formatToTitleCase(
        formatDisplayList(relationships.slice(0, 2).map((item) => item.replace(/[_-]/g, " ")))
      )
    : ""
  const highlight = approvals[0] ?? measures[0]
  const highlightLabel = highlight ? formatToTitleCase(highlight.replace(/[_-]/g, " ")) : "Enhanced Measures"
  const pepQualifier = pepTier ? ` (${formatToTitleCase(pepTier.replace(/[_-]/g, " "))})` : ""

  let title = "EDD"
  if (relationshipsLabel || categoryLabel) {
    title += ` for ${relationshipsLabel || categoryLabel}`
  }
  title += pepQualifier
  if (highlightLabel) {
    title += ` Requiring ${highlightLabel}`
  }

  return finalizeTitle(title.trim())
}

const buildSanctionsTitle = (rule: ComplianceRule): string | null => {
  const details = rule.rule_details
  if (!details) {
    return null
  }

  const detailRecord = details as Record<string, unknown>
  const sanctionsList = getDetailString(detailRecord, ["sanctions_list"])
  const frequency = getDetailString(detailRecord, ["screening_frequency"])
  const appliesTo = getDetailList(detailRecord, ["applies_to"])
  const matchThreshold = getDetailNumber(detailRecord, ["match_threshold"])

  if (!sanctionsList && !frequency && appliesTo.length === 0 && matchThreshold === undefined) {
    return null
  }

  const frequencyMap: Record<string, string> = {
    real_time: "Real-Time",
    daily: "Daily",
    weekly: "Weekly",
    onboarding_only: "At Onboarding",
  }

  const parts = [`${formatToTitleCase(sanctionsList ?? "Sanctions")} Screening`]

  if (frequency) {
    parts.push(frequencyMap[frequency.toLowerCase()] ?? formatToTitleCase(frequency))
  }

  if (appliesTo.length) {
    parts.push(
      `for ${formatToTitleCase(
        formatDisplayList(appliesTo.slice(0, 2).map((item) => item.replace(/[_-]/g, " ")))
      )}`
    )
  }

  if (matchThreshold !== undefined) {
    parts.push(`at ${Math.round(matchThreshold * 100)}% Match Threshold`)
  }

  if (!parts.length) {
    return null
  }

  return finalizeTitle(parts.join(" ").replace(/\s{2,}/g, " ").trim())
}

const buildRecordKeepingTitle = (rule: ComplianceRule): string | null => {
  const details = rule.rule_details
  if (!details) {
    return null
  }

  const detailRecord = details as Record<string, unknown>
  const recordType = getDetailString(detailRecord, ["record_type"])
  const retention = getDetailNumber(detailRecord, ["retention_period_years"])
  const storageRequirements = getDetailList(detailRecord, ["storage_requirements"])

  if (!recordType && retention === undefined && storageRequirements.length === 0) {
    return null
  }

  const typeLabel = formatToTitleCase(recordType ?? "Records")
  const retentionLabel =
    retention !== undefined ? `${retention} Year${retention === 1 ? "" : "s"} Retention` : "Retention"
  const storageLabel = storageRequirements.length
    ? `(${formatToTitleCase(storageRequirements[0].replace(/[_-]/g, " "))})`
    : ""

  return finalizeTitle([typeLabel, retentionLabel, storageLabel].filter(Boolean).join(" ").trim())
}

const isCategoryLabel = (label: string, ruleType: string) => {
  const comparable = label.toLowerCase().replace(/[^a-z0-9]/g, "")
  const comparableType = ruleType.toLowerCase().replace(/[^a-z0-9]/g, "")
  return (
    comparable === comparableType ||
    comparable === `${comparableType}rule` ||
    comparable.endsWith("rule") && comparable.slice(0, -4) === comparableType
  )
}

const summarizeSourceText = (text: string | undefined): string | null => {
  if (!text) {
    return null
  }

  let cleaned = normalizeWhitespace(text)
  if (!cleaned) {
    return null
  }

  if (/digital token/i.test(cleaned) && /entity other than/i.test(cleaned)) {
    return finalizeTitle("Digital Token Transfers to Non-Supervised Entities Require Enhanced Mitigation")
  }

  cleaned = cleaned.replace(/^[\(\[\dA-Za-z]+\)\s]+/, "")
  cleaned = cleaned.replace(/\b(?:a|an|the)\s+(?:bank|financial institution|financial institutions|institution|reporting institution|dealer|company|firm|service provider|payment institution|licensee)s?\s+(?:shall|must|should|are required to|is required to|needs to|will)\s+/i, "")
  cleaned = cleaned.replace(/\b(?:shall|must|should|are required to|is required to|needs to|will)\s+/i, "")
  cleaned = cleaned.replace(/\btransfer of a ([^ ]+ )?digital token to or a receipt of a ([^ ]+ )?digital token from\b/gi, "digital token transfers with")
  cleaned = cleaned.replace(/\ban entity other than\b/gi, "entities other than")
  cleaned = cleaned.replace(/\bwhere\b/gi, "for")
  cleaned = cleaned.replace(/\bwith respect to\b/gi, "for")
  cleaned = cleaned.replace(/\bin respect of\b/gi, "for")
  cleaned = cleaned.replace(/\s*:\s*\(a\).*$/i, "")
  cleaned = cleaned.replace(/\((?:[^()]{0,80})\)/g, "")
  cleaned = cleaned.replace(/\s{2,}/g, " ").trim()

  const firstSentence = cleaned.split(/(?<=[.!?])\s+/)[0] || cleaned
  let candidate = firstSentence.replace(/[.!?,"']+$/, "").trim()

  if (!candidate) {
    return null
  }

  if (/^perform\b/i.test(candidate)) {
    candidate = candidate.replace(/^perform\b/i, "Enhanced")
  }

  candidate = candidate.replace(/\brisk mitigation measures\b/gi, "risk mitigation")

  if (candidate.length > 140) {
    candidate = candidate.slice(0, 137).trimEnd()
    candidate = candidate.replace(/[,:;]$/, "")
    candidate += "…"
  }

  return finalizeTitle(formatToTitleCase(candidate))
}

const buildTitleFromDetails = (rule: ComplianceRule): string | null => {
  const normalizedType = rule.rule_type?.toLowerCase() ?? ""
  if (!rule.rule_details || Object.keys(rule.rule_details).length === 0) {
    return null
  }

  if (
    ["threshold", "transaction_amount_threshold", "cash_transaction_threshold"].some((type) =>
      normalizedType.includes(type)
    )
  ) {
    return buildThresholdTitle(rule)
  }

  if (normalizedType.includes("deadline")) {
    return buildDeadlineTitle(rule)
  }

  if (normalizedType.includes("edd")) {
    return buildEddTitle(rule)
  }

  if (normalizedType.includes("sanctions")) {
    return buildSanctionsTitle(rule)
  }

  if (normalizedType.includes("record") || normalizedType.includes("retention")) {
    return buildRecordKeepingTitle(rule)
  }

  return null
}

const CATEGORY_COLOR_MAP: Record<string, string> = {
  threshold: "bg-blue-500/15 text-blue-700 dark:text-blue-300 border-transparent",
  deadline: "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-transparent",
  edd_trigger: "bg-purple-500/15 text-purple-700 dark:text-purple-300 border-transparent",
  sanctions: "bg-rose-500/15 text-rose-700 dark:text-rose-300 border-transparent",
  record_keeping: "bg-slate-500/15 text-slate-700 dark:text-slate-300 border-transparent",
  transaction_amount_threshold: "bg-blue-500/15 text-blue-700 dark:text-blue-300 border-transparent",
  cash_transaction_threshold: "bg-blue-500/15 text-blue-700 dark:text-blue-300 border-transparent",
  sanctions_screening: "bg-rose-500/15 text-rose-700 dark:text-rose-300 border-transparent",
  high_risk_jurisdiction: "bg-orange-500/15 text-orange-700 dark:text-orange-300 border-transparent",
  pep_screening: "bg-purple-500/15 text-purple-700 dark:text-purple-300 border-transparent",
  currency_restriction: "bg-teal-500/15 text-teal-700 dark:text-teal-300 border-transparent",
  default: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-transparent",
}

const getCategoryColorClass = (category: string) => {
  const key = category.toLowerCase()
  return CATEGORY_COLOR_MAP[key] || CATEGORY_COLOR_MAP.default
}

const getRuleTags = (rule: ComplianceRule) => {
  const tags = new Set<string>()
  if (rule.rule_type) {
    tags.add(rule.rule_type)
  }
  return Array.from(tags)
}

const getRuleTimestamp = (rule: ComplianceRule) => {
  const dateSource = rule.updated_at || rule.created_at || rule.effective_date
  if (!dateSource) {
    return 0
  }

  const timestamp = new Date(dateSource).getTime()
  return Number.isNaN(timestamp) ? 0 : timestamp
}

const isWithinDateRange = (rule: ComplianceRule, range: string) => {
  if (range === "all") {
    return true
  }

  const timestamp = getRuleTimestamp(rule)
  if (!timestamp) {
    return false
  }

  const now = Date.now()
  const diffMs = now - timestamp
  const dayMs = 1000 * 60 * 60 * 24

  switch (range) {
    case "24h":
      return diffMs <= dayMs
    case "7d":
      return diffMs <= dayMs * 7
    case "30d":
      return diffMs <= dayMs * 30
    case "90d":
      return diffMs <= dayMs * 90
    default:
      return true
  }
}

const buildTitleFromTextualSources = (rule: ComplianceRule): string | null => {
  const details = rule.rule_details as Record<string, unknown> | undefined
  const detailTitle = details && typeof details["title"] === "string" ? (details["title"] as string) : undefined
  const detailSummary =
    details && typeof details["summary"] === "string" ? (details["summary"] as string) : undefined

  const description =
    rule.description && !isCategoryLabel(rule.description, rule.rule_type) ? rule.description : undefined

  const candidates = [detailTitle, detailSummary, description, rule.source_text]
    .filter((value): value is string => Boolean(value && value.trim()))

  for (const text of candidates) {
    const title = summarizeSourceText(text)
    if (title) {
      return title
    }
  }

  return null
}

const getRuleTitle = (rule: ComplianceRule) => {
  const detailedTitle = buildTitleFromDetails(rule)
  if (detailedTitle) {
    return detailedTitle
  }

  const textualTitle = buildTitleFromTextualSources(rule)
  if (textualTitle) {
    return finalizeTitle(textualTitle)
  }

  const description =
    rule.description && !isCategoryLabel(rule.description, rule.rule_type) ? rule.description : undefined
  if (description) {
    return finalizeTitle(formatToTitleCase(description))
  }

  const readableType = formatToTitleCase(rule.rule_type || "Rule")
  return finalizeTitle(readableType || "Compliance Rule")
}

export default function RulesPage() {
  const [isGenerating, setIsGenerating] = useState(false)
  const [rules, setRules] = useState<ComplianceRule[]>([])
  const [isLoadingRules, setIsLoadingRules] = useState(false)
  const [lastExtractionResult, setLastExtractionResult] = useState<BatchExtractionResponse | null>(null)
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([])
  const [expandedPendingRules, setExpandedPendingRules] = useState<Set<string>>(new Set())
  const [approvingRules, setApprovingRules] = useState<Set<string>>(new Set())
  const [confidenceAnalysis, setConfidenceAnalysis] = useState<Record<string, { reason: string; questions: string[]; tier: string }>>({})
  const [loadingConfidenceAnalysis, setLoadingConfidenceAnalysis] = useState<Set<string>>(new Set())

  // Filter states for current rules
  const [filterRuleType, setFilterRuleType] = useState<string>('all')
  const [filterJurisdiction, setFilterJurisdiction] = useState<string>('all')
  const [filterRegulator, setFilterRegulator] = useState<string>('all')
  const [ruleDateRange, setRuleDateRange] = useState<string>('all')

  // Filter states for pending rules
  const [pendingFilterRuleType, setPendingFilterRuleType] = useState<string>('all')
  const [pendingFilterJurisdiction, setPendingFilterJurisdiction] = useState<string>('all')
  const [pendingFilterRegulator, setPendingFilterRegulator] = useState<string>('all')
  const [pendingDateRange, setPendingDateRange] = useState<string>('all')

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

  const togglePendingRule = async (ruleId: string) => {
    setExpandedPendingRules(prev => {
      const newSet = new Set(prev)
      if (newSet.has(ruleId)) {
        newSet.delete(ruleId)
      } else {
        newSet.add(ruleId)
        // Load confidence analysis if not already loaded
        if (!confidenceAnalysis[ruleId]) {
          loadConfidenceAnalysis(ruleId)
        }
      }
      return newSet
    })
  }

  const loadConfidenceAnalysis = async (ruleId: string) => {
    setLoadingConfidenceAnalysis(prev => new Set(prev).add(ruleId))
    try {
      const analysis = await api.getConfidenceAnalysis(ruleId)
      if (analysis.has_low_confidence) {
        setConfidenceAnalysis(prev => ({
          ...prev,
          [ruleId]: {
            reason: analysis.reason || 'Confidence level requires additional review.',
            questions: analysis.questions || [],
            tier: analysis.tier || 'moderate'
          }
        }))
      } else {
        // Even if not low confidence, store empty analysis to prevent re-fetching
        setConfidenceAnalysis(prev => ({
          ...prev,
          [ruleId]: {
            reason: '',
            questions: [],
            tier: 'high'
          }
        }))
      }
    } catch (error) {
      console.error('Failed to load confidence analysis:', error)
      toast.error('Failed to load confidence analysis', {
        description: 'Please try expanding the rule again.'
      })
    } finally {
      setLoadingConfidenceAnalysis(prev => {
        const newSet = new Set(prev)
        newSet.delete(ruleId)
        return newSet
      })
    }
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
    const types = new Set(
      rules
        .filter(r => r.validation_status === 'validated' && r.rule_type)
        .map(r => r.rule_type)
    )
    return Array.from(types).sort()
  }

  const getUniqueJurisdictions = () => {
    const jurisdictions = new Set(
      rules
        .filter(r => r.validation_status === 'validated' && r.jurisdiction)
        .map(r => r.jurisdiction)
    )
    return Array.from(jurisdictions).sort()
  }

  const getUniqueRegulators = () => {
    const regulators = new Set(
      rules
        .filter(r => r.validation_status === 'validated' && r.regulator)
        .map(r => r.regulator)
    )
    return Array.from(regulators).sort()
  }

  // Filter rules
  const getFilteredRules = () => {
    return rules
      .filter(r => r.validation_status === 'validated')
      .filter(r => filterRuleType === 'all' || r.rule_type === filterRuleType)
      .filter(r => filterJurisdiction === 'all' || r.jurisdiction === filterJurisdiction)
      .filter(r => filterRegulator === 'all' || r.regulator === filterRegulator)
      .filter(r => isWithinDateRange(r, ruleDateRange))
      .sort((a, b) => getRuleTimestamp(b) - getRuleTimestamp(a))
  }

  const clearFilters = () => {
    setFilterRuleType('all')
    setFilterJurisdiction('all')
    setFilterRegulator('all')
    setRuleDateRange('all')
  }

  // Get unique values for pending filters
  const getUniquePendingRuleTypes = () => {
    const types = new Set(
      rules
        .filter(r => r.validation_status === 'pending' && r.rule_type)
        .map(r => r.rule_type)
    )
    return Array.from(types).sort()
  }

  const getUniquePendingJurisdictions = () => {
    const jurisdictions = new Set(
      rules
        .filter(r => r.validation_status === 'pending' && r.jurisdiction)
        .map(r => r.jurisdiction)
    )
    return Array.from(jurisdictions).sort()
  }

  const getUniquePendingRegulators = () => {
    const regulators = new Set(
      rules
        .filter(r => r.validation_status === 'pending' && r.regulator)
        .map(r => r.regulator)
    )
    return Array.from(regulators).sort()
  }

  // Filter pending rules
  const getFilteredPendingRules = () => {
    return rules
      .filter(r => r.validation_status === 'pending')
      .filter(r => pendingFilterRuleType === 'all' || r.rule_type === pendingFilterRuleType)
      .filter(r => pendingFilterJurisdiction === 'all' || r.jurisdiction === pendingFilterJurisdiction)
      .filter(r => pendingFilterRegulator === 'all' || r.regulator === pendingFilterRegulator)
      .filter(r => isWithinDateRange(r, pendingDateRange))
      .sort((a, b) => getRuleTimestamp(b) - getRuleTimestamp(a))
  }

  const clearPendingFilters = () => {
    setPendingFilterRuleType('all')
    setPendingFilterJurisdiction('all')
    setPendingFilterRegulator('all')
    setPendingDateRange('all')
  }

const handleTagFilter = (tag: string) => {
  setFilterRuleType(current => (current === tag ? 'all' : tag))
}

const handlePendingTagFilter = (tag: string) => {
  setPendingFilterRuleType(current => (current === tag ? 'all' : tag))
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
                    No compliance rules found. Click &quot;Generate Updated Rules&quot; to fetch the latest regulatory requirements.
                  </p>
                </div>
              ) : (
                <>
                  {/* Filter Section */}
                  <div className="flex flex-wrap items-center gap-3 w-full">
                    <Select value={ruleDateRange} onValueChange={setRuleDateRange}>
                      <SelectTrigger className="h-9 min-w-[160px] flex-1 sm:flex-none">
                        <SelectValue placeholder="All time" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Time</SelectItem>
                        <SelectItem value="24h">Last 24 Hours</SelectItem>
                        <SelectItem value="7d">Last 7 Days</SelectItem>
                        <SelectItem value="30d">Last 30 Days</SelectItem>
                        <SelectItem value="90d">Last 90 Days</SelectItem>
                      </SelectContent>
                    </Select>

                    <Select value={filterRuleType} onValueChange={setFilterRuleType}>
                      <SelectTrigger className="h-9 min-w-[160px] flex-1 sm:flex-none">
                        <SelectValue placeholder="All rule categories" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Rule Categories</SelectItem>
                        {getUniqueRuleTypes().map(type => (
                          <SelectItem key={type} value={type}>{formatToTitleCase(type)}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    <Select value={filterJurisdiction} onValueChange={setFilterJurisdiction}>
                      <SelectTrigger className="h-9 min-w-[160px] flex-1 sm:flex-none">
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
                      <SelectTrigger className="h-9 min-w-[160px] flex-1 sm:flex-none">
                        <SelectValue placeholder="All regulators" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Regulators</SelectItem>
                        {getUniqueRegulators().map(regulator => (
                          <SelectItem key={regulator} value={regulator}>{regulator}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    {(filterRuleType !== 'all' || filterJurisdiction !== 'all' || filterRegulator !== 'all' || ruleDateRange !== 'all') && (
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
                      getFilteredRules().map((rule) => {
                        const addedOn = rule.updated_at || rule.created_at || rule.effective_date
                        const addedOnDate = addedOn ? new Date(addedOn) : null
                        const addedOnLabel = addedOnDate && !Number.isNaN(addedOnDate.getTime())
                          ? addedOnDate.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
                          : null

                        return (
                          <div key={rule.id} className="rounded-lg border bg-card p-4">
                            <div className="flex items-start justify-between gap-4 mb-3">
                              <div className="flex flex-col gap-2">
                                <div className="flex items-start gap-2">
                                  <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
                                  <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                      <h4 className="font-semibold leading-tight">{getRuleTitle(rule)}</h4>
                                      {getRuleTags(rule).map(tag => {
                                        const isActive = filterRuleType === tag
                                        return (
                                          <Badge
                                            key={tag}
                                            variant={isActive ? "default" : "outline"}
                                            onClick={() => handleTagFilter(tag)}
                                            role="button"
                                            tabIndex={0}
                                            onKeyDown={(event) => {
                                              if (event.key === 'Enter' || event.key === ' ') {
                                                event.preventDefault()
                                                handleTagFilter(tag)
                                              }
                                            }}
                                            className={`cursor-pointer border ${getCategoryColorClass(tag)} ${isActive ? 'ring-1 ring-offset-1 ring-offset-background ring-primary/70' : ''}`}
                                          >
                                            {formatToTitleCase(tag)}
                                          </Badge>
                                        )
                                      })}
                                      {rule.jurisdiction && (
                                        <Badge
                                          variant="secondary"
                                          className="bg-green-500/15 text-green-700 dark:text-green-300 border border-green-500/40"
                                        >
                                          {rule.jurisdiction}
                                        </Badge>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              </div>
                              {addedOnLabel && (
                                <span className="text-xs text-muted-foreground whitespace-nowrap">
                                  Added {addedOnLabel}
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground mb-3">{rule.source_text}</p>
                            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                              <span>Regulator: {rule.regulator || 'Not specified'}</span>
                              {rule.circular_number && <span>• Circular: {rule.circular_number}</span>}
                              {rule.effective_date && (
                                <span>• Effective: {new Date(rule.effective_date).toLocaleDateString()}</span>
                              )}
                              {typeof rule.extraction_confidence === 'number' && !Number.isNaN(rule.extraction_confidence) && (
                                <span>• Confidence: {(rule.extraction_confidence * 100).toFixed(0)}%</span>
                              )}
                            </div>
                          </div>
                        )
                      })
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
                  <div className="flex flex-wrap items-center gap-3 w-full">
                    <Select value={pendingDateRange} onValueChange={setPendingDateRange}>
                      <SelectTrigger className="h-9 min-w-[160px] flex-1 sm:flex-none">
                        <SelectValue placeholder="All time" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Time</SelectItem>
                        <SelectItem value="24h">Last 24 Hours</SelectItem>
                        <SelectItem value="7d">Last 7 Days</SelectItem>
                        <SelectItem value="30d">Last 30 Days</SelectItem>
                        <SelectItem value="90d">Last 90 Days</SelectItem>
                      </SelectContent>
                    </Select>

                    <Select value={pendingFilterRuleType} onValueChange={setPendingFilterRuleType}>
                      <SelectTrigger className="h-9 min-w-[160px] flex-1 sm:flex-none">
                        <SelectValue placeholder="All rule categories" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Rule Categories</SelectItem>
                        {getUniquePendingRuleTypes().map(type => (
                          <SelectItem key={type} value={type}>{formatToTitleCase(type)}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    <Select value={pendingFilterJurisdiction} onValueChange={setPendingFilterJurisdiction}>
                      <SelectTrigger className="h-9 min-w-[160px] flex-1 sm:flex-none">
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
                      <SelectTrigger className="h-9 min-w-[160px] flex-1 sm:flex-none">
                        <SelectValue placeholder="All regulators" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Regulators</SelectItem>
                        {getUniquePendingRegulators().map(regulator => (
                          <SelectItem key={regulator} value={regulator}>{regulator}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    {(pendingFilterRuleType !== 'all' || pendingFilterJurisdiction !== 'all' || pendingFilterRegulator !== 'all' || pendingDateRange !== 'all') && (
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
                        const addedOn = rule.updated_at || rule.created_at || rule.effective_date
                        const addedOnDate = addedOn ? new Date(addedOn) : null
                        const addedOnLabel = addedOnDate && !Number.isNaN(addedOnDate.getTime())
                          ? addedOnDate.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
                          : null
                        const confidenceTier = rule.extraction_confidence < 0.80 ? 'low' :
                                              rule.extraction_confidence <= 0.95 ? 'moderate' : 'high'
                        const hasLowOrModerateConfidence = confidenceTier !== 'high'
                        const analysis = confidenceAnalysis[rule.id]
                        const isLoadingAnalysis = loadingConfidenceAnalysis.has(rule.id)

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
                                    <div className="flex-1 min-w-0 space-y-2">
                                      <div className="flex items-start justify-between gap-3">
                                        <div className="flex-1 min-w-0">
                                          <div className="flex flex-wrap items-center gap-2">
                                            <h4 className="font-semibold leading-tight">{getRuleTitle(rule)}</h4>
                                            {getRuleTags(rule).map(tag => {
                                              const isActive = pendingFilterRuleType === tag
                                              return (
                                                <Badge
                                                  key={tag}
                                                  variant={isActive ? "default" : "outline"}
                                                  onClick={() => handlePendingTagFilter(tag)}
                                                  role="button"
                                                  tabIndex={0}
                                                  onKeyDown={(event) => {
                                                    if (event.key === 'Enter' || event.key === ' ') {
                                                      event.preventDefault()
                                                      handlePendingTagFilter(tag)
                                                    }
                                                  }}
                                                  className={`cursor-pointer border ${getCategoryColorClass(tag)} ${isActive ? 'ring-1 ring-offset-1 ring-offset-background ring-primary/70' : ''}`}
                                                >
                                                  {formatToTitleCase(tag)}
                                                </Badge>
                                              )
                                            })}
                                            {rule.jurisdiction && (
                                              <Badge
                                                variant="secondary"
                                                className="bg-orange-500/15 text-orange-700 dark:text-orange-300 border border-orange-500/40"
                                              >
                                                {rule.jurisdiction}
                                              </Badge>
                                            )}
                                            {hasLowOrModerateConfidence && (
                                              <Badge
                                                variant="outline"
                                                className={
                                                  confidenceTier === 'low'
                                                    ? "bg-red-500/15 text-red-700 dark:text-red-300 border-red-500/40"
                                                    : "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/40"
                                                }
                                              >
                                                {confidenceTier === 'low' ? 'Low' : 'Moderate'} Confidence ({Math.round(rule.extraction_confidence * 100)}%)
                                              </Badge>
                                            )}
                                          </div>
                                        </div>
                                        {addedOnLabel && (
                                          <span className="text-xs text-muted-foreground whitespace-nowrap">
                                            Captured {addedOnLabel}
                                          </span>
                                        )}
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

                                {hasLowOrModerateConfidence && (
                                  <div className={`rounded-lg border p-4 space-y-3 ${
                                    confidenceTier === 'low'
                                      ? 'border-red-500/40 bg-red-50/50 dark:bg-red-950/20'
                                      : 'border-amber-500/40 bg-amber-50/50 dark:bg-amber-950/20'
                                  }`}>
                                    <div className="flex items-start gap-2">
                                      <AlertCircle className={`h-5 w-5 flex-shrink-0 mt-0.5 ${
                                        confidenceTier === 'low'
                                          ? 'text-red-600 dark:text-red-400'
                                          : 'text-amber-600 dark:text-amber-400'
                                      }`} />
                                      <div className="flex-1 space-y-3">
                                        {isLoadingAnalysis ? (
                                          <div className={`text-sm ${
                                            confidenceTier === 'low'
                                              ? 'text-red-800 dark:text-red-200'
                                              : 'text-amber-800 dark:text-amber-200'
                                          }`}>
                                            Loading confidence analysis...
                                          </div>
                                        ) : analysis ? (
                                          <>
                                            <div>
                                              <h5 className={`text-sm font-semibold mb-1 ${
                                                confidenceTier === 'low'
                                                  ? 'text-red-900 dark:text-red-100'
                                                  : 'text-amber-900 dark:text-amber-100'
                                              }`}>
                                                Why Confidence is {confidenceTier === 'low' ? 'Low' : 'Moderate'}
                                              </h5>
                                              <p className={`text-sm ${
                                                confidenceTier === 'low'
                                                  ? 'text-red-800 dark:text-red-200'
                                                  : 'text-amber-800 dark:text-amber-200'
                                              }`}>
                                                {analysis.reason}
                                              </p>
                                            </div>

                                            {analysis.questions && analysis.questions.length > 0 && (
                                              <div>
                                                <h5 className={`text-sm font-semibold mb-2 ${
                                                  confidenceTier === 'low'
                                                    ? 'text-red-900 dark:text-red-100'
                                                    : 'text-amber-900 dark:text-amber-100'
                                                }`}>
                                                  Clarification Questions
                                                </h5>
                                                <ul className="space-y-2">
                                                  {analysis.questions.map((question, idx) => (
                                                    <li key={idx} className={`text-sm flex items-start gap-2 ${
                                                      confidenceTier === 'low'
                                                        ? 'text-red-800 dark:text-red-200'
                                                        : 'text-amber-800 dark:text-amber-200'
                                                    }`}>
                                                      <span className={`font-semibold flex-shrink-0 ${
                                                        confidenceTier === 'low'
                                                          ? 'text-red-600 dark:text-red-400'
                                                          : 'text-amber-600 dark:text-amber-400'
                                                      }`}>
                                                        {idx + 1}.
                                                      </span>
                                                      <span>{question}</span>
                                                    </li>
                                                  ))}
                                                </ul>
                                              </div>
                                            )}
                                          </>
                                        ) : (
                                          <div className={`text-sm ${
                                            confidenceTier === 'low'
                                              ? 'text-red-800 dark:text-red-200'
                                              : 'text-amber-800 dark:text-amber-200'
                                          }`}>
                                            This rule has {confidenceTier} confidence. Expand to see details.
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  </div>
                                )}

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
