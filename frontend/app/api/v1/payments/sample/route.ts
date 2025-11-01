import { NextResponse } from 'next/server'

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000'

export async function GET() {
  try {
    // Fetch 5 sample transactions from backend
    const transactions = []

    for (let i = 0; i < 5; i++) {
      const response = await fetch(`${BACKEND_API_URL}/api/v1/payments/sample`)

      if (!response.ok) {
        throw new Error(`Backend API failed: ${response.statusText}`)
      }

      const transaction = await response.json()
      transactions.push(transaction)
    }

    return NextResponse.json(transactions)
  } catch (error) {
    console.error('Error fetching sample transactions from backend:', error)

    return NextResponse.json(
      { error: 'Failed to load transactions from backend' },
      { status: 500 }
    )
  }
}
