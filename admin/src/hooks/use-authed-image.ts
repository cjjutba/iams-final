/**
 * useAuthedImage — fetch a protected image via the authenticated Axios
 * client and expose it to an <img src> via a blob URL.
 *
 * Problem: the admin API is Bearer-token authenticated, and a plain
 * ``<img src="/api/v1/recognitions/<id>/live-crop" />`` can't attach
 * custom headers — browsers only send cookies with image requests.
 * Without this hook, every crop thumbnail is a 401 and the UI shows
 * blank tiles.
 *
 * Solution: fetch the image via Axios (Bearer header attached by the
 * request interceptor), receive the bytes as a Blob, wrap in an object
 * URL, feed that to ``<img src>``. Blob URLs are same-origin and don't
 * need auth. They're revoked when the hook unmounts.
 *
 * Memory + dedup: a module-level ref-counted cache means N components
 * sharing a URL share one blob. When the last consumer unmounts, the
 * blob is revoked and evicted. Failed fetches evict immediately so a
 * retry on re-render isn't stuck on the cached error.
 *
 * Redirects: when the storage backend is MinIO, the crop endpoint
 * responds with ``302 Found`` to a presigned S3 URL. Axios follows the
 * redirect transparently, and the final fetch returns the JPEG bytes —
 * so this hook works identically for both filesystem and MinIO modes.
 */

import { useEffect, useState } from 'react'
import api from '@/services/api'

interface ImageState {
  src: string | null
  loading: boolean
  error: Error | null
}

interface CacheEntry {
  objectUrl: string
  refs: number
  promise: Promise<string>
}

const cache = new Map<string, CacheEntry>()

/**
 * Strip the API base path from a URL so it can be passed to the shared
 * ``api`` axios instance (which already prefixes every request with
 * baseURL). Leaves absolute URLs + presigned URLs + already-relative
 * tail paths alone.
 */
function toApiRelative(raw: string): string {
  if (/^https?:\/\//i.test(raw)) return raw
  // The backend builds crop URLs as `${API_PREFIX}/recognitions/...`.
  // baseURL is '/api/v1' by default; strip that leading segment if it's
  // present so axios doesn't double-prefix.
  const base = String(api.defaults.baseURL ?? '').replace(/\/$/, '')
  if (base && raw.startsWith(base + '/')) return raw.slice(base.length)
  return raw
}

async function fetchBlobUrl(url: string): Promise<string> {
  const res = await api.get(toApiRelative(url), { responseType: 'blob' })
  const blob = res.data as Blob
  return URL.createObjectURL(blob)
}

function acquire(url: string): CacheEntry {
  const existing = cache.get(url)
  if (existing) {
    existing.refs += 1
    return existing
  }
  const entry: CacheEntry = {
    objectUrl: '',
    refs: 1,
    promise: fetchBlobUrl(url).then(
      (objectUrl) => {
        entry.objectUrl = objectUrl
        return objectUrl
      },
      (err) => {
        // Evict on failure so the next mount retries instead of replaying
        // the cached rejection forever.
        cache.delete(url)
        throw err
      },
    ),
  }
  cache.set(url, entry)
  return entry
}

function release(url: string) {
  const entry = cache.get(url)
  if (!entry) return
  entry.refs -= 1
  if (entry.refs <= 0) {
    if (entry.objectUrl) URL.revokeObjectURL(entry.objectUrl)
    cache.delete(url)
  }
}

/**
 * Hook that returns a blob URL for a protected image, or null while
 * loading / on error. Pass null or empty to disable.
 */
export function useAuthedImage(url: string | null | undefined): ImageState {
  const [state, setState] = useState<ImageState>({
    src: null,
    loading: !!url,
    error: null,
  })

  useEffect(() => {
    if (!url) {
      setState({ src: null, loading: false, error: null })
      return
    }

    let cancelled = false
    setState({ src: null, loading: true, error: null })

    const entry = acquire(url)
    if (entry.objectUrl) {
      // Cache hit on a completed fetch — emit synchronously to avoid a
      // pointless loading flash.
      setState({ src: entry.objectUrl, loading: false, error: null })
    } else {
      entry.promise.then(
        (objectUrl) => {
          if (!cancelled) {
            setState({ src: objectUrl, loading: false, error: null })
          }
        },
        (err: Error) => {
          if (!cancelled) {
            setState({ src: null, loading: false, error: err })
          }
        },
      )
    }

    return () => {
      cancelled = true
      release(url)
    }
  }, [url])

  return state
}
