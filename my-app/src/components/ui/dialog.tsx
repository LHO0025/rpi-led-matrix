import * as React from "react"
import { cn } from "../../lib/utils"
import { Button } from "./button"

interface DialogProps {
    open: boolean
    onClose: () => void
    onConfirm: () => void
    title: string
    description: string
    confirmText?: string
    cancelText?: string
}

export function ConfirmDialog({
    open,
    onClose,
    onConfirm,
    title,
    description,
    confirmText = "Confirm",
    cancelText = "Cancel"
}: DialogProps) {
    if (!open) return null

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="fixed inset-0 bg-black/50" onClick={onClose} />
            <div className="relative z-50 w-full max-w-md rounded-lg bg-gray-800 p-6 shadow-xl">
                <h2 className="text-xl font-bold text-white mb-2">{title}</h2>
                <p className="text-gray-300 mb-6">{description}</p>
                <div className="flex justify-end gap-3">
                    <Button variant="outline" onClick={onClose}>
                        {cancelText}
                    </Button>
                    <Button variant="destructive" onClick={() => { onConfirm(); onClose(); }}>
                        {confirmText}
                    </Button>
                </div>
            </div>
        </div>
    )
}
