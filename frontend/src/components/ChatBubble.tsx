import { Bot, User } from 'lucide-react'

// ---------------------------------------------------------------------------
// Typing indicator (three bouncing dots)
// ---------------------------------------------------------------------------

export function TypingIndicator() {
  return (
    <div className="flex items-end gap-2">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-200 text-gray-500">
        <Bot className="h-4 w-4" />
      </div>
      <div className="flex items-center gap-1 rounded-2xl rounded-bl-none bg-gray-100 px-4 py-3">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="block h-2 w-2 rounded-full bg-gray-400 animate-bounce"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Chat bubble
// ---------------------------------------------------------------------------

interface ChatBubbleProps {
  role: 'interviewer' | 'candidate'
  content: string
  timestamp?: string
}

export default function ChatBubble({ role, content, timestamp }: ChatBubbleProps) {
  const isInterviewer = role === 'interviewer'

  return (
    <div className={`flex items-end gap-2 ${isInterviewer ? '' : 'flex-row-reverse'}`}>
      {/* Avatar */}
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full
          ${isInterviewer ? 'bg-gray-200 text-gray-500' : 'bg-indigo-600 text-white'}`}
      >
        {isInterviewer ? <Bot className="h-4 w-4" /> : <User className="h-4 w-4" />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[90%] sm:max-w-[75%] ${isInterviewer ? '' : 'items-end flex flex-col'}`}>
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed
            ${isInterviewer
              ? 'rounded-bl-none bg-gray-100 text-gray-800'
              : 'rounded-br-none bg-indigo-600 text-white'
            }`}
        >
          {content}
        </div>
        {timestamp && (
          <p className="mt-1 px-1 text-[10px] text-gray-400">{timestamp}</p>
        )}
      </div>
    </div>
  )
}
