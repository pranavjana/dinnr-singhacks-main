import { NextResponse } from 'next/server'

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000'

export async function POST(
  request: Request,
  { params }: { params: Promise<{ ruleId: string }> }
) {
  try {
    const { ruleId } = await params
    const { searchParams } = new URL(request.url)
    const validatedBy = searchParams.get('validated_by')

    const response = await fetch(
      `${BACKEND_API_URL}/api/v1/extraction/rules/${ruleId}/validate?validated_by=${encodeURIComponent(validatedBy || '')}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    )

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Backend validate rule error:', response.status, errorText)
      throw new Error(`Backend API failed: ${response.statusText}`)
    }

    const result = await response.json()
    return NextResponse.json(result)
  } catch (error) {
    console.error('Error validating rule:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to validate rule' },
      { status: 500 }
    )
  }
}
