import React from 'react';
import { AlertTriangle, Check, X, Mail, Trash2 } from 'lucide-react';
import { PendingConfirmationItem } from '../types';

interface ConfirmationCardProps {
  confirmation: PendingConfirmationItem;
  onRespond: (id: number, confirmed: boolean) => void;
  isLoading: boolean;
}

export const ConfirmationCard: React.FC<ConfirmationCardProps> = ({
  confirmation,
  onRespond,
  isLoading,
}) => {
  const isEmail = confirmation.action_type === 'send_email';
  const isDelete = confirmation.action_type === 'delete_calendar_event';

  return (
    <div className="confirmation-box">
      <div className="confirmation-header">
        {isEmail ? <Mail size={18} /> : isDelete ? <Trash2 size={18} /> : <AlertTriangle size={18} />}
        <span>Action sensible en attente de confirmation utilisateur</span>
      </div>

      <div className="confirmation-desc">
        {confirmation.description}
      </div>

      {confirmation.payload && (
        <div style={{
          background: 'rgba(0, 0, 0, 0.35)',
          padding: '10px 12px',
          borderRadius: '6px',
          fontSize: '0.8rem',
          fontFamily: 'monospace',
          border: '1px solid rgba(245, 158, 11, 0.25)',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px'
        }}>
          {confirmation.payload.to && <div><strong>Destinataire :</strong> {confirmation.payload.to}</div>}
          {confirmation.payload.subject && <div><strong>Objet :</strong> {confirmation.payload.subject}</div>}
          {confirmation.payload.event_id && <div><strong>Événement ID :</strong> {confirmation.payload.event_id}</div>}
        </div>
      )}

      <div className="confirmation-actions">
        <button
          className="confirm-btn-yes"
          disabled={isLoading}
          onClick={() => onRespond(confirmation.id, true)}
        >
          <Check size={16} />
          <span>{isEmail ? "Valider et Expédier l'Email" : isDelete ? "Confirmer la Suppression" : "Autoriser l'Action"}</span>
        </button>

        <button
          className="confirm-btn-no"
          disabled={isLoading}
          onClick={() => onRespond(confirmation.id, false)}
        >
          <X size={16} />
          <span>Annuler</span>
        </button>
      </div>
    </div>
  );
};
