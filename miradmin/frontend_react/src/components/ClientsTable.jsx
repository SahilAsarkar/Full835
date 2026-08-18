import React, { useState } from 'react';

function formatDate(dateVal) {
  if (!dateVal) return 'N/A';
  const d = new Date(dateVal);
  if (isNaN(d.getTime())) return dateVal;
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

export default function ClientsTable({ clients, onSelectClient, onOpenAddClient, onDeleteClient }) {
  const [filterStage, setFilterStage] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  const prodCount = clients.filter(c => c.stage === 'production').length;
  const onbCount = clients.filter(c => c.stage !== 'production').length;

  const filteredClients = clients.filter((c) => {
    const matchesStage = filterStage === 'all' || (filterStage === 'production' ? c.stage === 'production' : c.stage !== 'production');
    const searchLower = searchTerm.toLowerCase();
    const matchesSearch =
      c.name.toLowerCase().includes(searchLower) ||
      c.id.toLowerCase().includes(searchLower) ||
      (c.code && c.code.toLowerCase().includes(searchLower)) ||
      (c.owner && c.owner.toLowerCase().includes(searchLower)) ||
      (c.claimsSystem && c.claimsSystem.toLowerCase().includes(searchLower)) ||
      (c.claims_system && c.claims_system.toLowerCase().includes(searchLower));
    return matchesStage && matchesSearch;
  });

  return (
    <section className="view on" id="v-clients">
      <div className="hdr-row">
        <div>
          <div className="eyebrow">Tenants</div>
          <h1>All Clients</h1>
          <p className="sub">Dynamic relational database-driven client registry. Click any client to open their onboarding portal.</p>
        </div>
        <button className="btn primary" id="btn-add-client" onClick={onOpenAddClient}>+ Add Client</button>
      </div>

      <div className="metrics">
        <div className="metric">
          <div className="v" id="stat-prod">{prodCount}</div>
          <div className="l">In Production</div>
          <div className="d">Delivering MIR to MPL</div>
        </div>
        <div className="metric">
          <div className="v" id="stat-onb">{onbCount}</div>
          <div className="l">Onboarding</div>
          <div className="d">Active Sequential Workflow</div>
        </div>
        <div className="metric">
          <div className="v">{clients.length > 0 ? `${Math.round(clients.reduce((acc, c) => acc + (c.progress_pct || 0), 0) / clients.length)}%` : '0%'}</div>
          <div className="l">Average Progress</div>
          <div className="d">Across all client pipelines</div>
        </div>
        <div className="metric">
          <div className="v" id="stat-total">{clients.length}</div>
          <div className="l">Total Tenants</div>
          <div className="d">Managed in Database</div>
        </div>
      </div>

      <div className="filters">
        <select value={filterStage} onChange={(e) => setFilterStage(e.target.value)}>
          <option value="all">All Stages</option>
          <option value="onboarding">In Onboarding</option>
          <option value="production">In Production</option>
        </select>
        <input
          placeholder="Filter clients by name, owner, or identifier…"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        <span className="n">{filteredClients.length} of {clients.length} shown</span>
      </div>

      <table className="clickable">
        <thead>
          <tr>
            <th>Client</th>
            <th>Stage</th>
            <th>Claims System</th>
            <th>Live Since / Started</th>
            <th>Onboarding Progress</th>
            <th>Owner</th>
            <th>State</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="clients-body">
          {filteredClients.length === 0 ? (
            <tr>
              <td colSpan="8" style={{ textAlign: 'center', padding: '32px', color: 'var(--ink-3)' }}>
                No clients match the current filter or search criteria.
              </td>
            </tr>
          ) : (
            filteredClients.map((c) => {
              const isProd = c.stage === 'production';
              const displayOwner = c.owner || 'Unassigned';
              const displayClaims = c.claimsSystem || c.claims_system || 'Unknown';
              const displayState = c.state || 'Unknown';
              const displayDate = formatDate(c.liveSince || c.live_since || c.created_at);

              return (
                <tr key={c.id} onClick={() => onSelectClient(c.id)} title={`Click to view ${c.name} workspace`}>
                  <td>
                    <b>{c.name}</b>
                    <div className="mono" style={{ fontSize: '11px', color: 'var(--ink-3)' }}>{c.code || c.id}</div>
                  </td>
                  <td>
                    <span className={`tag ${isProd ? 'ok' : 'work'}`}>
                      {isProd ? 'Production' : 'Onboarding'}
                    </span>
                  </td>
                  <td>{displayClaims}</td>
                  <td className="num">{displayDate}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ flex: 1, background: 'var(--line)', height: '6px', borderRadius: '3px', overflow: 'hidden' }}>
                        <div style={{ width: `${c.progress_pct}%`, background: isProd ? 'var(--teal)' : 'var(--ochre)', height: '100%' }}></div>
                      </div>
                      <span className="mono" style={{ fontSize: '11px', minWidth: '32px' }}>{c.progress_pct}%</span>
                    </div>
                  </td>
                  <td>
                    <b>{displayOwner}</b>
                  </td>
                  <td>
                    <span className={`tag ${displayState === 'Healthy' ? 'ok' : displayState === 'Our move' ? 'alert' : 'work'}`}>
                      {displayState}
                    </span>
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <button 
                      className="btn tiny" 
                      style={{ background: 'var(--surface-3)', color: 'var(--alert)' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteClient && onDeleteClient(c.id);
                      }}
                      title="Revoke / Delete Client"
                    >
                      Revoke
                    </button>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>

      <div className="note">
        <b>Client-Aware Architecture:</b> Every client maintains an isolated sequential compliance workflow, notes, contacts, transfer setup, and audit records in the database.
      </div>
    </section>
  );
}
