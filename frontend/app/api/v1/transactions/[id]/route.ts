import { NextRequest, NextResponse } from 'next/server'

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000'

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const body = await request.json()
    const { id } = await params

    const response = await fetch(`${BACKEND_API_URL}/api/v1/transactions/${id}`, {
      method: 'PATCH',
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
    console.error('Error updating transaction in backend:', error)

    return NextResponse.json(
      { error: 'Failed to update transaction in backend' },
      { status: 500 }
    )
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params

    const response = await fetch(`${BACKEND_API_URL}/api/v1/transactions/${id}`)

    if (!response.ok) {
      throw new Error(`Backend API failed: ${response.statusText}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching transaction from backend:', error)

    return NextResponse.json(
      { error: 'Failed to load transaction from backend' },
      { status: 500 }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params

    const response = await fetch(`${BACKEND_API_URL}/api/v1/transactions/${id}`, {
      method: 'DELETE',
    })

    if (!response.ok) {
      throw new Error(`Backend API failed: ${response.statusText}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error deleting transaction from backend:', error)

    return NextResponse.json(
      { error: 'Failed to delete transaction from backend' },
      { status: 500 }
    )
  }
}
