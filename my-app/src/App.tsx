import './App.css';

import { useEffect, useRef, useState } from "react";

import { Trash2 } from 'lucide-react';
import ImageComponent from './ImageComponent';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Label } from './components/ui/label';
import { Slider } from './components/ui/slider';
import { ClimbingBoxLoader, ClipLoader } from "react-spinners";

// Use relative URL when served from same server, or specify full URL for development
export const SERVER_URL = import.meta.env.DEV ? "http://192.168.0.127:5000" : ""

function App() {
  const [images, setImages] = useState([])
  const [toBeDeleted, setToBeDeleted] = useState([])

  useEffect(() => {
    fetch(`${SERVER_URL}/images`) // change if Flask runs elsewhere
      .then((res) => res.json())
      .then((data) => {
        setImages(data.images || []);
        console.log("Fetched images:", data.images);
      })
      .catch((err) => console.error("Error fetching images:", err));
  }, []);

  const [isDeleteLoading, setIsDeleteLoading] = useState(false)
  const handleDelete = () => {
    setIsDeleteLoading(true)
    const response = fetch(`${SERVER_URL}/delete_image`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ filenames: toBeDeleted }),
    })
      .then((res) => res.json())
      .then((data) => {
        setIsDeleteLoading(false)
        data.deleted.forEach((filename: any) => {
          setImages(prevImages => prevImages.filter(img => img !== filename));
        })
      })
      .catch((err) => {
        console.error("Error deleting image:", err)
        setIsDeleteLoading(false)
      });
  };

  const fileInputRef = useRef(null);
  const [isImageSelected, setIsImageSelected] = useState(false);
  function handleUpload() {
    const file = fileInputRef.current.files[0]
    if (!file) return;

    const formData = new FormData();
    formData.append("image", file);

    fetch(`${SERVER_URL}/upload_image`, {
      method: "POST",
      body: formData,
    })
      .then((res) => res.json())
      .then((data) => {
        console.log("Upload response:", data);
        setImages((prevImages) => [...prevImages, data.filename]);

      })
      .catch((err) => console.error("Error uploading image:", err));
  }

  const [brightness, setBrightness] = useState(50);
  const [holdSeconds, setHoldSeconds] = useState(20);

  // Fetch initial config on mount
  useEffect(() => {
    fetch(`${SERVER_URL}/api/config`)
      .then((res) => res.json())
      .then((data) => {
        if (data.brightness) setBrightness(data.brightness);
        if (data.hold_seconds) setHoldSeconds(data.hold_seconds);
      })
      .catch((err) => console.error("Error fetching config:", err));
  }, []);

  function handleSelectedImage(event) {
    if (event.target.files[0]) {
      setIsImageSelected(true);
    } else {
      setIsImageSelected(false);
    }
  }

  function handleUpdateBrightness(brightness) {
    fetch(`${SERVER_URL}/set_brightness`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ brightness: brightness }),
    })
      .then((res) => res.json())
      .catch((err) => console.error("Error setting brightness:", err));
  }

  function handleUpdateHoldSeconds(seconds: number) {
    fetch(`${SERVER_URL}/set_hold_seconds`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ hold_seconds: seconds }),
    })
      .then((res) => res.json())
      .catch((err) => console.error("Error setting hold seconds:", err));
  }

  // Format seconds to human readable (e.g., "1m 30s")
  function formatTime(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  }

  function handleTurnOn() {
    fetch(`${SERVER_URL}/turn_on`, { method: "POST" })
      .then((res) => res.json())
      .catch((err) => console.error("Error turning on:", err));
  }

  function handleTurnOff() {
    fetch(`${SERVER_URL}/turn_off`, { method: "POST" })
      .then((res) => res.json())
      .catch((err) => console.error("Error turning off:", err));
  }

  return (
    <>
      <div className="p-4 overflow-y-auto">
        <div className="relative grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-1 max-h-[75vh] overflow-y-scroll">
          {
            isDeleteLoading &&
            <div className='absolute left-0 top-0 w-full h-full bg-black/50 z-50 pointer-events-auto flex justify-center items-center'>
              <ClimbingBoxLoader color={"white"} loading={true} />
            </div>
          }
          {images.length > 0 ? (
            images.map((url, idx) => (
              <ImageComponent url={url} idx={idx} toBeDeleted={toBeDeleted} setToBeDeleted={setToBeDeleted} />
            ))
          ) : (
            <p className="col-span-3 text-center text-gray-500">No images found.</p>
          )}
        </div>
      </div>

      <Button className='ml-4' disabled={toBeDeleted.length === 0} onClick={handleDelete}><Trash2 />Delete images</Button>

      <div className='flex flex-col gap-5 p-4 mt-2'>
        <div className='flex gap-3'>
          <Button onClick={handleTurnOn}>Turn on</Button>
          <Button onClick={handleTurnOff}>Turn off</Button>
        </div>

        <div className="grid w-full items-center gap-3">
          <Label>Upload new image</Label>
          <div className="flex w-full items-center gap-2">
            <Input ref={fileInputRef} onChange={handleSelectedImage} type="file" accept="image/*" />
            <Button disabled={!isImageSelected} type="submit" variant="outline" onClick={handleUpload}>
              Upload
            </Button>
          </div>
        </div>

        <div className="grid w-full items-center gap-3">
          <Label>Brightness</Label>
          <div className="flex w-full items-center gap-5">
            <Slider
              value={[brightness]}
              onValueChange={(value) => setBrightness(value[0])}
              onValueCommit={(value) => handleUpdateBrightness(value[0])}
              defaultValue={[50]}
              max={100}
              min={1}
              step={5}
            />
            <span className='font-bold text-xl w-16'>{brightness}%</span>
          </div>
        </div>

        <div className="grid w-full items-center gap-3">
          <Label>Image Hold Time</Label>
          <div className="flex w-full items-center gap-5">
            <Slider
              value={[holdSeconds]}
              onValueChange={(value) => setHoldSeconds(value[0])}
              onValueCommit={(value) => handleUpdateHoldSeconds(value[0])}
              defaultValue={[20]}
              min={10}
              max={300}
              step={5}
            />
            <span className='font-bold text-xl w-20'>{formatTime(holdSeconds)}</span>
          </div>
        </div>
      </div>


    </>
  )
}

export default App
