import { NextRequest, NextResponse } from 'next/server'

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000'

// GET - Fetch document audit trail
export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${BACKEND_API_URL}/api/v1/documents/audit`)

    if (!response.ok) {
      throw new Error(`Backend API failed: ${response.statusText}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching document audit trail from backend:', error)
    return NextResponse.json(
      { error: 'Failed to fetch document audit trail' },
      { status: 500 }
    )
  }
}

// POST - Save document analysis result to audit trail
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    const response = await fetch(`${BACKEND_API_URL}/api/v1/documents/audit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      throw new Error(`Backend API failed: ${response.statusText}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error saving document to audit trail:', error)
    return NextResponse.json(
      { error: 'Failed to save document audit trail' },
      { status: 500 }
    )
  }
}
