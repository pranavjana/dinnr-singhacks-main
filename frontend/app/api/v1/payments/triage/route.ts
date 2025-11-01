import { NextResponse } from 'next/server'

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000'

export async function POST(request: Request) {
  try {
    const body = await request.json()

    // Send to backend triage endpoint
    const response = await fetch(`${BACKEND_API_URL}/api/v1/payments/triage`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      // Get error details from backend
      const errorText = await response.text()
      console.error('Backend triage error:', response.status, errorText)

      throw new Error(`Backend API triage failed: ${response.statusText} - ${errorText}`)
    }

    const triageResult = await response.json()
    return NextResponse.json(triageResult)
  } catch (error) {
    console.error('Error in triage:', error)

    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to generate triage plan' },
      { status: 500 }
    )
  }
}
