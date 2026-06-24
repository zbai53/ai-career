import { useEffect, useRef, useState } from 'react'

interface TypewriterTextProps {
  text: string
  speed?: number          // ms per character, default 20
  onComplete?: () => void
}

export default function TypewriterText({ text, speed = 20, onComplete }: TypewriterTextProps) {
  const [displayed, setDisplayed] = useState('')
  const [done, setDone] = useState(false)
  const onCompleteRef = useRef(onComplete)

  // Keep ref current without restarting the animation
  useEffect(() => { onCompleteRef.current = onComplete }, [onComplete])

  // Restart animation whenever text changes
  useEffect(() => {
    setDisplayed('')
    setDone(false)

    if (!text) {
      setDone(true)
      onCompleteRef.current?.()
      return
    }

    let index = 0
    const id = setInterval(() => {
      index += 1
      setDisplayed(text.slice(0, index))
      if (index >= text.length) {
        clearInterval(id)
        setDone(true)
        onCompleteRef.current?.()
      }
    }, speed)

    return () => clearInterval(id)
  }, [text, speed])

  // Render with <br /> substitution when text contains newlines
  const hasNewlines = text.includes('\n')

  if (hasNewlines) {
    const html = displayed.replace(/\n/g, '<br/>') + (done ? '' : '<span class="typewriter-cursor">|</span>')
    return (
      <>
        <style>{`.typewriter-cursor{display:inline-block;animation:tw-blink 0.7s step-end infinite}@keyframes tw-blink{0%,100%{opacity:1}50%{opacity:0}}`}</style>
        <span dangerouslySetInnerHTML={{ __html: html }} />
      </>
    )
  }

  return (
    <>
      <style>{`.typewriter-cursor{display:inline-block;animation:tw-blink 0.7s step-end infinite}@keyframes tw-blink{0%,100%{opacity:1}50%{opacity:0}}`}</style>
      <span style={{ whiteSpace: 'pre-wrap' }}>
        {displayed}
        {!done && <span className="typewriter-cursor">|</span>}
      </span>
    </>
  )
}
