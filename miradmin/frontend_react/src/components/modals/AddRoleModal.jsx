import React, { useState } from 'react';
import CenteredModal from './CenteredModal';
import { addEmployeeRole } from '../../services/api';

export default function AddRoleModal({ isOpen, onClose, onRoleAdded }) {
  const [roleName, setRoleName] = useState('');
  const [roleDesc, setRoleDesc] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!roleName.trim()) return;
    setLoading(true);
    try {
      await addEmployeeRole(roleName.trim(), roleDesc.trim());
      setRoleName('');
      setRoleDesc('');
      if (onRoleAdded) onRoleAdded();
      onClose();
    } catch (err) {
      alert('Error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <CenteredModal isOpen={isOpen} onClose={onClose}>
      <div className="modal-t">Add Employee Post / Role</div>
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label>Role Name *</label>
          <input
            placeholder="e.g. EDI Support Engineer"
            value={roleName}
            onChange={(e) => setRoleName(e.target.value)}
            required
            autoFocus
          />
        </div>
        <div className="field">
          <label>Description</label>
          <input
            placeholder="Role description or escalation tier"
            value={roleDesc}
            onChange={(e) => setRoleDesc(e.target.value)}
          />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn primary" disabled={loading}>
            {loading ? 'Adding...' : 'Save Role'}
          </button>
        </div>
      </form>
    </CenteredModal>
  );
}
