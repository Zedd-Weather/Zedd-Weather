import { X } from 'lucide-react';
import type { ReactNode } from 'react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  icon?: ReactNode;
  children: ReactNode;
  maxWidth?: string;
}

export function Modal({ isOpen, onClose, title, icon, children, maxWidth = 'max-w-3xl' }: ModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-2 sm:p-4">
      <div className={`bg-[#111] border border-slate-800 rounded-xl w-full ${maxWidth} max-h-[90vh] sm:max-h-[80vh] flex flex-col`}>
        <div className="p-4 sm:p-6 border-b border-slate-800 flex justify-between items-center">
          <h2 className="text-lg sm:text-xl font-semibold text-slate-200 flex items-center">
            {icon}
            {title}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <X className="w-5 h-5 sm:w-6 sm:h-6" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
