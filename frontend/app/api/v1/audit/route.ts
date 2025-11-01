import { NextRequest, NextResponse } from 'next/server'

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const limit = searchParams.get('limit')

    const queryParams = new URLSearchParams()
    if (limit) queryParams.append('limit', limit)

    const query = queryParams.toString()
    const response = await fetch(
      `${BACKEND_API_URL}/api/v1/audit${query ? `?${query}` : ''}`
    )

    if (!response.ok) {
      throw new Error(`Backend API failed: ${response.statusText}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching audit trail from backend:', error)

    return NextResponse.json(
      { error: 'Failed to load audit trail from backend' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    const response = await fetch(`${BACKEND_API_URL}/api/v1/audit`, {
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
    console.error('Error creating audit entry in backend:', error)

    return NextResponse.json(
      { error: 'Failed to create audit entry in backend' },
      { status: 500 }
    )
  }
}
