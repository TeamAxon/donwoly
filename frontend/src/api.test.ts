import { afterEach, describe, expect, it, vi } from 'vitest'
import { parseSseBlock, streamChat } from './api'


afterEach(() => {
  vi.restoreAllMocks()
})

describe('parseSseBlock', () => {
  it('parses an event and JSON payload', () => {
    expect(parseSseBlock('event: chunk\ndata: {"answerChunk":"안녕"}')).toEqual({
      event: 'chunk',
      data: { answerChunk: '안녕' },
    })
  })
})

describe('streamChat', () => {
  it('handles SSE events split across arbitrary network chunks', async () => {
    const encoder = new TextEncoder()
    const pieces = [
      'event: meta\ndata: {"conversationId":"c1",',
      '"messageId":"m1"}\n\nevent: chunk\ndata: {"answerChunk":"첫',
      ' 번째"}\n\nevent: chunk\ndata: {"answerChunk":" 답변"}\n\n',
      'event: sources\ndata: {"sources":[{"title":"문서","url":"https://example.com"}]}\n\n',
      'event: done\ndata: {}\n\n',
    ]
    const stream = new ReadableStream({
      start(controller) {
        pieces.forEach((piece) => controller.enqueue(encoder.encode(piece)))
        controller.close()
      },
    })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(stream, {
          status: 200,
          headers: { 'Content-Type': 'text/event-stream' },
        }),
      ),
    )

    const chunks: string[] = []
    const metadata: unknown[] = []
    const sources: unknown[] = []
    let completed = false
    await streamChat(
      { message: '질문' },
      'token',
      {
        onMeta: (value) => metadata.push(value),
        onChunk: (value) => chunks.push(value),
        onSources: (value) => sources.push(value),
        onDone: () => { completed = true },
      },
    )

    expect(metadata).toEqual([{ conversationId: 'c1', messageId: 'm1' }])
    expect(chunks.join('')).toBe('첫 번째 답변')
    expect(sources).toEqual([[{ title: '문서', url: 'https://example.com' }]])
    expect(completed).toBe(true)
  })
})
