import { NextResponse } from 'next/server'

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000'

export async function GET(request: Request) {
  try {
    // Extract query parameters from the request URL
    const { searchParams } = new URL(request.url)
    const queryString = searchParams.toString()

    // Forward to backend with query parameters
    const url = `${BACKEND_API_URL}/api/v1/extraction/rules${queryString ? `?${queryString}` : ''}`
    const response = await fetch(url)

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Backend rules error:', response.status, errorText)
      throw new Error(`Backend API failed: ${response.statusText} - ${errorText}`)
    }

    const rules = await response.json()
    return NextResponse.json(rules)
  } catch (error) {
    console.error('Error fetching rules:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch rules' },
      { status: 500 }
    )
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json()

    const response = await fetch(`${BACKEND_API_URL}/api/v1/extraction/rules`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    const result = await response.json()

    if (!response.ok) {
      console.error('Backend create rule error:', response.status, result)
      return NextResponse.json(
        { error: result?.detail || 'Failed to create compliance rule' },
        { status: response.status }
      )
    }

    return NextResponse.json(result, { status: response.status })
  } catch (error) {
    console.error('Error creating rule:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to create compliance rule' },
      { status: 500 }
    )
  }
}
