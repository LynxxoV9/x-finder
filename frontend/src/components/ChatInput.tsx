import React, { useRef, useState } from 'react';
import { Send, Image, X, Sparkles } from 'lucide-react';

interface ChatInputProps {
  onSend: (message: string, imageBase64?: string) => void;
  isLoading: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, isLoading }) => {
  const [text, setText] = useState('');
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [imageName, setImageName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setImageName(file.name);
      const reader = new FileReader();
      reader.onloadend = () => {
        setImageBase64(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const clearImage = () => {
    setImageBase64(null);
    setImageName(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleSubmit = () => {
    if ((!text.trim() && !imageBase64) || isLoading) return;
    onSend(text.trim(), imageBase64 || undefined);
    setText('');
    clearImage();
  };

  return (
    <div className="chat-input-area">
      <div className="input-wrapper">
        {/* Aperçu de l'image sélectionnée */}
        {imageBase64 && (
          <div className="image-attachment-chip">
            <Image size={14} />
            <span>{imageName || 'Image jointe'}</span>
            <button
              onClick={clearImage}
              style={{ background: 'none', border: 'none', color: '#f43f5e', cursor: 'pointer' }}
            >
              <X size={14} />
            </button>
          </div>
        )}

        <textarea
          className="chat-textarea"
          placeholder="Attribuez une mission à X-Finder... (ex: Recherche les failles CVE récentes, planifie ma réunion, consulte Notion)"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={2}
          disabled={isLoading}
        />

        <div className="input-controls">
          <div className="input-actions-left">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept="image/*"
              style={{ display: 'none' }}
            />
            <button
              type="button"
              className="media-btn"
              onClick={() => fileInputRef.current?.click()}
              title="Joindre une image pour analyse visuelle OSINT"
            >
              <Image size={16} />
              <span>Image / Média</span>
            </button>
          </div>

          <button
            type="button"
            className="send-btn"
            disabled={(!text.trim() && !imageBase64) || isLoading}
            onClick={handleSubmit}
          >
            {isLoading ? (
              <span className="typing-indicator">
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </span>
            ) : (
              <>
                <span>Exécuter</span>
                <Send size={15} />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
