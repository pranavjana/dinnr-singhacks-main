import { NextResponse } from 'next/server'

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000'

export async function PUT(
  request: Request,
  { params }: { params: { ruleId: string } }
) {
  try {
    const { ruleId } = params
    const body = await request.json()

    const response = await fetch(`${BACKEND_API_URL}/api/v1/extraction/rules/${ruleId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    const result = await response.json()

    if (!response.ok) {
      console.error('Backend update rule error:', response.status, result)
      return NextResponse.json(
        { error: result?.detail || 'Failed to update compliance rule' },
        { status: response.status }
      )
    }

    return NextResponse.json(result, { status: response.status })
  } catch (error) {
    console.error('Error updating rule:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to update compliance rule' },
      { status: 500 }
    )
  }
}
