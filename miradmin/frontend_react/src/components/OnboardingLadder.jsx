import React, { useEffect } from 'react';
import StepRung from './StepRung';
import ClientSelectDropdown from './ClientSelectDropdown';
import { postStepData } from '../services/api';

function formatDate(dateVal) {
  if (!dateVal) return 'N/A';
  const d = new Date(dateVal);
  if (isNaN(d.getTime())) return dateVal;
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

export default function OnboardingLadder({ client, steps, roles, clients, onSelectClient, onRefresh, onOpenNotes, onOpenRedo, onOpenAddRole }) {
  useEffect(() => {
    const handleStorage = (e) => {
      if (e.key === 'cross_tab_refresh') {
        sessionStorage.removeItem('pending_return_step');
        onRefresh();
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, [onRefresh]);

  useEffect(() => {
    const handleFocus = async () => {
      const pendingKey = sessionStorage.getItem('pending_return_step');
      if (pendingKey && client) {
        if (pendingKey === 'step_8_mapping') {
          // Do not prompt for step 8! It is smart and completes itself via the Save button.
          return;
        }
        sessionStorage.removeItem('pending_return_step');
        const confirmed = window.confirm(`Welcome back! Did you finish work in the tool for ${pendingKey.replace(/_/g, ' ').toUpperCase()}? Click OK to mark this step complete.`);
        if (confirmed) {
          try {
            await postStepData(`/clients/${encodeURIComponent(client.id)}/onboarding/steps/${encodeURIComponent(pendingKey)}/complete`, {});
            await onRefresh();
          } catch (err) {
            alert('Enforcement: ' + err.message);
          }
        }
      }
    };
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, [client, onRefresh]);

  if (!client || !steps) {
    return (
      <section className="view on" id="v-onboard">
        <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--ink-2)' }}>
          <div style={{ fontSize: 24, marginBottom: 12 }}>⏳ Loading Onboarding Ladder...</div>
          <p>Fetching client compliance state and onboarding steps...</p>
        </div>
      </section>
    );
  }

  const totalSteps = steps.length || 15;
  const doneCount = steps.filter(s => s.done).length;
  const inProgressStep = steps.find(s => s.inProgress);
  const activeStepNum = inProgressStep ? `Step ${inProgressStep.id}` : (doneCount === totalSteps ? 'Complete' : '—');
  const activeStepTitle = inProgressStep ? inProgressStep.title : (doneCount === totalSteps ? `All ${totalSteps} Steps Complete` : '—');
  const stageName = client.stage === 'production' ? 'Production' : 'Onboarding';

  let currentPhase = null;

  return (
    <section className="view on" id="v-onboard">
      <div className="hdr-row">
        <div>
          <div className="eyebrow" id="ob-eyebrow">Selected Client</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', margin: '2px 0 4px' }}>
            <ClientSelectDropdown
              id="client-select-hdr"
              clients={clients}
              value={client.id}
              onChange={(value) => onSelectClient(value)}
            />
            <h1 id="ob-title" style={{ margin: 0 }}>Onboarding Workflow</h1>
          </div>
          <p className="sub">Sequential {totalSteps}-step compliance ladder. Completing the active step automatically unlocks the next step.</p>
        </div>
      </div>

      <div className="metrics">
        <div className="metric">
          <div className="v" id="m-complete">{doneCount} / {totalSteps}</div>
          <div className="l">Steps Complete</div>
          <div className="d" id="m-started">Started — {formatDate(client.created_at)}</div>
        </div>
        <div className="metric">
          <div className="v" id="m-waiting">{activeStepNum}</div>
          <div className="l">Active Action</div>
          <div className="d" id="m-waiting-d">{activeStepTitle}</div>
        </div>
        <div className="metric">
          <div className="v" id="m-pct">{client.progress_pct}%</div>
          <div className="l">Completion</div>
          <div className="d" id="m-stage">Stage: {stageName}</div>
        </div>
        <div className="metric">
          <div className="v" id="m-move">{formatDate(client.updated_at)}</div>
          <div className="l">Last Activity</div>
          <div className="d" id="m-move-d">Activity logged</div>
        </div>
      </div>

      <div className="ladder" id="ladder">
        {steps.map((step) => {
          let renderPhaseHeader = false;
          let phaseText = step.phase;
          if (phaseText !== currentPhase) {
            currentPhase = phaseText;
            renderPhaseHeader = true;
          }

          return (
            <React.Fragment key={`${client.id}-${step.id}`}>
              {renderPhaseHeader && (
                <div className="phase">
                  {phaseText}
                </div>
              )}
              <StepRung
                step={step}
                clientId={client.id}
                roles={roles}
                onRefresh={onRefresh}
                onOpenNotes={onOpenNotes}
                onOpenRedo={onOpenRedo}
                onOpenAddRole={onOpenAddRole}
              />
            </React.Fragment>
          );
        })}
      </div>

      <div className="note">
        <b>Sequential Workflow:</b> Steps unlock one by one. Use the <b>💬 Notes</b> icon on any step to record internal notes. Steps can be completed via document uploads, structured forms, or integration callbacks.
      </div>
    </section>
  );
}
