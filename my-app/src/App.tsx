import './App.css';

import { useEffect, useRef, useState } from "react";

import { Trash2, Upload, RefreshCw } from 'lucide-react';
import ImageComponent from './ImageComponent';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Label } from './components/ui/label';
import { Slider } from './components/ui/slider';
import { ConfirmDialog } from './components/ui/dialog';
import { ClimbingBoxLoader } from "react-spinners";

// Use relative URL when served from same server, or specify full URL for development
export const SERVER_URL = import.meta.env.DEV ? "http://192.168.0.127:5000" : ""

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
        // Verify token is still valid
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
        <ClimbingBoxLoader color={"white"} />
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

  // Local pending state
  const [images, setImages] = useState<string[]>([])
  const [toBeDeleted, setToBeDeleted] = useState<string[]>([])
  const [pendingUploads, setPendingUploads] = useState<File[]>([])
  const [brightness, setBrightness] = useState(50)
  const [holdSeconds, setHoldSeconds] = useState(20)

  // UI state
  const [isApplying, setIsApplying] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const authHeaders = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }

  // Check if there are pending changes
  const hasChanges =
    brightness !== serverBrightness ||
    holdSeconds !== serverHoldSeconds ||
    toBeDeleted.length > 0 ||
    pendingUploads.length > 0

  // Fetch initial data
  useEffect(() => {
    // Fetch images
    fetch(`${SERVER_URL}/images`)
      .then((res) => res.json())
      .then((data) => {
        const imgs = data.images || []
        setServerImages(imgs)
        setImages(imgs)
      })
      .catch((err) => console.error("Error fetching images:", err))

    // Fetch config
    fetch(`${SERVER_URL}/api/config`)
      .then((res) => res.json())
      .then((data) => {
        if (data.brightness) {
          setServerBrightness(data.brightness)
          setBrightness(data.brightness)
        }
        if (data.hold_seconds) {
          setServerHoldSeconds(data.hold_seconds)
          setHoldSeconds(data.hold_seconds)
        }
      })
      .catch((err) => console.error("Error fetching config:", err))
  }, [])

  // Handle file selection for upload
  function handleFileSelect(event: React.ChangeEvent<HTMLInputElement>) {
    const files = event.target.files
    if (files && files.length > 0) {
      const newFiles = Array.from(files)
      setPendingUploads(prev => [...prev, ...newFiles])
      // Show preview in image list
      newFiles.forEach(file => {
        setImages(prev => [...prev, `pending:${file.name}`])
      })
    }
    if (fileInputRef.current) fileInputRef.current.value = ""
  }

  // Remove pending upload
  function removePendingUpload(fileName: string) {
    setPendingUploads(prev => prev.filter(f => f.name !== fileName))
    setImages(prev => prev.filter(img => img !== `pending:${fileName}`))
  }

  // Mark images for deletion
  function toggleDeleteImage(filename: string) {
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

  // Apply all changes
  async function applyChanges() {
    setIsApplying(true)

    try {
      // First, upload any pending files
      for (const file of pendingUploads) {
        const formData = new FormData()
        formData.append("image", file)

        await fetch(`${SERVER_URL}/upload_image`, {
          method: "POST",
          headers: { 'Authorization': `Bearer ${token}` },
          body: formData,
        })
      }

      // Then apply config changes and deletions
      const response = await fetch(`${SERVER_URL}/apply_changes`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          brightness: brightness,
          hold_seconds: holdSeconds,
          delete_images: toBeDeleted
        })
      })

      const data = await response.json()

      if (response.ok) {
        // Refresh state from server
        const imagesRes = await fetch(`${SERVER_URL}/images`)
        const imagesData = await imagesRes.json()
        const newImages = imagesData.images || []

        setServerImages(newImages)
        setImages(newImages)
        setServerBrightness(brightness)
        setServerHoldSeconds(holdSeconds)
        setToBeDeleted([])
        setPendingUploads([])
      }
    } catch (err) {
      console.error("Error applying changes:", err)
    }

    setIsApplying(false)
  }

  // Discard all changes
  function discardChanges() {
    setImages(serverImages)
    setBrightness(serverBrightness)
    setHoldSeconds(serverHoldSeconds)
    setToBeDeleted([])
    setPendingUploads([])
  }

  // Immediate actions (no confirmation needed)
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
          <div className="mb-4 p-3 bg-yellow-900/50 border border-yellow-600 rounded-lg flex items-center justify-between">
            <span className="text-yellow-200">You have unsaved changes</span>
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

        {/* Image gallery */}
        <div className="relative grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-1 max-h-[55vh] overflow-y-scroll">
          {isApplying && (
            <div className='absolute left-0 top-0 w-full h-full bg-black/50 z-50 pointer-events-auto flex justify-center items-center'>
              <ClimbingBoxLoader color={"white"} loading={true} />
            </div>
          )}
          {images.length > 0 ? (
            images.map((url, idx) => {
              const isPending = url.startsWith('pending:')
              const displayUrl = isPending ? URL.createObjectURL(pendingUploads.find(f => f.name === url.replace('pending:', ''))!) : url
              const isMarkedForDelete = toBeDeleted.includes(url)

              return (
                <div
                  key={idx}
                  className={`relative cursor-pointer border-2 rounded overflow-hidden
                    ${isMarkedForDelete ? 'border-red-500 opacity-50' : 'border-transparent'}
                    ${isPending ? 'border-green-500' : ''}`}
                  onClick={() => toggleDeleteImage(url)}
                >
                  <img
                    src={isPending ? displayUrl : `${SERVER_URL}/images/${url}`}
                    alt={isPending ? url.replace('pending:', '') : url}
                    className="w-full h-24 object-cover"
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

        {/* Upload new image */}
        <div className="grid w-full items-center gap-3">
          <Label>Upload new image</Label>
          <div className="flex w-full items-center gap-2">
            <Input
              ref={fileInputRef}
              onChange={handleFileSelect}
              type="file"
              accept="image/*"
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
