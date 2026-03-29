import './App.css';

import { useEffect, useRef, useState, useCallback, useMemo } from "react";

import { Trash2, Upload, RefreshCw, GripVertical } from 'lucide-react';
import ImageComponent from './ImageComponent';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Label } from './components/ui/label';
import { Slider } from './components/ui/slider';
import { ConfirmDialog } from './components/ui/dialog';
import { PulseLoader } from "react-spinners";

// Use relative URL when served from same server, or specify full URL for development
export const SERVER_URL = import.meta.env.DEV
  ? (import.meta.env.VITE_API_URL || "http://localhost:5000")
  : ""

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [password, setPassword] = useState("")
  const [loginError, setLoginError] = useState("")
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'))

  // Check authentication on mount
  useEffect(() => {
    const checkAuth = async () => {
      const storedToken = localStorage.getItem('token')
      if (storedToken) {
        try {
          const response = await fetch(`${SERVER_URL}/api/auth/verify`, {
            headers: { 'Authorization': `Bearer ${storedToken}` }
          })
          if (response.ok) {
            setToken(storedToken)
            setIsAuthenticated(true)
          } else {
            localStorage.removeItem('token')
            setToken(null)
          }
        } catch (err) {
          localStorage.removeItem('token')
          setToken(null)
        }
      }
      setIsLoading(false)
    }
    checkAuth()
  }, [])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoginError("")

    try {
      const response = await fetch(`${SERVER_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password })
      })

      const data = await response.json()

      if (response.ok) {
        localStorage.setItem('token', data.token)
        setToken(data.token)
        setIsAuthenticated(true)
      } else {
        setLoginError(data.error || 'Login failed')
      }
    } catch (err) {
      setLoginError('Connection error')
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    setToken(null)
    setIsAuthenticated(false)
    setPassword("")
  }

  // Show loading screen
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <PulseLoader color={"white"} />
      </div>
    )
  }

  // Show login screen if not authenticated
  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="w-full max-w-md p-8 space-y-6 bg-gray-800 rounded-lg shadow-xl">
          <h2 className="text-3xl font-bold text-center text-white">LED Matrix Control</h2>
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <Label htmlFor="password" className="text-white">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                className="mt-2"
                autoFocus
              />
            </div>
            {loginError && (
              <p className="text-red-500 text-sm">{loginError}</p>
            )}
            <Button type="submit" className="w-full">
              Sign In
            </Button>
          </form>
        </div>
      </div>
    )
  }

  return <MainApp token={token!} onLogout={handleLogout} />
}

function MainApp({ token, onLogout }: { token: string, onLogout: () => void }) {
  // Current server state
  const [serverImages, setServerImages] = useState<string[]>([])
  const [serverBrightness, setServerBrightness] = useState(50)
  const [serverHoldSeconds, setServerHoldSeconds] = useState(20)
  const [serverOrder, setServerOrder] = useState<string[]>([])

  // Local pending state
  const [images, setImages] = useState<string[]>([])
  const [toBeDeleted, setToBeDeleted] = useState<string[]>([])
  const [pendingUploads, setPendingUploads] = useState<File[]>([])
  const [brightness, setBrightness] = useState(50)
  const [holdSeconds, setHoldSeconds] = useState(20)

  // Schedule state
  const [scheduleEnabled, setScheduleEnabled] = useState(false)
  const [scheduleOnTime, setScheduleOnTime] = useState("08:00")
  const [scheduleOffTime, setScheduleOffTime] = useState("23:00")

  // Reordering state
  const [isReorderMode, setIsReorderMode] = useState(false)
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null)
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null)
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const touchStartPosRef = useRef<{ x: number; y: number } | null>(null)

  // UI state
  const [isApplying, setIsApplying] = useState(false)
  const [isFetchingData, setIsFetchingData] = useState(true)
  const [applyError, setApplyError] = useState<string | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ObjectURL cache to prevent memory leaks
  const objectUrlsRef = useRef<Map<string, string>>(new Map())

  const authHeaders = useMemo(() => ({
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }), [token])

  // Check if order has changed (comparing only non-pending images)
  const currentNonPendingImages = images.filter(img => !img.startsWith('pending:'))
  const orderChanged = JSON.stringify(currentNonPendingImages) !== JSON.stringify(serverOrder)

  // Check if there are pending changes
  const hasChanges =
    brightness !== serverBrightness ||
    holdSeconds !== serverHoldSeconds ||
    toBeDeleted.length > 0 ||
    pendingUploads.length > 0 ||
    orderChanged

  // Clean up ObjectURLs when pending uploads change
  useEffect(() => {
    return () => {
      objectUrlsRef.current.forEach(url => URL.revokeObjectURL(url))
      objectUrlsRef.current.clear()
    }
  }, [])

  function getPendingImageUrl(file: File): string {
    const key = file.name + file.size
    if (!objectUrlsRef.current.has(key)) {
      objectUrlsRef.current.set(key, URL.createObjectURL(file))
    }
    return objectUrlsRef.current.get(key)!
  }

  // Fetch initial data
  useEffect(() => {
    setIsFetchingData(true)

    const fetchData = async () => {
      try {
        // Fetch images with order
        const orderRes = await fetch(`${SERVER_URL}/images/order`)
        if (orderRes.ok) {
          const data = await orderRes.json()
          const orderedImgs = data.order || []
          setServerOrder(orderedImgs)
          setServerImages(orderedImgs)
          setImages(orderedImgs)
        }
      } catch (err) {
        console.error("Error fetching image order:", err)
        // Fallback to unordered list
        try {
          const res = await fetch(`${SERVER_URL}/images`)
          if (res.ok) {
            const data = await res.json()
            const imgs = data.images || []
            setServerImages(imgs)
            setImages(imgs)
            setServerOrder(imgs)
          }
        } catch (err2) {
          console.error("Error fetching images:", err2)
        }
      }

      try {
        const configRes = await fetch(`${SERVER_URL}/api/config`)
        if (configRes.ok) {
          const data = await configRes.json()
          if (data.brightness) {
            setServerBrightness(data.brightness)
            setBrightness(data.brightness)
          }
          if (data.hold_seconds) {
            setServerHoldSeconds(data.hold_seconds)
            setHoldSeconds(data.hold_seconds)
          }
        }
      } catch (err) {
        console.error("Error fetching config:", err)
      }

      try {
        const schedRes = await fetch(`${SERVER_URL}/api/schedule`)
        if (schedRes.ok) {
          const data = await schedRes.json()
          setScheduleEnabled(data.enabled ?? false)
          setScheduleOnTime(data.on_time ?? "08:00")
          setScheduleOffTime(data.off_time ?? "23:00")
        }
      } catch (err) {
        console.error("Error fetching schedule:", err)
      }

      setIsFetchingData(false)
    }

    fetchData()
  }, [])

  // Handle file selection for upload
  function handleFileSelect(event: React.ChangeEvent<HTMLInputElement>) {
    const files = event.target.files
    if (files && files.length > 0) {
      const newFiles = Array.from(files)
      setPendingUploads(prev => [...prev, ...newFiles])
      newFiles.forEach(file => {
        setImages(prev => [...prev, `pending:${file.name}`])
      })
    }
    if (fileInputRef.current) fileInputRef.current.value = ""
  }

  // Remove pending upload
  function removePendingUpload(fileName: string) {
    // Revoke ObjectURL
    const file = pendingUploads.find(f => f.name === fileName)
    if (file) {
      const key = file.name + file.size
      const url = objectUrlsRef.current.get(key)
      if (url) {
        URL.revokeObjectURL(url)
        objectUrlsRef.current.delete(key)
      }
    }
    setPendingUploads(prev => prev.filter(f => f.name !== fileName))
    setImages(prev => prev.filter(img => img !== `pending:${fileName}`))
  }

  // Mark images for deletion
  function toggleDeleteImage(filename: string) {
    if (isReorderMode) return

    if (filename.startsWith('pending:')) {
      removePendingUpload(filename.replace('pending:', ''))
      return
    }

    if (toBeDeleted.includes(filename)) {
      setToBeDeleted(prev => prev.filter(f => f !== filename))
    } else {
      setToBeDeleted(prev => [...prev, filename])
    }
  }

  // Reorder functions
  const handleDragStart = useCallback((index: number) => {
    setDraggedIndex(index)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent, index: number) => {
    e.preventDefault()
    if (draggedIndex !== null && draggedIndex !== index) {
      setDragOverIndex(index)
    }
  }, [draggedIndex])

  const handleDrop = useCallback((index: number) => {
    if (draggedIndex !== null && draggedIndex !== index) {
      const newImages = [...images]
      const [draggedItem] = newImages.splice(draggedIndex, 1)
      newImages.splice(index, 0, draggedItem)
      setImages(newImages)
    }
    setDraggedIndex(null)
    setDragOverIndex(null)
  }, [draggedIndex, images])

  const handleDragEnd = useCallback(() => {
    setDraggedIndex(null)
    setDragOverIndex(null)
  }, [])

  // Touch handlers for mobile reordering
  const handleTouchStart = useCallback((e: React.TouchEvent, index: number) => {
    if (!isReorderMode) return
    e.preventDefault()

    const touch = e.touches[0]
    touchStartPosRef.current = { x: touch.clientX, y: touch.clientY }

    longPressTimerRef.current = setTimeout(() => {
      setDraggedIndex(index)
      if (navigator.vibrate) {
        navigator.vibrate(50)
      }
    }, 300)
  }, [isReorderMode])

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (!isReorderMode) return

    if (draggedIndex !== null) {
      e.preventDefault()
    }

    // Cancel long press if moved too much
    if (longPressTimerRef.current && touchStartPosRef.current) {
      const touch = e.touches[0]
      const dx = Math.abs(touch.clientX - touchStartPosRef.current.x)
      const dy = Math.abs(touch.clientY - touchStartPosRef.current.y)
      if (dx > 10 || dy > 10) {
        clearTimeout(longPressTimerRef.current)
        longPressTimerRef.current = null
      }
    }

    if (draggedIndex === null) return

    const touch = e.touches[0]
    const elements = document.elementsFromPoint(touch.clientX, touch.clientY)
    const imageElement = elements.find(el => el.hasAttribute('data-image-index'))
    if (imageElement) {
      const newIndex = parseInt(imageElement.getAttribute('data-image-index') || '-1', 10)
      if (newIndex >= 0 && newIndex !== draggedIndex) {
        setDragOverIndex(newIndex)
      }
    }
  }, [isReorderMode, draggedIndex])

  const handleTouchEnd = useCallback(() => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current)
      longPressTimerRef.current = null
    }

    if (draggedIndex !== null && dragOverIndex !== null && draggedIndex !== dragOverIndex) {
      const newImages = [...images]
      const [draggedItem] = newImages.splice(draggedIndex, 1)
      newImages.splice(dragOverIndex, 0, draggedItem)
      setImages(newImages)
    }

    setDraggedIndex(null)
    setDragOverIndex(null)
    touchStartPosRef.current = null
  }, [draggedIndex, dragOverIndex, images])

  // Update schedule immediately on change
  function updateSchedule(updates: { enabled?: boolean; on_time?: string; off_time?: string }) {
    if (updates.enabled !== undefined) setScheduleEnabled(updates.enabled)
    if (updates.on_time !== undefined) setScheduleOnTime(updates.on_time)
    if (updates.off_time !== undefined) setScheduleOffTime(updates.off_time)

    fetch(`${SERVER_URL}/api/schedule`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify(updates)
    }).catch(err => console.error("Error updating schedule:", err))
  }

  // Apply all changes
  async function applyChanges() {
    setIsApplying(true)
    setApplyError(null)

    try {
      // Upload pending files — track which succeeded
      const uploadedNames: string[] = []
      const failedUploads: string[] = []

      for (const file of pendingUploads) {
        const formData = new FormData()
        formData.append("image", file)

        try {
          const res = await fetch(`${SERVER_URL}/upload_image`, {
            method: "POST",
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData,
          })
          if (res.ok) {
            const data = await res.json()
            uploadedNames.push(data.filename)
          } else if (res.status === 401) {
            setApplyError("Session expired. Please log in again.")
            setIsApplying(false)
            return
          } else {
            failedUploads.push(file.name)
          }
        } catch {
          failedUploads.push(file.name)
        }
      }

      if (failedUploads.length > 0) {
        setApplyError(`Failed to upload: ${failedUploads.join(', ')}`)
      }

      // Apply config changes and deletions
      const response = await fetch(`${SERVER_URL}/apply_changes`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          brightness: brightness,
          hold_seconds: holdSeconds,
          delete_images: toBeDeleted
        })
      })

      if (response.status === 401) {
        setApplyError("Session expired. Please log in again.")
        setIsApplying(false)
        return
      }

      if (response.ok || response.status === 207) {
        // Save the new order (excluding pending and deleted, plus successfully uploaded)
        const finalOrder = images
          .filter(img => !img.startsWith('pending:') && !toBeDeleted.includes(img))

        const orderToSave = [...finalOrder, ...uploadedNames]

        await fetch(`${SERVER_URL}/images/order`, {
          method: "POST",
          headers: authHeaders,
          body: JSON.stringify({ order: orderToSave })
        })

        // Refresh state from server
        const orderRes = await fetch(`${SERVER_URL}/images/order`)
        const orderData = await orderRes.json()
        const newOrder = orderData.order || []

        setServerOrder(newOrder)
        setServerImages(newOrder)
        setImages(newOrder)
        setServerBrightness(brightness)
        setServerHoldSeconds(holdSeconds)
        setToBeDeleted([])
        setPendingUploads([])
        setIsReorderMode(false)

        // Clean up ObjectURLs
        objectUrlsRef.current.forEach(url => URL.revokeObjectURL(url))
        objectUrlsRef.current.clear()
      }
    } catch (err) {
      console.error("Error applying changes:", err)
      setApplyError("Network error. Please check connection.")
    }

    setIsApplying(false)
  }

  // Discard all changes
  function discardChanges() {
    // Clean up ObjectURLs
    objectUrlsRef.current.forEach(url => URL.revokeObjectURL(url))
    objectUrlsRef.current.clear()

    setImages(serverOrder)
    setBrightness(serverBrightness)
    setHoldSeconds(serverHoldSeconds)
    setToBeDeleted([])
    setPendingUploads([])
    setIsReorderMode(false)
    setApplyError(null)
  }

  // Immediate actions
  function handleTurnOn() {
    fetch(`${SERVER_URL}/turn_on`, {
      method: "POST",
      headers: authHeaders
    }).catch((err) => console.error("Error turning on:", err))
  }

  function handleTurnOff() {
    fetch(`${SERVER_URL}/turn_off`, {
      method: "POST",
      headers: authHeaders
    }).catch((err) => console.error("Error turning off:", err))
  }

  // Format seconds to human readable
  function formatTime(seconds: number): string {
    if (seconds < 60) return `${seconds}s`
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`
  }

  if (isFetchingData) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <PulseLoader color={"white"} />
      </div>
    )
  }

  return (
    <>
      <ConfirmDialog
        open={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={() => {
          toBeDeleted.forEach(img => {
            setImages(prev => prev.filter(i => i !== img))
          })
          setShowDeleteConfirm(false)
        }}
        title="Delete Images"
        description={`Are you sure you want to delete ${toBeDeleted.length} image(s)? This change will be applied when you click "Apply Changes".`}
        confirmText="Delete"
      />

      <div className="p-4 overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-2xl font-bold text-white">LED Matrix Control</h1>
          <Button onClick={onLogout} variant="outline">Logout</Button>
        </div>

        {/* Pending changes banner */}
        {hasChanges && (
          <div className="mb-4 p-3 bg-yellow-900/50 border border-yellow-600 rounded-lg">
            <p className="text-yellow-200 mb-3">You have unsaved changes</p>
            {applyError && (
              <p className="text-red-400 text-sm mb-2">{applyError}</p>
            )}
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={discardChanges}>
                Discard
              </Button>
              <Button size="sm" onClick={applyChanges} disabled={isApplying}>
                <RefreshCw className={isApplying ? "animate-spin mr-2" : "mr-2"} size={16} />
                {isApplying ? "Applying..." : "Apply Changes"}
              </Button>
            </div>
          </div>
        )}

        {/* Error banner (when no pending changes) */}
        {!hasChanges && applyError && (
          <div className="mb-4 p-3 bg-red-900/50 border border-red-600 rounded-lg">
            <p className="text-red-200 text-sm">{applyError}</p>
          </div>
        )}

        {/* Reorder mode toggle */}
        <div className="mb-3 flex items-center gap-3">
          <Button
            variant={isReorderMode ? "default" : "outline"}
            size="sm"
            onClick={() => setIsReorderMode(!isReorderMode)}
          >
            <GripVertical className="mr-2" size={16} />
            {isReorderMode ? "Done Reordering" : "Reorder Images"}
          </Button>
          {isReorderMode && (
            <span className="text-sm text-gray-400">
              Drag images to reorder
            </span>
          )}
          {orderChanged && !isReorderMode && (
            <span className="text-sm text-yellow-400">
              Order modified
            </span>
          )}
        </div>

        {/* Image gallery */}
        <div className="relative grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-1 max-h-[55vh] overflow-y-scroll">
          {isApplying && (
            <div className='absolute left-0 top-0 w-full h-full bg-black/80 z-50 pointer-events-auto flex justify-center items-center'>
              <PulseLoader color={"white"} />
            </div>
          )}
          {images.length > 0 ? (
            images.map((url, idx) => {
              const isPending = url.startsWith('pending:')
              const pendingFile = isPending ? pendingUploads.find(f => f.name === url.replace('pending:', '')) : null
              const isMarkedForDelete = toBeDeleted.includes(url)
              const isDragging = draggedIndex === idx
              const isDragOver = dragOverIndex === idx

              return (
                <div
                  key={`${url}-${idx}`}
                  data-image-index={idx}
                  draggable={isReorderMode && !isPending}
                  onDragStart={() => isReorderMode && handleDragStart(idx)}
                  onDragOver={(e) => isReorderMode && handleDragOver(e, idx)}
                  onDrop={() => isReorderMode && handleDrop(idx)}
                  onDragEnd={handleDragEnd}
                  onTouchStart={(e) => handleTouchStart(e, idx)}
                  onTouchMove={handleTouchMove}
                  onTouchEnd={handleTouchEnd}
                  className={`relative cursor-pointer border-2 rounded overflow-hidden transition-all
                    ${isMarkedForDelete ? 'border-red-500 opacity-50' : 'border-transparent'}
                    ${isPending ? 'border-green-500' : ''}
                    ${isDragging ? 'opacity-50 scale-95 border-blue-500' : ''}
                    ${isDragOver ? 'border-blue-400 scale-105' : ''}
                    ${isReorderMode && !isPending ? 'cursor-grab active:cursor-grabbing' : ''}`}
                  style={isReorderMode ? {
                    WebkitUserSelect: 'none',
                    userSelect: 'none',
                    WebkitTouchCallout: 'none',
                    touchAction: 'none'
                  } : undefined}
                  onClick={() => !isReorderMode && toggleDeleteImage(url)}
                >
                  {isReorderMode && !isPending && (
                    <div className="absolute top-1 right-1 z-10 bg-black/50 rounded p-0.5">
                      <GripVertical size={14} className="text-white" />
                    </div>
                  )}
                  <img
                    src={isPending && pendingFile ? getPendingImageUrl(pendingFile) : `${SERVER_URL}/images/thumb/${url}`}
                    alt={isPending ? url.replace('pending:', '') : url}
                    className="w-full h-24 object-cover pointer-events-none"
                    loading="lazy"
                  />
                  {isPending && (
                    <div className="absolute top-1 left-1 bg-green-500 text-white text-xs px-1 rounded">
                      New
                    </div>
                  )}
                  {isMarkedForDelete && (
                    <div className="absolute inset-0 flex items-center justify-center bg-red-500/30">
                      <Trash2 className="text-red-500" size={24} />
                    </div>
                  )}
                  {isReorderMode && (
                    <div className="absolute bottom-1 left-1 bg-black/70 text-white text-xs px-1.5 py-0.5 rounded">
                      {idx + 1}
                    </div>
                  )}
                </div>
              )
            })
          ) : (
            <p className="col-span-3 text-center text-gray-500">No images found.</p>
          )}
        </div>

        {/* Delete selected button */}
        <Button
          className='mt-2'
          variant="destructive"
          disabled={toBeDeleted.length === 0}
          onClick={() => setShowDeleteConfirm(true)}
        >
          <Trash2 className="mr-2" size={16} />
          Mark {toBeDeleted.length} for deletion
        </Button>
      </div>

      <div className='flex flex-col gap-5 p-4 mt-2'>
        {/* Immediate actions */}
        <div className='flex gap-3'>
          <Button onClick={handleTurnOn}>Turn on</Button>
          <Button onClick={handleTurnOff}>Turn off</Button>
        </div>

        {/* Schedule */}
        <div className="grid w-full items-center gap-3 p-3 bg-gray-800 rounded-lg">
          <div className="flex items-center justify-between">
            <Label>Auto Schedule</Label>
            <button
              type="button"
              role="switch"
              aria-checked={scheduleEnabled}
              onClick={() => updateSchedule({ enabled: !scheduleEnabled })}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                scheduleEnabled ? 'bg-blue-600' : 'bg-gray-600'
              }`}
            >
              <span className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
                scheduleEnabled ? 'translate-x-6' : 'translate-x-1'
              }`} />
            </button>
          </div>
          {scheduleEnabled && (
            <div className="flex gap-4 items-center">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-400">On</span>
                <input
                  type="time"
                  value={scheduleOnTime}
                  onChange={(e) => updateSchedule({ on_time: e.target.value })}
                  className="bg-gray-700 text-white rounded px-2 py-1 text-sm"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-400">Off</span>
                <input
                  type="time"
                  value={scheduleOffTime}
                  onChange={(e) => updateSchedule({ off_time: e.target.value })}
                  className="bg-gray-700 text-white rounded px-2 py-1 text-sm"
                />
              </div>
            </div>
          )}
        </div>

        {/* Upload new image */}
        <div className="grid w-full items-center gap-3">
          <Label>Upload new image</Label>
          <div className="flex w-full items-center gap-2">
            <Input
              ref={fileInputRef}
              onChange={handleFileSelect}
              type="file"
              accept="image/png,image/jpeg,image/jpg,image/gif,image/webp"
              multiple
            />
            <Upload size={20} className="text-gray-400" />
          </div>
          {pendingUploads.length > 0 && (
            <p className="text-sm text-green-400">
              {pendingUploads.length} file(s) ready to upload
            </p>
          )}
        </div>

        {/* Brightness */}
        <div className="grid w-full items-center gap-3">
          <Label>Brightness {brightness !== serverBrightness && <span className="text-yellow-400">(modified)</span>}</Label>
          <div className="flex w-full items-center gap-5">
            <Slider
              value={[brightness]}
              onValueChange={(value) => setBrightness(value[0])}
              defaultValue={[50]}
              max={100}
              min={1}
              step={5}
            />
            <span className='font-bold text-xl w-16'>{brightness}%</span>
          </div>
        </div>

        {/* Hold time */}
        <div className="grid w-full items-center gap-3">
          <Label>Image Hold Time {holdSeconds !== serverHoldSeconds && <span className="text-yellow-400">(modified)</span>}</Label>
          <div className="flex w-full items-center gap-5">
            <Slider
              value={[holdSeconds]}
              onValueChange={(value) => setHoldSeconds(value[0])}
              defaultValue={[20]}
              min={10}
              max={300}
              step={5}
            />
            <span className='font-bold text-xl w-20'>{formatTime(holdSeconds)}</span>
          </div>
        </div>

        {/* Apply changes button at bottom */}
        {hasChanges && (
          <Button
            className="w-full mt-4"
            size="lg"
            onClick={applyChanges}
            disabled={isApplying}
          >
            <RefreshCw className={isApplying ? "animate-spin mr-2" : "mr-2"} size={16} />
            {isApplying ? "Applying Changes..." : "Apply Changes"}
          </Button>
        )}
      </div>
    </>
  )
}

export default App
