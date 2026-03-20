import { act, type ReactElement } from "react"
import { createRoot } from "react-dom/client"

globalThis.IS_REACT_ACT_ENVIRONMENT = true

export async function renderElement(element: ReactElement) {
  const container = document.createElement("div")
  document.body.appendChild(container)
  const root = createRoot(container)

  await act(async () => {
    root.render(element)
  })

  return {
    container,
    async rerender(next: ReactElement) {
      await act(async () => {
        root.render(next)
      })
    },
    async unmount() {
      await act(async () => {
        root.unmount()
      })
      container.remove()
    },
  }
}

export async function renderHook<T>(useHook: () => T) {
  const result: { current: T | null } = { current: null }

  function Harness() {
    result.current = useHook()
    return null
  }

  const rendered = await renderElement(<Harness />)
  return { ...rendered, result }
}
