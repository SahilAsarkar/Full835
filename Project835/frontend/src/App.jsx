import React, { useState, useEffect, useCallback } from "react";
import Topbar from "./components/Topbar";
import Drawer from "./components/Drawer";
import FileViewerModal from "./components/FileViewerModal";
import SftpBrowserModal from "./components/SftpBrowserModal";

import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import TotpSetupPage from "./pages/TotpSetupPage";
import TotpVerifyPage from "./pages/TotpVerifyPage";

import FlowView from "./pages/FlowView";
import ConversionsView from "./pages/ConversionsView";
import NoticesView from "./pages/NoticesView";
import ArchiveView from "./pages/ArchiveView";
import ConnectionsView from "./pages/ConnectionsView";

// MIR Admin integrated components
import ClientsTable from "./components/miradmin/ClientsTable";
import OnboardingLadder from "./components/miradmin/OnboardingLadder";
import DocumentsView from "./components/miradmin/DocumentsView";
import TestEnvironmentView from "./components/miradmin/TestEnvironmentView";
import GoLiveView from "./components/miradmin/GoLiveView";
import AccessView from "./components/miradmin/AccessView";
import MappingApp from "./components/miradmin/MappingTool/MappingApp";
import AddClientModal from "./components/miradmin/modals/AddClientModal";
import NotesModal from "./components/miradmin/modals/NotesModal";
import AddRoleModal from "./components/miradmin/modals/AddRoleModal";
import RedoConfirmModal from "./components/miradmin/modals/RedoConfirmModal";
import {
  fetchClients,
  fetchClientState,
  deleteClient,
  redoStep,
  fetchEmployeeRoles,
  fetchAuditLogs
} from "./services/miradmin/api";

export default function App() {
  const [userState, setUserState] = useState(null); // { authenticated: bool, user: { name, email, totp_enabled, totp_verified } }
  const [loadingUser, setLoadingUser] = useState(true);
  const [activeTab, setActiveTab] = useState(() => {
    try {
      return localStorage.getItem("activeTab") || "flow";
    } catch (e) {
      return "flow";
    }
  });
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    try {
      localStorage.setItem("activeTab", tab);
    } catch (e) {}
    setIsDrawerOpen(false);
  };

  // Modals state
  const [viewerFileId, setViewerFileId] = useState(null);
  const [sftpBrowserState, setSftpBrowserState] = useState(null);

  // Dashboard live data state
  const [metrics, setMetrics] = useState({});
  const [trackedFiles, setTrackedFiles] = useState([]);
  const [sftpConfigs, setSftpConfigs] = useState([]);
  const [activeSftpConfig, setActiveSftpConfig] = useState(null);

  // Fetch initial user status
  const checkUserStatus = useCallback(async () => {
    try {
      const res = await fetch("/accounts/api/user/");
      const data = await res.json();
      setUserState(data);
    } catch (e) {
      setUserState({ authenticated: false, user: null });
    } finally {
      setLoadingUser(false);
    }
  }, []);

  useEffect(() => {
    checkUserStatus();
  }, [checkUserStatus]);

  // MIR Admin State
  const [clients, setClients] = useState([]);
  const [activeClientId, setActiveClientId] = useState('');
  const [clientState, setClientState] = useState(null);
  const [clientStateLoading, setClientStateLoading] = useState(false);
  const [roles, setRoles] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditModuleFilter, setAuditModuleFilter] = useState('');
  const [auditClientFilter, setAuditClientFilter] = useState('');

  // MIR Modals State
  const [isAddClientOpen, setIsAddClientOpen] = useState(false);
  const [isNotesOpen, setIsNotesOpen] = useState(false);
  const [activeNoteTarget, setActiveNoteTarget] = useState({ stepKey: '', stepTitle: '' });
  const [isAddRoleOpen, setIsAddRoleOpen] = useState(false);
  const [isRedoOpen, setIsRedoOpen] = useState(false);
  const [redoTarget, setRedoTarget] = useState({ stepKey: '', stepNum: null });
  const [redoLoading, setRedoLoading] = useState(false);

  const loadClients = useCallback(async () => {
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
  }, [activeClientId]);

  const loadRoles = useCallback(async () => {
    try {
      const data = await fetchEmployeeRoles();
      setRoles(data.roles || []);
    } catch (err) {
      console.error('Failed to load employee roles:', err);
    }
  }, []);

  const loadAuditLogs = useCallback(async (cid = auditClientFilter, mod = auditModuleFilter) => {
    try {
      const logs = await fetchAuditLogs(cid, mod);
      setAuditLogs(logs);
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    }
  }, [auditClientFilter, auditModuleFilter]);

  const loadClientWorkflow = useCallback(async (clientId) => {
    if (!clientId) return;
    setClientStateLoading(true);
    try {
      const state = await fetchClientState(clientId);
      setClientState(state);
    } catch (err) {
      console.error('Failed to load client workflow:', err);
    } finally {
      setClientStateLoading(false);
    }
  }, []);

  useEffect(() => {
    if (userState && userState.authenticated && userState.user?.totp_verified) {
      loadClients();
      loadRoles();
      loadAuditLogs();
    }
  }, [userState, loadClients, loadRoles, loadAuditLogs]);

  useEffect(() => {
    if (activeTab === 'mir_audit') {
      loadAuditLogs(auditClientFilter, auditModuleFilter);
    }
  }, [activeTab, auditClientFilter, auditModuleFilter, loadAuditLogs]);

  useEffect(() => {
    if (activeClientId) {
      loadClientWorkflow(activeClientId);
    }
  }, [activeClientId, loadClientWorkflow]);

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
        handleTabChange('mir_clients');
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

  // Dashboard Data Refresh
  const refreshDashboardData = useCallback(async () => {
    if (!userState || !userState.authenticated) return;
    try {
      const [mRes, tRes, sRes] = await Promise.all([
        fetch("/edi835/api/metrics/"),
        fetch("/edi835/api/tracked-files/"),
        fetch("/edi835/api/sftp/get/"),
      ]);

      if (mRes.ok) {
        const mData = await mRes.json();
        setMetrics(mData);
      }
      if (tRes.ok) {
        const tData = await tRes.json();
        setTrackedFiles(tData.files || []);
      }
      if (sRes.ok) {
        const sData = await sRes.json();
        setSftpConfigs(sData.configurations || []);
        setActiveSftpConfig(sData.active_config || null);
      }
    } catch (e) {
      console.warn("Failed refreshing dashboard data:", e);
    }
  }, [userState]);

  useEffect(() => {
    if (userState && userState.authenticated && userState.user?.totp_verified) {
      refreshDashboardData();
      const interval = setInterval(refreshDashboardData, 3000);
      return () => clearInterval(interval);
    }
  }, [userState, refreshDashboardData]);

  const handleLogout = async () => {
    try {
      await fetch("/accounts/api/logout/", { method: "POST" });
    } catch (e) {
      console.warn("Logout error:", e);
    }
    setUserState({ authenticated: false, user: null });
  };

  const handleLoginSuccess = (data) => {
    checkUserStatus();
  };

  const handleSignupSuccess = (data) => {
    checkUserStatus();
  };

  const handleTotpVerified = () => {
    checkUserStatus();
  };

  if (loadingUser) {
    return (
      <div
        style={{
          display: "flex",
          height: "100vh",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "var(--body)",
          color: "var(--ink-2)",
        }}
      >
        Loading MIR Relay...
      </div>
    );
  }

  // Auth Routing Guard logic
  if (!userState || !userState.authenticated) {
    return (
      <div>
        <Topbar user={null} onToggleDrawer={() => {}} onLogout={() => {}} />
        <LoginPage
          onLoginSuccess={handleLoginSuccess}
          onNavigate={(page) => {
            if (page === "signup") {
              setUserState({ authenticated: false, showSignup: true });
            }
          }}
        />
      </div>
    );
  }

  if (userState.showSignup) {
    return (
      <div>
        <Topbar user={null} onToggleDrawer={() => {}} onLogout={() => {}} />
        <SignupPage
          onSignupSuccess={handleSignupSuccess}
          onNavigate={(page) => {
            if (page === "login") {
              setUserState({ authenticated: false, showSignup: false });
            }
          }}
        />
      </div>
    );
  }

  const user = userState.user;
  if (!user.totp_enabled) {
    return (
      <div>
        <Topbar user={user} onToggleDrawer={() => {}} onLogout={handleLogout} />
        <TotpSetupPage
          onSetupSuccess={checkUserStatus}
          onGoDashboard={checkUserStatus}
        />
      </div>
    );
  }

  if (!user.totp_verified) {
    return (
      <div>
        <Topbar user={user} onToggleDrawer={() => {}} onLogout={handleLogout} />
        <TotpVerifyPage onVerifySuccess={handleTotpVerified} />
      </div>
    );
  }

  // Logged-in & 2FA Verified SPA View
  return (
    <div>
      <Topbar
        user={user}
        onToggleDrawer={() => setIsDrawerOpen(!isDrawerOpen)}
        onLogout={handleLogout}
      />

      <div className="shell">
        <Drawer
          isOpen={isDrawerOpen}
          activeTab={activeTab}
          onSelectTab={handleTabChange}
          onClose={() => setIsDrawerOpen(false)}
        />

        <main className="main">
          {activeTab === "flow" && (
            <FlowView
              metrics={metrics}
              recentFiles={trackedFiles}
              inboundConfig={activeSftpConfig}
              outboundConfig={activeSftpConfig}
              onNavigateTab={handleTabChange}
            />
          )}

          {activeTab === "batches" && (
            <ConversionsView
              trackedFiles={trackedFiles}
              onRefreshData={refreshDashboardData}
              onOpenFileModal={(id) => setViewerFileId(id)}
            />
          )}

          {activeTab === "notices" && <NoticesView />}

          {activeTab === "archive" && (
            <ArchiveView
              metrics={metrics}
              trackedFiles={trackedFiles}
              sftpConfig={activeSftpConfig}
              onRefreshData={refreshDashboardData}
              onOpenFileModal={(id) => setViewerFileId(id)}
            />
          )}

          {activeTab === "conn" && (
            <ConnectionsView
              sftpConfigs={sftpConfigs}
              activeConfig={activeSftpConfig}
              onRefreshSftp={refreshDashboardData}
              onOpenSftpBrowser={(params) => setSftpBrowserState(params)}
            />
          )}

          {/* Integrated MIR Administration Views */}
          {activeTab === "mir_clients" && (
            <ClientsTable
              clients={clients}
              onSelectClient={(clientId) => {
                handleSelectClient(clientId);
                handleTabChange("mir_onboard");
              }}
              onOpenAddClient={() => setIsAddClientOpen(true)}
              onDeleteClient={handleDeleteClient}
            />
          )}

          {activeTab === "mir_onboard" && (
            clientStateLoading ? (
              <section className="view on" id="v-onboard">
                <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--ink-2)' }}>
                  <div style={{ fontSize: 24, marginBottom: 12 }}>⏳ Loading Onboarding Ladder...</div>
                  <p>Fetching client compliance state and onboarding steps...</p>
                </div>
              </section>
            ) : clientState ? (
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
            ) : (
              <section className="view on" id="v-onboard">
                <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--ink-2)' }}>
                  <div style={{ fontSize: 24, marginBottom: 12 }}>📋 Select a Client</div>
                  <p style={{ marginBottom: 20 }}>Please select a client from the Client Directory or dropdown to view their Onboarding Ladder.</p>
                  {clients.length > 0 ? (
                    <select
                      value={activeClientId || ''}
                      onChange={(e) => handleSelectClient(e.target.value)}
                      style={{ padding: '8px 16px', fontSize: '14px', borderRadius: '6px' }}
                    >
                      <option value="" disabled>-- Select Client --</option>
                      {clients.map(c => (
                        <option key={c.id} value={c.id}>{c.name} ({c.id})</option>
                      ))}
                    </select>
                  ) : (
                    <button className="btn p" onClick={() => setIsAddClientOpen(true)}>+ Add First Client</button>
                  )}
                </div>
              </section>
            )
          )}

          {activeTab === "mir_docs" && (
            <DocumentsView
              clients={clients}
              activeClientId={activeClientId}
              onSelectClient={handleSelectClient}
            />
          )}

          {activeTab === "mir_mapping" && <MappingApp />}

          {activeTab === "mir_sandbox" && (
            <TestEnvironmentView
              clients={clients}
              activeClientId={activeClientId}
              onSelectClient={handleSelectClient}
            />
          )}

          {activeTab === "mir_promote" && (
            <GoLiveView
              clients={clients}
              activeClientId={activeClientId}
              onSelectClient={handleSelectClient}
              onClientUpdated={() => { loadClients(); loadClientWorkflow(activeClientId); }}
            />
          )}

          {activeTab === "mir_trust" && (
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
            </section>
          )}

          {activeTab === "mir_access" && (
            <AccessView currentUser={user} />
          )}

          {activeTab === "mir_audit" && (
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
        </main>
      </div>

      {/* Modals */}
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

      {/* Modals */}
      <FileViewerModal
        fileId={viewerFileId}
        onClose={() => setViewerFileId(null)}
      />

      {sftpBrowserState && (
        <SftpBrowserModal
          isOpen={!!sftpBrowserState}
          initialPath={sftpBrowserState.initialPath}
          configId={activeSftpConfig ? activeSftpConfig.id : null}
          sftpUniHost={sftpBrowserState.host}
          sftpUniPort={sftpBrowserState.port}
          sftpUniUser={sftpBrowserState.user}
          sftpUniPass={sftpBrowserState.pass}
          sftpUniSshKey={sftpBrowserState.sshKey}
          sftpUniAuth={sftpBrowserState.auth}
          onSelectFolder={sftpBrowserState.onSelectFolder}
          onClose={() => setSftpBrowserState(null)}
        />
      )}
    </div>
  );
}
