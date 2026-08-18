import React, { useState, useEffect } from 'react';
import CenteredModal from './CenteredModal';
import { createClient, fetchAccessInfo } from '../../services/api';

export default function AddClientModal({ isOpen, onClose, onClientCreated, existingClients = [] }) {
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [claims, setClaims] = useState('Vendor hosted');
  const [email, setEmail] = useState('');
  const [owner, setOwner] = useState('Vikram J.');
  const [owners, setOwners] = useState([]);
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function loadOwners() {
      try {
        const data = await fetchAccessInfo();
        if (data && data.staff) {
          setOwners(data.staff);
          if (data.staff.length > 0) {
            setOwner(data.staff[0].person);
          }
        }
      } catch (err) {
        console.error('Failed to load owners:', err);
      }
    }
    if (isOpen) {
      loadOwners();
    }
  }, [isOpen]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    const trimmedName = name.trim();
    const trimmedCode = code.trim();

    if (!trimmedName) {
      setErrorMsg('Client legal name is required.');
      return;
    }

    // Client-side duplicate check (case-insensitive name & code)
    if (existingClients.some(c => c.name && c.name.toLowerCase() === trimmedName.toLowerCase())) {
      setErrorMsg(`Duplicate client: A client named "${trimmedName}" already exists in the system.`);
      return;
    }
    if (trimmedCode && existingClients.some(c => (c.code && c.code.toLowerCase() === trimmedCode.toLowerCase()) || (c.id && c.id.toLowerCase() === trimmedCode.toLowerCase()))) {
      setErrorMsg(`Duplicate client identifier: Client code "${trimmedCode}" is already in use.`);
      return;
    }

    if (email.trim()) {
      const emailPattern = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
      if (!emailPattern.test(email.trim())) {
        setErrorMsg('Invalid email address format.');
        return;
      }
    }

    setLoading(true);
    try {
      const response = await createClient({
        name: trimmedName,
        code: trimmedCode || undefined,
        claimsSystem: claims,
        contactInfo: email.trim() || undefined,
        owner: owner
      });
      
      await onClientCreated(response.client);
      setName('');
      setCode('');
      setEmail('');
      setErrorMsg('');
      setClaims('Vendor hosted');
      setOwner('Vikram J.');
      onClose();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to create client.');
    } finally {
      setLoading(false);
    }
  };

  const handleCloseModal = () => {
    setErrorMsg('');
    onClose();
  };

  return (
    <CenteredModal isOpen={isOpen} onClose={handleCloseModal}>
      <div className="modal-t">Add New Client</div>
      <p className="modal-b">Create a client record in the database and automatically generate their sequential onboarding compliance workflow.</p>
      
      {errorMsg && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          color: '#ef4444',
          borderRadius: '6px',
          padding: '10px 14px',
          fontSize: '13px',
          marginBottom: '16px',
          fontWeight: 500
        }}>
          ⚠️ {errorMsg}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="field">
          <label>Client Legal Name *</label>
          <input
            placeholder="e.g. Apex Health Plan, Inc."
            value={name}
            onChange={(e) => { setName(e.target.value); setErrorMsg(''); }}
            required
            autoFocus
          />
        </div>
        <div className="field">
          <label>Client Code / Identifier</label>
          <input
            placeholder="e.g. APEXHP"
            value={code}
            onChange={(e) => { setCode(e.target.value); setErrorMsg(''); }}
          />
        </div>
        <div className="field">
          <label>Claims System</label>
          <select value={claims} onChange={(e) => setClaims(e.target.value)}>
            <option value="Vendor hosted">Vendor hosted</option>
            <option value="In-house">In-house</option>
            <option value="Legacy AS/400">Legacy AS/400</option>
            <option value="Other">Other Custom System</option>
          </select>
        </div>
        <div className="field">
          <label>Primary Contact Email</label>
          <input
            type="email"
            placeholder="contact@apex.example"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Assigned Account Owner</label>
          <select value={owner} onChange={(e) => setOwner(e.target.value)}>
            {owners.length > 0 ? (
              owners.map((o, idx) => (
                <option key={idx} value={o.person}>{o.person}</option>
              ))
            ) : (
              <>
                <option value="Vikram J.">Vikram J.</option>
                <option value="Rushi">Rushi</option>
                <option value="Prajval">Prajval</option>
              </>
            )}
          </select>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '18px' }}>
          <button type="button" className="btn" onClick={handleCloseModal}>Cancel</button>
          <button type="submit" className="btn primary" disabled={loading}>
            {loading ? 'Creating...' : 'Create Client'}
          </button>
        </div>
      </form>
    </CenteredModal>
  );
}
