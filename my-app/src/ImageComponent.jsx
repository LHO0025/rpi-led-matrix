import { useState } from "react";
import { Checkbox } from "./components/ui/checkbox";
import { cn } from "./lib/utils";

const Image = ({ url, idx, toBeDeleted, setToBeDeleted }) => {
    const [isChecked, setIsChecked] = useState(false);

    return (
        <div
            className={cn(
                "overflow-hidden duration-200 relative rounded-sm border-2 transition-all",
                isChecked && "border-blue-700"
            )}
            onClick={() => {
                setIsChecked(!isChecked)
                if (!isChecked) {
                    setToBeDeleted([...toBeDeleted, url]);
                } else {
                    setToBeDeleted(toBeDeleted.filter((item) => item !== url));
                }
            }}
        >
            {
                <div className={cn(
                    "absolute inset-0 bg-black pointer-events-none transition-opacity",
                    isChecked ? "opacity-80" : "opacity-0"
                )} />
            }
            {
                <Checkbox
                    checked={isChecked}
                    id="toggle-2"
                    className="absolute right-1 top-1 data-[state=checked]:border-blue-700 data-[state=checked]:bg-blue-700 data-[state=checked]:text-white"
                />
            }
            <img
                src={`http://192.168.88.178:5000/images/${url}`}
                alt={`image-${idx}`}
                className="w-full object-cover aspect-square "
                loading="lazy"
            />
        </div>
    )
}

export default Image