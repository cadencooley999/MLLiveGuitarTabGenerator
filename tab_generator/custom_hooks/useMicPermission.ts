import { useEffect, useState } from "react"

type MicPermission = "granted" | "denied" | "prompt" | "unknown"

export default function useMicPermission() {
  const [permission, setPermission] = useState<MicPermission>("unknown")

  useEffect(() => {
    const checkPermission = async () => {
      try {
        const result = await navigator.permissions.query({
          name: "microphone" as PermissionName,
        })

        setPermission(result.state)

        result.onchange = () => {
          setPermission(result.state)
        }
      } catch {
        // fallback for unsupported browsers
        setPermission("unknown")
      }
    }

    checkPermission()
  }, [])

  return permission
}