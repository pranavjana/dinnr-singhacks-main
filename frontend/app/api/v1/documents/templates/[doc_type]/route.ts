import { NextResponse } from 'next/server'

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000'

export async function GET(
  request: Request,
  { params }: { params: Promise<{ doc_type: string }> }
) {
  try {
    const { doc_type } = await params
    const response = await fetch(`${BACKEND_API_URL}/api/v1/documents/templates/${doc_type}`)

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Backend templates error:', response.status, errorText)

      return NextResponse.json(
        { error: 'Failed to fetch template' },
        { status: response.status }
      )
    }

    const result = await response.json()
    return NextResponse.json(result)
  } catch (error) {
    console.error('Error fetching template:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch template' },
      { status: 500 }
    )
  }
}
