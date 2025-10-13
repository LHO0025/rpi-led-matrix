import './App.css';

import { useEffect, useRef, useState } from "react";

import { Trash2 } from 'lucide-react';
import ImageComponent from './ImageComponent';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Label } from './components/ui/label';
import { Slider } from './components/ui/slider';

function App() {
  const [images, setImages] = useState([]);

  const [toBeDeleted, setToBeDeleted] = useState([]);

  useEffect(() => {
    fetch("http://192.168.88.178:5000/images") // change if Flask runs elsewhere
      .then((res) => res.json())
      .then((data) => {
        setImages(data.images || []);
        console.log("Fetched images:", data.images);
      })
      .catch((err) => console.error("Error fetching images:", err));
  }, []);

  const handleDelete = () => {
    const response = fetch("http://192.168.88.178:5000/delete_image", {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ filenames: toBeDeleted }),
    })
      .then((res) => res.json())
      .then((data) => {
        console.log("Delete response:", data);
        data.deleted.forEach((filename: any) => {
          setImages(prevImages => prevImages.filter(img => img !== filename));
        })
      })
      .catch((err) => console.error("Error deleting image:", err));
  };



  const fileInputRef = useRef(null);
  const [isImageSelected, setIsImageSelected] = useState(false);
  function handleUpload() {
    const file = fileInputRef.current.files[0]
    if (!file) return;

    const formData = new FormData();
    formData.append("image", file);

    fetch("http://192.168.88.178:5000/upload_image", {
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

  function handleSelectedImage(event) {
    if (event.target.files[0]) {
      setIsImageSelected(true);
    } else {
      setIsImageSelected(false);
    }
  }

  function handleUpdateBrightness(brightness) {
    fetch("http://192.168.88.178:5000/set_brightness", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ brightness: brightness }),
    })
      .then((res) => res.json())
      .then((data) => {
        console.log("Upload response:", data);
        setImages((prevImages) => [...prevImages, data.filename]);

      })
      .catch((err) => console.error("Error uploading image:", err));
  }

  return (
    <>

      <div className="p-4 overflow-y-auto">
        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-1 max-h-[75vh] overflow-y-scroll">
          {images.length > 0 ? (
            images.map((url, idx) => (
              <ImageComponent url={url} idx={idx} toBeDeleted={toBeDeleted} setToBeDeleted={setToBeDeleted} />
            ))
          ) : (
            <p className="col-span-3 text-center text-gray-500">No images found.</p>
          )}
        </div>
      </div>

      <Button className='ml-4' disabled={toBeDeleted.length === 0}><Trash2 />Delete images</Button>

      <div className='flex flex-col gap-5 p-4 mt-2'>
        <div className="grid w-full items-center gap-3">
          <Label>Upload new image</Label>
          <div className="flex w-full items-center gap-2">
            <Input ref={fileInputRef} onChange={handleSelectedImage} type="file" accept="image/*" />
            <Button disabled={!isImageSelected} type="submit" variant="outline">
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
              step={5}
            />
            <span className='font-bold text-xl'>{brightness}%</span>
          </div>
        </div>

        {/* <Input type="number" className='w-'/> */}
      </div>


    </>
  )
}

export default App
