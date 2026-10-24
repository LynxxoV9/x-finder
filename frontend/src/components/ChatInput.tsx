import React, { useEffect, useRef, useState } from 'react';
import { Send, Image, X, Pencil } from 'lucide-react';
import { Language, translations } from '../i18n/translations';

interface ChatInputProps {
  onSend: (message: string, imageBase64?: string) => void;
  isLoading: boolean;
  lang?: Language;
  draftRequest?: { id: number; text: string; imageUrl?: string } | null;
  onDraftConsumed?: () => void;
  onCancelDraft?: () => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  isLoading,
  lang = 'fr',
  draftRequest = null,
  onDraftConsumed,
  onCancelDraft,
}) => {
  const [text, setText] = useState('');
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [imageName, setImageName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const t = translations[lang];

  useEffect(() => {
    if (draftRequest) {
      setText(draftRequest.text);
      setImageBase64(draftRequest.imageUrl || null);
      setImageName(
        draftRequest.imageUrl
          ? (lang === 'fr' ? 'Image jointe' : 'Attached image')
          : null,
      );
      if (fileInputRef.current) fileInputRef.current.value = '';
      textareaRef.current?.focus();
    }
  }, [draftRequest, lang]);

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
    onDraftConsumed?.();
    clearImage();
  };

  const cancelDraft = () => {
    setText('');
    clearImage();
    onCancelDraft?.();
  };

  return (
    <div className="chat-input-area">
      {draftRequest && (
        <div className="edit-draft-notice">
          <Pencil size={14} />
          <span>
            {lang === 'fr'
              ? 'Modifiez la question puis envoyez-la comme nouveau message.'
              : 'Edit the prompt, then send it as a new message.'}
          </span>
          <button type="button" onClick={cancelDraft}>
            {lang === 'fr' ? 'Annuler' : 'Cancel'}
          </button>
        </div>
      )}
      <div className="input-wrapper">
        {/* Aperçu de l'image sélectionnée */}
        {imageBase64 && (
          <div className="image-attachment-chip">
            <Image size={14} />
            <span>{imageName || t.image_attached}</span>
            <button
              onClick={clearImage}
              style={{ background: 'none', border: 'none', color: '#f43f5e', cursor: 'pointer' }}
            >
              <X size={14} />
            </button>
          </div>
        )}

        <textarea
          ref={textareaRef}
          className="chat-textarea"
          placeholder={t.input_placeholder}
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
              title={t.media_btn}
            >
              <Image size={16} />
              <span>{t.media_btn}</span>
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
                <span>{t.send_btn}</span>
                <Send size={15} />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
