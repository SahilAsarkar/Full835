import React, { useState, useEffect } from 'react';
import { fetchAccessInfo } from '../services/api';

export default function AccessView({ currentUser }) {
  const [accessData, setAccessData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    loadAccess();
  }, []);

  async function loadAccess() {
    setLoading(true);
    setErrorMessage('');
    try {
      const data = await fetchAccessInfo();
      setAccessData(data);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load access information');
    } finally {
      setLoading(false);
    }
  }

  function formatDate(isoStr) {
    if (!isoStr) return '—';
    try {
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return isoStr;
      const dd = String(d.getDate()).padStart(2, '0');
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const yyyy = d.getFullYear();
      const hh = String(d.getHours()).padStart(2, '0');
      const min = String(d.getMinutes()).padStart(2, '0');
      return `${dd}/${mm}/${yyyy} ${hh}:${min}`;
    } catch (e) {
      return isoStr;
    }
  }

  return (
    <section className="view on" id="v-access">
      <div className="hdr-row">
        <div>
          <div className="eyebrow">Security Controls</div>
          <h1 style={{ margin: 0 }}>Access Matrix</h1>
          <p className="sub">Administrative staff role-based access and break-glass logging.</p>
        </div>
      </div>

      <div className="metrics">
        <div className="metric">
          <div className="v">{currentUser?.name || 'Vikram J.'}</div>
          <div className="l">Current Admin</div>
          <div className="d">{currentUser?.role || 'Platform Admin'}</div>
        </div>
        <div className="metric">
          <div className="v" style={{ fontSize: '18px' }}>
            {accessData?.last_login ? formatDate(accessData.last_login) : accessData ? 'Never' : 'Loading...'}
          </div>
          <div className="l">Last Login</div>
          <div className="d">Dynamic database record</div>
        </div>
        <div className="metric">
          <div className="v">Hardware Key</div>
          <div className="l">MFA Status</div>
          <div className="d">FIDO2 / WebAuthn</div>
        </div>
        <div className="metric">
          <div className="v">Active</div>
          <div className="l">Session State</div>
          <div className="d">30-min auto-expire</div>
        </div>
      </div>

      {errorMessage && (
        <div className="note" style={{ background: 'var(--brick-bg)', borderColor: 'var(--brick)', color: 'var(--brick)' }}>
          <b>Error:</b> {errorMessage}
        </div>
      )}

      {loading && !accessData ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--ink-3)' }}>
          Loading access controls &amp; login logs...
        </div>
      ) : (
        <>
          <h2 className="sec">Administrative Staff Access</h2>
          <table style={{ width: '100%', tableLayout: 'fixed' }}>
            <thead>
              <tr>
                <th>Person</th>
                <th>Role</th>
                <th>Access Level</th>
                <th>MFA Status</th>
                <th>Last Login</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {(accessData?.staff || []).map((member, idx) => (
                <tr key={idx}>
                  <td><b>{member.person}</b></td>
                  <td>{member.role}</td>
                  <td><span className="tag ok">{member.access}</span></td>
                  <td><span className="tag ok">{member.mfa}</span></td>
                  <td className="num">{formatDate(member.last_login)}</td>
                  <td><span className="tag ok">{member.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>

          <h2 className="sec">Recent Administrator Login History</h2>
          <table style={{ width: '100%', tableLayout: 'fixed' }}>
            <thead>
              <tr>
                <th>Login Timestamp</th>
                <th>Admin Username</th>
                <th>IP Address</th>
                <th>Client User Agent</th>
                <th>Status</th>
                <th>Logout Time</th>
              </tr>
            </thead>
            <tbody>
              {(accessData?.recent_logins || []).length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', color: 'var(--ink-3)', padding: '16px' }}>
                    No recent logins recorded.
                  </td>
                </tr>
              ) : (
                (accessData?.recent_logins || []).map((log) => (
                  <tr key={log.id}>
                    <td className="num">{formatDate(log.login_time)}</td>
                    <td><b>{log.username}</b></td>
                    <td><code>{log.ip_address}</code></td>
                    <td style={{ fontSize: '12px', color: 'var(--ink-2)', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {log.user_agent}
                    </td>
                    <td>
                      <span className={`tag ${log.status === 'SUCCESS' ? 'ok' : 'bad'}`}>
                        {log.status}
                      </span>
                    </td>
                    <td className="num">{formatDate(log.logout_time)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
