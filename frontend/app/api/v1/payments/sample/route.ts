import { NextResponse } from 'next/server'
import { promises as fs } from 'fs'
import path from 'path'

// Cache for CSV data to avoid reading file on every request
let cachedTransactions: any[] | null = null

async function loadTransactions() {
  if (cachedTransactions) {
    return cachedTransactions
  }

  try {
    // Read CSV file from the project root directory
    const csvPath = path.join(process.cwd(), '..', 'transactions_mock_1000_for_participants.csv')
    const fileContent = await fs.readFile(csvPath, 'utf-8')

    // Parse CSV
    const lines = fileContent.split('\n')
    const headers = lines[0].split(',')

    const transactions = []
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim()
      if (!line) continue

      const values = line.split(',')
      const transaction: any = {}

      headers.forEach((header, index) => {
        transaction[header.trim()] = values[index]?.trim() || ''
      })

      transactions.push(transaction)
    }

    cachedTransactions = transactions
    return transactions
  } catch (error) {
    console.error('Error reading CSV file:', error)
    throw error
  }
}

function parseCSVDate(dateStr: string): string {
  if (!dateStr) return new Date().toISOString()

  // Try to parse DD/MM/YYYY format
  const parts = dateStr.split('/')
  if (parts.length === 3) {
    const [day, month, year] = parts
    const date = new Date(`${year}-${month}-${day}`)
    if (!isNaN(date.getTime())) {
      return date.toISOString()
    }
  }

  // Try standard Date parsing
  const date = new Date(dateStr)
  if (!isNaN(date.getTime())) {
    return date.toISOString()
  }

  // Fallback to current date
  return new Date().toISOString()
}

function transformToPaymentTransaction(csvRow: any) {
  // Transform CSV data to match backend PaymentTransaction model
  return {
    // Keep CSV transaction_id for tracking
    transaction_id: csvRow.transaction_id,

    // Required fields
    originator_name: csvRow.originator_name || 'Unknown',
    originator_account: csvRow.originator_account || 'UNKNOWN',
    originator_country: csvRow.originator_country || 'XX',

    beneficiary_name: csvRow.beneficiary_name || 'Unknown',
    beneficiary_account: csvRow.beneficiary_account || 'UNKNOWN',
    beneficiary_country: csvRow.beneficiary_country || 'XX',

    amount: parseFloat(csvRow.amount) || 0,
    currency: csvRow.currency || 'USD',

    // Convert date strings to ISO format using custom parser
    transaction_date: csvRow.booking_datetime || new Date().toISOString(),
    value_date: parseCSVDate(csvRow.value_date),

    // SWIFT message type - required field, default to MT103 if not present
    swift_message_type: csvRow.swift_mt || 'MT103',

    // Optional fields
    channel: csvRow.channel,
    product_type: csvRow.product_type,
    purpose_code: csvRow.purpose_code,
    narrative: csvRow.narrative,

    ordering_institution: csvRow.ordering_institution_bic,
    beneficiary_institution: csvRow.beneficiary_institution_bic,

    sanctions_screening_result: csvRow.sanctions_screening,
    pep_screening_result: csvRow.customer_is_pep === 'TRUE' ? 'REVIEW' : 'PASS',
    edd_required: csvRow.edd_required === 'TRUE',
    edd_performed: csvRow.edd_performed === 'TRUE',
    str_filed_datetime: csvRow.str_filed_datetime || null,
    client_risk_profile: csvRow.client_risk_profile,
    customer_risk_rating: csvRow.customer_risk_rating,

    // Keep all original CSV fields for display
    _csvData: csvRow
  }
}

export async function GET() {
  try {
    const transactions = await loadTransactions()

    // Return 5 random transactions
    const selectedTransactions = []
    const usedIndices = new Set<number>()

    while (selectedTransactions.length < 5 && usedIndices.size < transactions.length) {
      const randomIndex = Math.floor(Math.random() * transactions.length)
      if (!usedIndices.has(randomIndex)) {
        usedIndices.add(randomIndex)
        const transformed = transformToPaymentTransaction(transactions[randomIndex])
        selectedTransactions.push(transformed)
      }
    }

    return NextResponse.json(selectedTransactions)
  } catch (error) {
    console.error('Error loading transaction:', error)

    return NextResponse.json(
      { error: 'Failed to load transaction from CSV' },
      { status: 500 }
    )
  }
}
