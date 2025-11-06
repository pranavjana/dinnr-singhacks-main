import { NextResponse } from 'next/server'

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000'

export async function GET(
  request: Request,
  { params }: { params: Promise<{ ruleId: string }> }
) {
  try {
    const { ruleId } = await params

    const response = await fetch(
      `${BACKEND_API_URL}/api/v1/extraction/rules/${ruleId}/confidence-analysis`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    )

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Backend confidence analysis error:', response.status, errorText)
      throw new Error(`Backend API failed: ${response.statusText}`)
    }

    const result = await response.json()
    return NextResponse.json(result)
  } catch (error) {
    console.error('Error fetching confidence analysis:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch confidence analysis' },
      { status: 500 }
    )
  }
}
