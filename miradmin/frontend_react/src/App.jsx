import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import ClientsTable from './components/ClientsTable';
import OnboardingLadder from './components/OnboardingLadder';
import DocumentsView from './components/DocumentsView';
import TestEnvironmentView from './components/TestEnvironmentView';
import GoLiveView from './components/GoLiveView';
import AccessView from './components/AccessView';
import AddClientModal from './components/modals/AddClientModal';
import NotesModal from './components/modals/NotesModal';
import AddRoleModal from './components/modals/AddRoleModal';
import RedoConfirmModal from './components/modals/RedoConfirmModal';
import LoginGate from './components/login/LoginGate';
import MappingApp from './components/MappingTool/MappingApp';

import { fetchClients, fetchClientState, createClient, deleteClient, redoStep, fetchEmployeeRoles, fetchAuditLogs, logoutAdmin } from './services/api';

export default function App() {
  const isMappingRoute = window.location.pathname.startsWith('/mapping');
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return Boolean(localStorage.getItem('onesmarter_admin_token'));
  });
  const [currentUser, setCurrentUser] = useState(() => {
    const saved = localStorage.getItem('onesmarter_admin_user');
    try {
      return saved ? JSON.parse(saved) : null;
    } catch (e) {
      return null;
    }
  });

  const [clients, setClients] = useState([]);
  const [activeClientId, setActiveClientId] = useState('');
  const [clientState, setClientState] = useState(null);
  const [activeNav, setActiveNav] = useState('clients'); // default to All Clients page
  const [roles, setRoles] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditModuleFilter, setAuditModuleFilter] = useState('');
  const [auditClientFilter, setAuditClientFilter] = useState('');

  // Modal states
  const [isAddClientOpen, setIsAddClientOpen] = useState(false);
  const [isNotesOpen, setIsNotesOpen] = useState(false);
  const [activeNoteTarget, setActiveNoteTarget] = useState({ stepKey: '', stepTitle: '' });
  const [isAddRoleOpen, setIsAddRoleOpen] = useState(false);
  const [isRedoOpen, setIsRedoOpen] = useState(false);
  const [redoTarget, setRedoTarget] = useState({ stepKey: '', stepNum: null });
  const [redoLoading, setRedoLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      loadClients();
      loadRoles();
      loadAuditLogs();
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (activeNav === 'audit') {
      loadAuditLogs(auditClientFilter, auditModuleFilter);
    }
  }, [activeNav, auditClientFilter, auditModuleFilter]);

  useEffect(() => {
    if (activeClientId) {
      loadClientWorkflow(activeClientId);
    }
  }, [activeClientId]);

  const loadClients = async () => {
    try {
      const data = await fetchClients();
      const list = data.results || data || [];
      setClients(list);
      if (list.length > 0 && !activeClientId) {
        setActiveClientId(list[0].id);
      }
    } catch (err) {
      console.error('Failed to load clients:', err);
    }
  };

  const loadRoles = async () => {
    try {
      const data = await fetchEmployeeRoles();
      setRoles(data.roles || []);
    } catch (err) {
      console.error('Failed to load employee roles:', err);
    }
  };

  const loadAuditLogs = async (cid = auditClientFilter, mod = auditModuleFilter) => {
    try {
      const logs = await fetchAuditLogs(cid, mod);
      setAuditLogs(logs);
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    }
  };

  const loadClientWorkflow = async (clientId) => {
    try {
      const state = await fetchClientState(clientId);
      setClientState(state);
    } catch (err) {
      console.error('Failed to load client workflow:', err);
    }
  };

  const handleSelectClient = (clientId) => {
    setActiveClientId(clientId);
    loadClientWorkflow(clientId);
  };

  const handleDeleteClient = async (clientId) => {
    if (!window.confirm("Are you sure you want to permanently delete (revoke) this client?")) return;
    try {
      await deleteClient(clientId);
      loadClients();
      if (activeClientId === clientId) {
        setActiveClientId(null);
        setClientState(null);
        setActiveNav('clients');
      }
    } catch (err) {
      console.error('Failed to delete client:', err);
      alert('Failed to delete client: ' + err.message);
    }
  };

  const handleClientCreated = (newClient) => {
    loadClients();
    setActiveClientId(newClient.id);
    loadClientWorkflow(newClient.id);
  };

  const handleOpenNotes = (stepKey, stepTitle) => {
    setActiveNoteTarget({ stepKey, stepTitle });
    setIsNotesOpen(true);
  };

  const handleOpenRedo = (stepKey, stepNum) => {
    setRedoTarget({ stepKey, stepNum });
    setIsRedoOpen(true);
  };

  const handleConfirmRedo = async () => {
    if (!redoTarget.stepKey || !activeClientId) return;
    setRedoLoading(true);
    try {
      await redoStep(activeClientId, redoTarget.stepKey);
      await loadClientWorkflow(activeClientId);
      await loadClients();
      setIsRedoOpen(false);
    } catch (err) {
      alert(`Redo failed: ${err.message}`);
    } finally {
      setRedoLoading(false);
    }
  };

  const handleLoginSuccess = (res) => {
    if (res && res.user) {
      localStorage.setItem('onesmarter_admin_user', JSON.stringify(res.user));
      setCurrentUser(res.user);
    }
    setIsAuthenticated(true);
  };

  const handleSignOut = async () => {
    await logoutAdmin();
    localStorage.removeItem('onesmarter_admin_token');
    localStorage.removeItem('onesmarter_admin_user');
    setCurrentUser(null);
    setIsAuthenticated(false);
  };

  const currentClient = clients.find(c => c.id === activeClientId) || clients[0];

  if (!isAuthenticated) {
    return <LoginGate onLoginSuccess={handleLoginSuccess} />;
  }

  if (isMappingRoute) {
    return <MappingApp />;
  }

  return (
    <>
      <Header
        clients={clients}
        activeClientId={activeClientId}
        onSelectClient={handleSelectClient}
        activeClientName={currentClient?.name}
        onSignOut={handleSignOut}
        showClientBadge={['onboard', 'docs', 'sandbox', 'promote'].includes(activeNav)}
        currentUser={currentUser}
      />

      <div className="shell">
        {/* Left Navigation Sidebar matching POC exactly */}
        <nav className="rail">
          <div className="grp eyebrow">Clients</div>
          <button className={`navitem ${activeNav === 'clients' ? 'on' : ''}`} onClick={() => setActiveNav('clients')}>
            <span>All Clients</span>
            <span className="count">{clients.length}</span>
          </button>
          <button className={`navitem ${activeNav === 'onboard' ? 'on' : ''}`} onClick={() => setActiveNav('onboard')}>
            <span>Onboarding</span>
          </button>
          <button className={`navitem ${activeNav === 'docs' ? 'on' : ''}`} onClick={() => setActiveNav('docs')}>
            <span>Documents</span>
          </button>

          <div className="grp eyebrow" style={{ paddingTop: '18px' }}>Pre-Production</div>
          <button className={`navitem ${activeNav === 'sandbox' ? 'on' : ''}`} onClick={() => setActiveNav('sandbox')}>
            <span>Test Environment</span>
          </button>
          <button className={`navitem ${activeNav === 'promote' ? 'on' : ''}`} onClick={() => setActiveNav('promote')}>
            <span>Go Live</span>
          </button>

          <div className="grp eyebrow" style={{ paddingTop: '18px' }}>Governance</div>
          <button className={`navitem ${activeNav === 'trust' ? 'on' : ''}`} onClick={() => setActiveNav('trust')}>
            <span>Trust Center</span>
          </button>
          <button className={`navitem ${activeNav === 'access' ? 'on' : ''}`} onClick={() => setActiveNav('access')}>
            <span>Access</span>
          </button>
          <button className={`navitem ${activeNav === 'audit' ? 'on' : ''}`} onClick={() => setActiveNav('audit')}>
            <span>Audit Log</span>
          </button>

          <div className="grp eyebrow" style={{ paddingTop: '18px' }}>Operations</div>
          <button className={`navitem ${activeNav === 'ops' ? 'on' : ''}`} onClick={() => setActiveNav('ops')}>
            <span>Operations</span>
          </button>
          <button className={`navitem ${activeNav === 'offboard' ? 'on' : ''}`} onClick={() => setActiveNav('offboard')}>
            <span>Offboarding</span>
          </button>
        </nav>

        <main className="main">
          {activeNav === 'clients' && (
            <ClientsTable
              clients={clients}
              onSelectClient={(clientId) => {
                handleSelectClient(clientId);
                setActiveNav('onboard');
              }}
              onOpenAddClient={() => setIsAddClientOpen(true)}
              onDeleteClient={handleDeleteClient}
            />
          )}

          {activeNav === 'onboard' && clientState && (
            <OnboardingLadder
              client={clientState.client}
              steps={clientState.steps}
              roles={roles}
              clients={clients}
              onSelectClient={handleSelectClient}
              onRefresh={() => { loadClients(); loadClientWorkflow(activeClientId); }}
              onOpenNotes={handleOpenNotes}
              onOpenRedo={handleOpenRedo}
              onOpenAddRole={() => setIsAddRoleOpen(true)}
            />
          )}

          {activeNav === 'docs' && (
            <DocumentsView
              clients={clients}
              activeClientId={activeClientId}
              onSelectClient={handleSelectClient}
            />
          )}

          {activeNav === 'sandbox' && (
            <TestEnvironmentView
              clients={clients}
              activeClientId={activeClientId}
              onSelectClient={handleSelectClient}
            />
          )}

          {activeNav === 'promote' && (
            <GoLiveView
              clients={clients}
              activeClientId={activeClientId}
              onSelectClient={handleSelectClient}
              onClientUpdated={() => { loadClients(); loadClientWorkflow(activeClientId); }}
            />
          )}

          {activeNav === 'trust' && (
            <section className="view on" id="v-trust">
              <div className="hdr-row">
                <div>
                  <div className="eyebrow">Compliance Assurance</div>
                  <h1>Trust Center</h1>
                  <p className="sub">Security, encryption, HIPAA safeguards, and compliance attestations.</p>
                </div>
              </div>
              <div className="metrics">
                <div className="metric">
                  <div className="v" style={{ fontSize: '20px', fontWeight: 600 }}>SOC 2 Type II</div>
                  <div className="l">
                    <span className="tag ok">Attested</span>
                  </div>
                  <div className="d">Report available under NDA</div>
                </div>
                <div className="metric">
                  <div className="v" style={{ fontSize: '20px', fontWeight: 600 }}>ISO 27001</div>
                  <div className="l">
                    <span className="tag ok">Certified</span>
                  </div>
                  <div className="d">Surveillance audit Q1 2026</div>
                </div>
                <div className="metric">
                  <div className="v" style={{ fontSize: '20px', fontWeight: 600 }}>HIPAA Audit</div>
                  <div className="l">
                    <span className="tag ok">Audited</span>
                  </div>
                  <div className="d">Safeguards verified</div>
                </div>
                <div className="metric">
                  <div className="v" style={{ fontSize: '20px', fontWeight: 600 }}>Post-Quantum</div>
                  <div className="l">
                    <span className="tag ok">Encrypted</span>
                  </div>
                  <div className="d">ML-DSA-65 signatures</div>
                </div>
              </div>

              <h2 className="sec">Security Policies &amp; Standards</h2>
              <table style={{ width: '100%', tableLayout: 'fixed' }}>
                <thead>
                  <tr>
                    <th>Policy / Document</th>
                    <th>Standard</th>
                    <th>Status</th>
                    <th>Last Reviewed</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><b>Information Security Policy</b></td>
                    <td>ISO 27001:2022</td>
                    <td><span className="tag ok">Published</span></td>
                    <td className="num">15 Jan 2026</td>
                  </tr>
                  <tr>
                    <td><b>Incident Response Plan</b></td>
                    <td>NIST SP 800-61</td>
                    <td><span className="tag ok">Active</span></td>
                    <td className="num">10 Feb 2026</td>
                  </tr>
                  <tr>
                    <td><b>HIPAA Security Rule Safeguards</b></td>
                    <td>45 CFR Part 160/164</td>
                    <td><span className="tag ok">Compliant</span></td>
                    <td className="num">02 Feb 2026</td>
                  </tr>
                  <tr>
                    <td><b>Access Control Policy</b></td>
                    <td>SOC 2 CC6.0</td>
                    <td><span className="tag ok">Published</span></td>
                    <td className="num">18 Jan 2026</td>
                  </tr>
                </tbody>
              </table>
            </section>
          )}

          {activeNav === 'access' && (
            <AccessView currentUser={currentUser} />
          )}

          {activeNav === 'audit' && (
            <section className="view on" id="v-audit">
              <div className="hdr-row">
                <div>
                  <div className="eyebrow">Append Only Audit</div>
                  <h1>Audit Log</h1>
                  <p className="sub">Immutable audit trail of all client onboarding, document, test, go-live, and administrative actions.</p>
                </div>
              </div>

              <div className="filters" style={{ borderBottom: '1px solid var(--line)', marginBottom: '16px' }}>
                <select
                  value={auditClientFilter}
                  onChange={e => setAuditClientFilter(e.target.value)}
                >
                  <option value="">All Clients</option>
                  {clients.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>

                <select
                  value={auditModuleFilter}
                  onChange={e => setAuditModuleFilter(e.target.value)}
                >
                  <option value="">All Modules</option>
                  <option value="CLIENTS">Clients</option>
                  <option value="DOCUMENTS">Documents</option>
                  <option value="ONBOARDING">Onboarding</option>
                  <option value="TEST_ENV">Test Environment</option>
                  <option value="GO_LIVE">Go Live</option>
                  <option value="AUTH">Authentication</option>
                  <option value="SYSTEM">System</option>
                </select>

                <span className="n">{auditLogs.length} Events Recorded</span>
              </div>

              <table>
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Module</th>
                    <th>Action</th>
                    <th>Client</th>
                    <th>Details</th>
                    <th>Who</th>
                  </tr>
                </thead>
                <tbody>
                  {auditLogs.length === 0 ? (
                    <tr>
                      <td colSpan="6" style={{ textAlign: 'center', padding: '24px', color: 'var(--ink-3)' }}>
                        No audit log entries found matching criteria.
                      </td>
                    </tr>
                  ) : (
                    auditLogs.map((log) => (
                      <tr key={log.id}>
                        <td className="num">{new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</td>
                        <td><span className="tag" style={{ textTransform: 'uppercase', fontSize: '10px' }}>{log.module || 'SYSTEM'}</span></td>
                        <td><span className="tag ok">{log.action}</span></td>
                        <td><b>{log.client_name || log.client || 'System'}</b></td>
                        <td>{log.details}</td>
                        <td className="num">{log.performed_by || 'Admin User'}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </section>
          )}

          {activeNav === 'ops' && (
            <section className="view on" id="v-ops">
              <div className="eyebrow">Reliability</div>
              <h1>Operations &amp; Delivery</h1>
              <p className="sub">File delivery metrics, silent folder monitoring, and SLA tracking.</p>
              <div className="metrics">
                <div className="metric"><div className="v">99.98%</div><div className="l">Delivery Success</div><div className="d">90-day average</div></div>
                <div className="metric"><div className="v">12m</div><div className="l">Restore Drill</div><div className="d">Completed successfully</div></div>
                <div className="metric"><div className="v">0</div><div className="l">Open Incidents</div><div className="d">Healthy operation</div></div>
              </div>
            </section>
          )}

          {activeNav === 'offboard' && (
            <section className="view on" id="v-offboard">
              <div className="eyebrow">Lifecycle Termination</div>
              <h1>Offboarding Procedures</h1>
              <p className="sub">Cryptographic key destruction and certified data return upon client contract conclusion.</p>
              <div className="ladder">
                <div className="rung"><div className="mark">1</div><div className="txt"><h3>Termination Notice Recorded</h3><div className="meta">Effective date registered in database</div></div></div>
                <div className="rung"><div className="mark">2</div><div className="txt"><h3>Archive Returned to Client</h3><div className="meta">Exported in standard format with intact digital signatures</div></div></div>
                <div className="rung"><div className="mark">3</div><div className="txt"><h3>Tenant Key Destruction</h3><div className="meta">Permanent erasure of wrapped post-quantum tenant keys</div></div></div>
              </div>
            </section>
          )}
        </main>
      </div>

      {/* Viewport Centered Modals */}
      <AddClientModal
        isOpen={isAddClientOpen}
        onClose={() => setIsAddClientOpen(false)}
        onClientCreated={handleClientCreated}
        existingClients={clients}
      />

      <NotesModal
        isOpen={isNotesOpen}
        onClose={() => setIsNotesOpen(false)}
        clientId={activeClientId}
        stepKey={activeNoteTarget.stepKey}
        stepTitle={activeNoteTarget.stepTitle}
      />

      <AddRoleModal
        isOpen={isAddRoleOpen}
        onClose={() => setIsAddRoleOpen(false)}
        onRoleAdded={loadRoles}
      />

      <RedoConfirmModal
        isOpen={isRedoOpen}
        onClose={() => setIsRedoOpen(false)}
        stepNum={redoTarget.stepNum}
        onConfirm={handleConfirmRedo}
        loading={redoLoading}
      />
    </>
  );
}
