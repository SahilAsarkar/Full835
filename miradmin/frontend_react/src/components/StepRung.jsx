import React, { useState } from 'react';
import { uploadStepFile, validateStaged835, postStepData, downloadTemplateFile } from '../services/api';
import FeedbackModal from './modals/FeedbackModal';

function formatDateTime(dateVal) {
  if (!dateVal) return 'N/A';
  const d = new Date(dateVal);
  if (isNaN(d.getTime())) return dateVal;
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${dd}/${mm}/${yyyy} ${hh}:${min}`;
}

export default function StepRung({ step, clientId, roles, onRefresh, onOpenNotes, onOpenRedo, onOpenAddRole }) {
  const [feedback, setFeedback] = useState({ isOpen: false, kind: 'ok', title: '', content: '', checks: [] });

  const [s4Name, setS4Name] = useState('');
  const [s4Role, setS4Role] = useState(roles[0]?.role_name || 'Named Contact');
  const [s4Email, setS4Email] = useState('');
  const [s4CountryCode, setS4CountryCode] = useState('+1');
  const [s4Phone, setS4Phone] = useState('');
  const [s4Alt, setS4Alt] = useState('');
  const [s4Ah, setS4Ah] = useState('');

  const [s5Text, setS5Text] = useState(step.extra?.verification?.verification_text || '');
  const [s6Method, setS6Method] = useState(step.extra?.transferConfig?.method || 'SFTP');
  const [s6Status, setS6Status] = useState(step.extra?.transferConfig?.setup_status || 'Configured');
  const [s6Watched, setS6Watched] = useState(Boolean(step.extra?.transferConfig?.watched_folder_sftp));
  const [s6Keys, setS6Keys] = useState(Boolean(step.extra?.transferConfig?.keys_exchanged));
  const [s6NoChange, setS6NoChange] = useState(Boolean(step.extra?.transferConfig?.no_change_to_client_system));
  const [s6Notes, setS6Notes] = useState(step.extra?.transferConfig?.notes || '');

  const [s10Notes, setS10Notes] = useState(step.extra?.submission?.submission_text || '');

  const [s13Date, setS13Date] = useState(step.extra?.schedule?.scheduled_date || '');
  const [s13Time, setS13Time] = useState(step.extra?.schedule?.scheduled_time || '10:00');
  const [s13Tz, setS13Tz] = useState(step.extra?.schedule?.timezone || 'ET');
  const [s13Notes, setS13Notes] = useState(step.extra?.schedule?.notes || '');

  const [stText, setStText] = useState(step.extra?.submission?.submission_text || '');

  const handleStandardFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const res = await uploadStepFile(clientId, step.key, file);
      setFeedback({
        isOpen: true,
        kind: 'ok',
        title: 'Evidence Validated & Stored',
        content: `Uploaded ${file.name} for Step ${step.id}.`,
        checks: res.checks || []
      });
      await onRefresh();
    } catch (err) {
      setFeedback({
        isOpen: true,
        kind: 'bad',
        title: 'Validation Failed',
        content: err.message,
        checks: err.checks || []
      });
    }
  };

  const handleStep7Upload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const ext = file.name.includes('.') ? file.name.split('.').pop().toLowerCase() : '';
    const allowed = ['835', 'x12', 'edi', 'txt', 'dat', '35', 'ansi', 'rem'];
    if (!allowed.includes(ext)) {
      setFeedback({
        isOpen: true,
        kind: 'bad',
        title: 'Upload Error',
        content: `Unsupported file type (.${ext}). Upload a valid 835/X12 file (.835, .x12, .edi, .txt, .dat, .35, .ansi, .rem).`,
        checks: []
      });
      return;
    }
    try {
      await uploadStepFile(clientId, step.key, file);
      setFeedback({
        isOpen: true,
        kind: 'ok',
        title: '835 File Staged',
        content: `Uploaded ${file.name}. Click "✓ Validate 835" to run full structural X12 checks.`,
        checks: []
      });
      await onRefresh();
    } catch (err) {
      setFeedback({
        isOpen: true,
        kind: 'bad',
        title: 'Upload Error',
        content: err.message,
        checks: []
      });
    }
  };

  const handleValidate835 = async () => {
    try {
      const res = await validateStaged835(clientId);
      setFeedback({
        isOpen: true,
        kind: 'ok',
        title: '835 Structural Validation Passed',
        content: 'Step 7 Complete: Deep X12 835 structural and balance checks passed.',
        checks: res.checks || []
      });
      await onRefresh();
    } catch (err) {
      setFeedback({
        isOpen: true,
        kind: 'bad',
        title: '835 Validation Failed',
        content: err.message,
        checks: err.checks || []
      });
      await onRefresh();
    }
  };

  const handleStep4Save = async () => {
    const trimmedName = s4Name.trim();
    if (!trimmedName) { alert('Please enter employee name'); return; }

    // Duplicate check
    const existing = step.extra?.contacts || [];
    if (existing.some(c => (c.employee_name || c.name || '').toLowerCase() === trimmedName.toLowerCase())) {
      alert(`Duplicate entry: An employee contact named "${trimmedName}" already exists for this client.`);
      return;
    }
    if (s4Email.trim() && existing.some(c => (c.email || '').toLowerCase() === s4Email.trim().toLowerCase())) {
      alert(`Duplicate entry: An employee contact with email "${s4Email.trim()}" already exists for this client.`);
      return;
    }
    const fullPhone = s4Phone.trim() ? `${s4CountryCode}${s4Phone.trim()}` : '';

    if (fullPhone && existing.some(c => (c.phone || '').trim() === fullPhone)) {
      alert(`Duplicate entry: An employee contact with phone "${fullPhone}" already exists for this client.`);
      return;
    }

    // Email validation
    if (s4Email.trim()) {
      const emailPattern = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
      if (!emailPattern.test(s4Email.trim())) {
        alert('Invalid email address format.');
        return;
      }
    }

    // Phone validation
    if (fullPhone) {
      const digits = fullPhone.replace(/\D/g, '');
      if (digits.length < 7 || digits.length > 15) {
        alert(`Invalid phone length (${digits.length} digits). Standard international phone numbers must be between 7 and 15 digits.`);
        return;
      }
    }

    try {
      await postStepData(`/clients/${encodeURIComponent(clientId)}/steps/step_4_contacts/save`, {
        role_name: s4Role, employee_name: trimmedName, email: s4Email.trim(), phone: fullPhone,
        alternate_contact: s4Alt.trim(), after_hours_notes: s4Ah.trim()
      });
      setS4Name('');
      setS4Email('');
      setS4Phone('');
      setS4Alt('');
      setS4Ah('');
      await onRefresh();
    } catch (err) { alert('Error: ' + err.message); }
  };

  const handleStep5Save = async () => {
    if (!s5Text.trim()) { alert('Please enter verification text'); return; }
    try {
      await postStepData(`/clients/${encodeURIComponent(clientId)}/steps/step_5_claim_sys/save`, { verification_text: s5Text });
      await onRefresh();
    } catch (err) { alert('Error: ' + err.message); }
  };

  const handleStep6Save = async () => {
    try {
      await postStepData(`/clients/${encodeURIComponent(clientId)}/steps/step_6_transfer_method/save`, {
        method: s6Method, setup_status: s6Status, watched_folder_sftp: s6Watched,
        keys_exchanged: s6Keys, no_change_to_client_system: s6NoChange, notes: s6Notes
      });
      await onRefresh();
    } catch (err) { alert('Error: ' + err.message); }
  };

  const handleStep13Save = async () => {
    if (!s13Date || !s13Time) { alert('Please select date and time'); return; }
    try {
      await postStepData(`/clients/${encodeURIComponent(clientId)}/steps/step_13_schedule/save`, {
        scheduled_date: s13Date, scheduled_time: s13Time, timezone: s13Tz, notes: s13Notes
      });
      await onRefresh();
    } catch (err) { alert('Error: ' + err.message); }
  };

  const handleTextSubmission = async () => {
    if (!stText.trim()) { alert('Please enter required details.'); return; }
    try {
      await postStepData(`/clients/${encodeURIComponent(clientId)}/steps/${encodeURIComponent(step.key)}/submit-text`, { submission_text: stText });
      await onRefresh();
    } catch (err) { alert('Error: ' + err.message); }
  };

  const launchRedirect = (url, pendingKey) => {
    sessionStorage.setItem('pending_return_step', pendingKey);
    window.open(url, '_blank');
  };

  const latestUp = step.latestUpload;
  const isFailed = latestUp && latestUp.validation_status === 'FAILED';

  const stateClass = step.done ? 'done' : (step.inProgress ? 'now' : 'locked');
  const markContent = step.done ? '✓' : (step.inProgress ? step.id : '🔒');
  const statusTag = step.done ? (
    <span className="tag ok">Complete</span>
  ) : step.inProgress ? (
    <span className="tag work">In Progress</span>
  ) : (
    <span className="tag idle">Locked</span>
  );

  return (
    <div className={`rung ${stateClass}`}>
      <div className="mark">{markContent}</div>

      <div className="txt">
        <h3>Step {step.id}: {step.title}</h3>
        <div className="meta">{step.desc}</div>

        {latestUp && (
          <div className="ev">
            📄 Filed: <b>{latestUp.original_filename}</b> ({formatDateTime(latestUp.uploaded_at)})
          </div>
        )}

        {step.latestNote && (
          <div className="ev" style={{ color: 'var(--ochre)' }}>
            💬 Latest Note: "{step.latestNote.note_text}" — <i>{step.latestNote.author}</i>
          </div>
        )}

        {(step.inProgress || step.done) && (
          <>
            {step.actionType === 'contact_manager' && (
              <div className="step-custom-box">
                <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8 }}>After-Hours &amp; Named Staff Management:</div>
                {step.extra?.contacts && step.extra.contacts.length > 0 && (
                  <div style={{ marginBottom: 12, fontSize: 12, background: '#fff', border: '1px solid var(--line-soft)', borderRadius: 2, padding: '8px 10px' }}>
                    <div style={{ fontWeight: 600, color: 'var(--ink-2)', marginBottom: 6, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Recorded Contacts ({step.extra.contacts.length}):</div>
                    {step.extra.contacts.map((c, idx) => (
                      <div key={c.id || idx} style={{ padding: '4px 0', borderBottom: idx < step.extra.contacts.length - 1 ? '1px solid var(--line-soft)' : 'none', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          👤 <b>{c.employee_name || c.name}</b> <span className="tag idle" style={{ marginLeft: 6 }}>{c.role_name}</span>
                          <div style={{ color: 'var(--ink-2)', fontSize: 11, marginTop: 2 }}>
                            {c.email && <span>✉ {c.email} </span>}
                            {c.phone && <span>· ☎ {c.phone} </span>}
                            {c.after_hours_notes && <span>· 🌙 {c.after_hours_notes}</span>}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 12 }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: 2 }}>Employee Post / Role:</label>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <select style={{ flex: 1, padding: 4, border: '1px solid var(--line)' }} value={s4Role} onChange={(e) => setS4Role(e.target.value)}>
                        {roles.map((r) => <option key={r.id} value={r.role_name}>{r.role_name}</option>)}
                      </select>
                      <button type="button" className="btn tiny" onClick={onOpenAddRole} title="Add Role">+</button>
                    </div>
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: 2 }}>Employee Name *:</label>
                    <input style={{ width: '100%', padding: 4, border: '1px solid var(--line)' }} placeholder="Jordan Contact" value={s4Name} onChange={(e) => setS4Name(e.target.value)} />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: 2 }}>Email:</label>
                    <input style={{ width: '100%', padding: 4, border: '1px solid var(--line)' }} placeholder="jordan@client.example" value={s4Email} onChange={(e) => setS4Email(e.target.value)} />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: 2 }}>Phone Number:</label>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <select 
                        style={{ padding: 4, border: '1px solid var(--line)', background: 'var(--surface-1)' }}
                        value={s4CountryCode}
                        onChange={(e) => setS4CountryCode(e.target.value)}
                      >
                        <option value="+1">+1 (US/CA)</option>
                        <option value="+44">+44 (UK)</option>
                        <option value="+91">+91 (IN)</option>
                        <option value="+61">+61 (AU)</option>
                      </select>
                      <input style={{ flex: 1, padding: 4, border: '1px solid var(--line)' }} placeholder="555-0199" value={s4Phone} onChange={(e) => setS4Phone(e.target.value)} />
                    </div>
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: 2 }}>Alternate Contact:</label>
                    <input style={{ width: '100%', padding: 4, border: '1px solid var(--line)' }} placeholder="Operations Desk" value={s4Alt} onChange={(e) => setS4Alt(e.target.value)} />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: 2 }}>After-Hours Availability:</label>
                    <input style={{ width: '100%', padding: 4, border: '1px solid var(--line)' }} placeholder="24/7 on-call escalation" value={s4Ah} onChange={(e) => setS4Ah(e.target.value)} />
                  </div>
                </div>
                <div style={{ marginTop: 10, textAlign: 'right' }}>
                  <button className="btn tiny primary" onClick={handleStep4Save}>
                    {step.extra?.contacts && step.extra.contacts.length > 0 ? '+ Add Employee Contact' : 'Save & Complete Step 4'}
                  </button>
                </div>
              </div>
            )}

            {step.actionType === 'claim_verify' && (
              <div className="step-custom-box">
                <label style={{ fontWeight: 600, fontSize: 12, display: 'block', marginBottom: 4 }}>Claim System Verification Information:</label>
                <textarea rows={2} style={{ width: '100%', padding: 6, border: '1px solid var(--line)', fontSize: 12.5 }} value={s5Text} onChange={(e) => setS5Text(e.target.value)} placeholder="e.g. Vendor hosted ClaimsCore Enterprise, SFTP outbound nightly 835 drops verified." />
                <div style={{ marginTop: 6, textAlign: 'right' }}>
                  <button className="btn tiny primary" onClick={handleStep5Save}>Submit &amp; Complete Step 5</button>
                </div>
              </div>
            )}

            {step.actionType === 'transfer_config' && (
              <div className="step-custom-box">
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 12 }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: 2 }}>Integration Method:</label>
                    <select style={{ width: '100%', padding: 4, border: '1px solid var(--line)' }} value={s6Method} onChange={(e) => setS6Method(e.target.value)}>
                      <option value="SFTP">SFTP</option>
                      <option value="HTTPS API">HTTPS API</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: 2 }}>Setup Status:</label>
                    <select style={{ width: '100%', padding: 4, border: '1px solid var(--line)' }} value={s6Status} onChange={(e) => setS6Status(e.target.value)}>
                      <option value="Configured">Configured</option>
                      <option value="Pending Keys">Pending Keys</option>
                      <option value="In Review">In Review</option>
                    </select>
                  </div>
                </div>
                <div style={{ marginTop: 8, display: 'flex', justifyContent: 'flex-end', alignItems: 'center' }}>
                  <button className="btn tiny primary" onClick={handleStep6Save}>Save &amp; Complete Step 6</button>
                </div>
              </div>
            )}

            {step.actionType === 'x12_835_validate' && (
              <div className="step-custom-box">
                <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>Sample 835 EDI Validation:</div>
                {latestUp ? (
                  <div style={{ fontSize: 12, marginBottom: 8 }}>📄 File: <b>{latestUp.original_filename}</b> ({latestUp.validation_status || 'PENDING'})</div>
                ) : (
                  <div style={{ fontSize: 12, color: 'var(--ink-3)', marginBottom: 8 }}>No 835 EDI file uploaded yet. Upload a valid .835, .x12, .edi, .txt, or .dat file.</div>
                )}
                {isFailed && <div style={{ color: 'var(--brick)', fontSize: 12, marginBottom: 8 }}>✕ Validation Failed. Please inspect X12 structure or re-upload a valid 835 file.</div>}
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <label className={`btn tiny ${step.done ? 'success' : 'primary'}`} style={{ cursor: 'pointer' }}>
                    ⬆ Upload 835 File
                    <input type="file" hidden accept=".835,.x12,.edi,.txt,.dat,.35,.ansi,.rem" onChange={handleStep7Upload} />
                  </label>
                  {step.inProgress && (
                    <button className="btn tiny success" onClick={handleValidate835} style={{ fontWeight: 600 }}>
                      ✓ Validate 835
                    </button>
                  )}
                </div>
              </div>
            )}

            {step.actionType === 'mapping_redirect' && (
              <div className="step-custom-box" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                <div><b>Mapping Application:</b> Launch rules engine to configure 835 mapping.</div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button className="btn tiny primary" onClick={() => launchRedirect(`/mapping?client=${encodeURIComponent(clientId)}`, 'step_8_mapping')}>
                    Start Mapping ↗
                  </button>
                </div>
              </div>
            )}

            {step.actionType === 'sftp_redirect' && (
              <div className="step-custom-box" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                <div><b>SFTP Sandbox Screen:</b> Setup test environment folders and SSH keys.</div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button className="btn tiny primary" onClick={() => launchRedirect(`/sftp?client=${encodeURIComponent(clientId)}`, 'step_9_sftp')}>
                    Open SFTP Screen ↗
                  </button>
                  <button className="btn tiny success" onClick={async () => {
                    try {
                      await postStepData(`/clients/${encodeURIComponent(clientId)}/onboarding/steps/step_9_sftp/complete`, {});
                      onRefresh();
                    } catch (err) { alert('Error: ' + err.message); }
                  }}>✓ Complete Step 9</button>
                </div>
              </div>
            )}

            {step.actionType === 'side_by_side_done' && (
              <div className="step-custom-box">
                <label style={{ fontWeight: 600, fontSize: 12, display: 'block', marginBottom: 4 }}>
                  Side-by-Side 835 Conversion Review Notes *:
                </label>
                <textarea
                  rows={2}
                  style={{ width: '100%', padding: 6, border: '1px solid var(--line)', fontSize: 12.5 }}
                  placeholder="e.g. Verified side-by-side 835 conversion claim totals CLP, BPR, and TRN against MIR format."
                  value={s10Notes}
                  onChange={(e) => setS10Notes(e.target.value)}
                />
                <div style={{ marginTop: 6, textAlign: 'right' }}>
                  <button className="btn tiny success" onClick={async () => {
                    if (!s10Notes.trim()) { alert('Step 10 Evidence Required: Please enter side-by-side 835 conversion review notes.'); return; }
                    try {
                      await postStepData(`/clients/${encodeURIComponent(clientId)}/onboarding/steps/step_10_test_review/complete`, { submission_text: s10Notes });
                      onRefresh();
                    } catch (err) { alert('Error: ' + err.message); }
                  }}>✓ Complete Step 10</button>
                </div>
              </div>
            )}

            {step.actionType === 'send_ftp_action' && (
              <div className="step-custom-box" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>Transmit verified test payload to client FTP server.</div>
                <button className="btn tiny primary" onClick={async () => {
                  try {
                    await postStepData(`/clients/${encodeURIComponent(clientId)}/steps/step_11_send_ftp/send`, {});
                    onRefresh();
                  } catch (err) { alert('Error: ' + err.message); }
                }}>🚀 Send File to FTP</button>
              </div>
            )}

            {step.actionType === 'schedule_action' && (
              <div className="step-custom-box">
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, fontSize: 12 }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: 2 }}>Go-Live Date *:</label>
                    <input type="date" style={{ width: '100%', padding: 4, border: '1px solid var(--line)' }} value={s13Date} onChange={(e) => setS13Date(e.target.value)} />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: 2 }}>Time *:</label>
                    <input type="time" style={{ width: '100%', padding: 4, border: '1px solid var(--line)' }} value={s13Time} onChange={(e) => setS13Time(e.target.value)} />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: 2 }}>Timezone:</label>
                    <select style={{ width: '100%', padding: 4, border: '1px solid var(--line)' }} value={s13Tz} onChange={(e) => setS13Tz(e.target.value)}>
                      <option value="ET">Eastern (ET)</option>
                      <option value="CT">Central (CT)</option>
                      <option value="PT">Pacific (PT)</option>
                    </select>
                  </div>
                </div>
                <div style={{ marginTop: 8 }}>
                  <input style={{ width: '100%', padding: 4, border: '1px solid var(--line)', fontSize: 12 }} placeholder="Meeting participants / calendar invite details" value={s13Notes} onChange={(e) => setS13Notes(e.target.value)} />
                </div>
                <div style={{ marginTop: 8, textAlign: 'right' }}>
                  <button className="btn tiny primary" onClick={handleStep13Save}>Save Schedule &amp; Complete Step 13</button>
                </div>
              </div>
            )}

            {(step.actionType === 'text_submission' || step.actionType === 'text_submission_final') && (
              <div className="step-custom-box">
                <label style={{ fontWeight: 600, fontSize: 12, display: 'block', marginBottom: 4 }}>
                  {step.actionType === 'text_submission_final' ? 'Production Delivery Sign-Off Notes:' : 'Go-Live Safeguards Verification:'}
                </label>
                <textarea rows={2} style={{ width: '100%', padding: 6, border: '1px solid var(--line)', fontSize: 12.5 }} placeholder={step.actionType === 'text_submission_final' ? 'First production file delivered and monitored without error.' : 'All cutover checks and security safeguards passed.'} value={stText} onChange={(e) => setStText(e.target.value)} />
                <div style={{ marginTop: 6, textAlign: 'right' }}>
                  <button className="btn tiny primary" onClick={handleTextSubmission}>
                    {step.actionType === 'text_submission_final' ? 'Conclude Onboarding' : `Submit & Complete Step ${step.id}`}
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <div className="side">
        {statusTag}
        <div className="rup">
          <button className="btn tiny" onClick={() => onOpenNotes(step.key, step.title)}>💬 Notes</button>
          {(step.done || step.inProgress) && (
            <button className="btn tiny danger" onClick={() => onOpenRedo(step.key, step.id)} title={`Reset Step ${step.id} to In Progress`}>
              🔄 Redo
            </button>
          )}
          {step.file && (
            <button className="btn tiny" onClick={() => downloadTemplateFile(clientId, step.key, step.title, step.ext)} title={`Download ${step.downloadName || 'Template'}`}>
              ⬇ Template
            </button>
          )}
          {(step.actionType === 'upload_template' || step.actionType === 'email_upload') && (
            <label className={`btn tiny ${step.done ? 'success' : 'primary'}`} style={{ cursor: 'pointer' }}>
              ⬆ Upload
              <input type="file" hidden onChange={handleStandardFileUpload} />
            </label>
          )}
        </div>
      </div>

      <FeedbackModal
        isOpen={feedback.isOpen}
        onClose={() => setFeedback({ ...feedback, isOpen: false })}
        kind={feedback.kind}
        title={feedback.title}
        content={feedback.content}
        checks={feedback.checks}
      />
    </div>
  );
}
