import React from 'react';

export default function Header({ clients, activeClientId, onSelectClient, activeClientName, onSignOut, showClientBadge = true, currentUser }) {
  const adminName = currentUser?.name || 'Vikram J.';
  const initials = adminName.split(' ').filter(Boolean).map(n => n[0]).join('').toUpperCase().slice(0, 2) || 'VJ';
  const role = currentUser?.role || 'Platform Admin';

  return (
    <div className="topbar">
      <div className="wordmark">OneSmarter <span>/ MIR Relay Admin</span></div>
      <div className="spacer"></div>
      {showClientBadge && (
        <div className="active-client-badge" id="top-client-badge">
          Client: <b>{activeClientName || 'Northwood'}</b>
        </div>
      )}
      <div className="env env-ok" id="env">Live · Database Connected</div>
      <div className="me">
        <div className="av">{initials}</div>
        <div>
          <div>{adminName}</div>
          <div className="role">{role}</div>
        </div>
      </div>
      <button className="signout" id="signout" onClick={onSignOut}>Sign Out</button>
    </div>
  );
}
