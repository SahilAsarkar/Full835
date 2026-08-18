import os
import sys
import unittest
from django.test import TestCase, Client
from django.core.management import call_command
from .models import (
    Client as ClientModel, OnboardingStepDefinition, ClientStepStatus,
    StepUpload, StepNote, EmployeeRole, ClientContact, ClaimSystemVerification,
    ClientTransferConfig, StepSchedule, StepTextSubmission, AuditLog
)
from .validation import get_step_download_filename, validate_x12_835_content


class TestDjangoAdminWorkflow(TestCase):
    def setUp(self):
        call_command('seed_data')
        self.client = Client(HTTP_AUTHORIZATION='Bearer onesmarter-admin')

    def test_unauthenticated_access_blocked(self):
        anon_client = Client()
        r = anon_client.get('/api/clients/')
        self.assertIn(r.status_code, (401, 403))

    # 1. Creating a client
    def test_01_create_client(self):
        r = self.client.post('/api/clients/', data={'name': 'Acme Health Group'}, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        data = r.json()
        self.assertEqual(data['client']['name'], 'Acme Health Group')

    def test_duplicate_client_prevention(self):
        r1 = self.client.post('/api/clients/', data={'name': 'Unique Client Test', 'code': 'UNIQ1'}, content_type='application/json')
        self.assertEqual(r1.status_code, 201)

        # Attempt to create duplicate name (case-insensitive)
        r2 = self.client.post('/api/clients/', data={'name': 'unique client test'}, content_type='application/json')
        self.assertEqual(r2.status_code, 400)
        self.assertIn('Duplicate client', r2.json()['error'])

        # Attempt to create duplicate code (case-insensitive)
        r3 = self.client.post('/api/clients/', data={'name': 'Different Name', 'code': 'uniq1'}, content_type='application/json')
        self.assertEqual(r3.status_code, 400)
        self.assertIn('Duplicate client identifier', r3.json()['error'])

    # 2. Automatically creating that client's onboarding workflow
    def test_02_client_workflow_creation(self):
        r = self.client.post('/api/clients/', data={'name': 'Beta Health'}, content_type='application/json')
        cid = r.json()['client']['id']
        r_state = self.client.get(f'/api/clients/{cid}/state/')
        steps = r_state.json()['state']['steps']
        self.assertEqual(len(steps), 15)

    # 3. Correct initial active step
    def test_03_initial_active_step(self):
        r = self.client.post('/api/clients/', data={'name': 'Gamma Health'}, content_type='application/json')
        cid = r.json()['client']['id']
        r_state = self.client.get(f'/api/clients/{cid}/state/')
        steps = r_state.json()['state']['steps']
        self.assertEqual(steps[0]['status'], 'IN_PROGRESS')
        for s in steps[1:]:
            self.assertEqual(s['status'], 'WAITING')

    # 4. Completing one step activates the next
    def test_04_sequential_step_progression(self):
        r = self.client.post('/api/clients/', data={'name': 'Delta Health'}, content_type='application/json')
        cid = r.json()['client']['id']
        
        valid_nda = self._create_nda_pdf(self._get_base_tmpl_lines())
        r_up = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=valid_nda, content_type='application/octet-stream', HTTP_X_FILENAME='My_Signed_NDA.pdf')
        self.assertEqual(r_up.status_code, 200)

        steps = self.client.get(f'/api/clients/{cid}/state/').json()['state']['steps']
        self.assertEqual(steps[0]['status'], 'DONE')
        self.assertEqual(steps[1]['status'], 'IN_PROGRESS')
        self.assertEqual(steps[2]['status'], 'WAITING')

    # 5 & 25. Step data is isolated between clients
    def test_05_client_data_isolation(self):
        r_a = self.client.post('/api/clients/', data={'name': 'Client Alpha'}, content_type='application/json')
        r_b = self.client.post('/api/clients/', data={'name': 'Client Beta'}, content_type='application/json')
        cid_a = r_a.json()['client']['id']
        cid_b = r_b.json()['client']['id']

        self.client.post(f'/api/clients/{cid_a}/steps/step_1_nda/notes', data={'note_text': 'Alpha secret note'}, content_type='application/json')

        notes_a = self.client.get(f'/api/clients/{cid_a}/steps/step_1_nda/notes').json()['notes']
        notes_b = self.client.get(f'/api/clients/{cid_b}/steps/step_1_nda/notes').json()['notes']
        self.assertEqual(len(notes_a), 1)
        self.assertEqual(len(notes_b), 0)

    # 6. Saving/retrieving Notes
    def test_06_notes_persistence(self):
        cid = 'northwood'
        r = self.client.post(f'/api/clients/{cid}/steps/step_2_baa/notes', data={'note_text': 'Reviewed BAA with legal counsel'}, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        notes = self.client.get(f'/api/clients/{cid}/steps/step_2_baa/notes').json()['notes']
        self.assertTrue(any('Reviewed BAA' in n['note_text'] for n in notes))

    # 7 & 8. Step 4 employee role/contact creation & adding new employee roles
    def test_07_08_employee_roles_and_contacts(self):
        r_role = self.client.post('/api/employee-roles', data={'role_name': 'Emergency Escalation Lead'}, content_type='application/json')
        self.assertEqual(r_role.status_code, 200)

    def test_08_employee_contacts(self):
        cid = 'northwood'
        self._advance_client_to_step(cid, 4)
        r_contact = self.client.post(f'/api/clients/{cid}/steps/step_4_contacts/save', data={
            'employee_name': 'Jordan Casey',
            'role_name': 'Emergency Escalation Lead',
            'email': 'jordan@northwood.example',
            'phone': '+1-555-0199',
            'after_hours_notes': 'Available 24/7 on call'
        }, content_type='application/json')
        self.assertEqual(r_contact.status_code, 200)

    # 9. Step 5 claim verification
    def test_09_claim_verification(self):
        cid = 'northwood'
        self._advance_client_to_step(cid, 5)
        r = self.client.post(f'/api/clients/{cid}/steps/step_5_claim_sys/save', data={
            'verification_text': 'Vendor hosted ClaimsCore v4.2 with SFTP drop verified'
        }, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        step5 = ClientStepStatus.objects.get(client_id=cid, step__step_number=5)
        self.assertEqual(step5.status, 'DONE')

    # 10. Step 6 transfer method persistence
    def test_10_transfer_method(self):
        cid = 'northwood'
        self._advance_client_to_step(cid, 6)
        r = self.client.post(f'/api/clients/{cid}/steps/step_6_transfer_method/save', data={
            'method': 'SFTP',
            'watched_folder_sftp': True,
            'keys_exchanged': True,
            'setup_status': 'Configured',
            'notes': '/outbound/835 watched path'
        }, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        step6 = ClientStepStatus.objects.get(client_id='northwood', step__step_number=6)
        self.assertEqual(step6.status, 'DONE')

    # 11 & 12. 835 upload, extension check & two-stage structural validation
    def test_11_12_valid_and_invalid_835(self):
        r_c = self.client.post('/api/clients/', data={'name': 'EDI Test Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        self._advance_client_to_step(cid, 7)

        # Bad extension .pdf on Step 7
        r_bad = self.client.post(f'/api/clients/{cid}/steps/step_7_835_val/upload', data=b'%PDF-1.4 Fake PDF', content_type='application/octet-stream', HTTP_X_FILENAME='fake835.pdf')
        self.assertEqual(r_bad.status_code, 422)

        # Stage valid EDI file (Stage 1)
        valid_edi = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *260814*1000*^*00501*000000001*0*P*:~\n"
            "GS*HP*SENDER*RECEIVER*20260814*1000*1*X*005010X221A1~\n"
            "ST*835*0001~\n"
            "BPR*I*1000.00*C*ACH*CTX*01*999999999*DA*123456789*1234567890**01*999999998*DA*000111222*20260814~\n"
            "TRN*1*TRACE12345*1999999999~\n"
            "N1*PR*PAYER NAME*XV*PAYERID~\n"
            "N1*PE*PAYEE NAME*XX*1234567890~\n"
            "CLP*CLAIM001*1*1000.00*800.00*200.00*12*PAYERCLM001*11*1~\n"
            "SE*7*0001~\n"
            "GE*1*1~\n"
            "IEA*1*000000001~"
        ).encode('utf-8')

        r_stage = self.client.post(f'/api/clients/{cid}/steps/step_7_835_val/upload', data=valid_edi, content_type='application/octet-stream', HTTP_X_FILENAME='sample.edi')
        self.assertEqual(r_stage.status_code, 200)
        self.assertTrue(r_stage.json().get('staged'))

        # Run Stage 2 validation
        r_val = self.client.post(f'/api/clients/{cid}/steps/step_7_835_val/validate-uploaded')
        self.assertEqual(r_val.status_code, 200)
        self.assertTrue(r_val.json().get('validated'))

        steps = self.client.get(f'/api/clients/{cid}/state/').json()['state']['steps']
        self.assertTrue(steps[6]['done'])
        self.assertTrue(steps[7]['inProgress'])

    def _advance_client_to_step(self, cid, target_step_number):
        from datetime import datetime, timezone
        client = ClientModel.objects.get(id=cid)
        for num in range(1, target_step_number):
            step_def = OnboardingStepDefinition.objects.get(step_number=num)
            st, _ = ClientStepStatus.objects.get_or_create(client=client, step=step_def)
            st.status = 'DONE'
            st.completed_at = datetime.now(timezone.utc)
            st.save()
        tgt_def = OnboardingStepDefinition.objects.get(step_number=target_step_number)
        st_tgt, _ = ClientStepStatus.objects.get_or_create(client=client, step=tgt_def)
        st_tgt.status = 'IN_PROGRESS'
        st_tgt.save()

    def test_compliance_ladder_out_of_order_rejected(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Ladder Strict Test'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        
        # Step 1 is IN_PROGRESS. Direct call to complete Step 15 must fail with 409 Conflict
        r_invalid = self.client.post(f'/api/clients/{cid}/steps/step_15_delivery/submit-text', data={'submission_text': 'Bypassing ladder'}, content_type='application/json')
        self.assertEqual(r_invalid.status_code, 409)
        self.assertIn('Compliance Ladder Enforcement', r_invalid.json()['error'])

    # 13, 14, 15, 16. Step callbacks and completions
    def test_13_16_callbacks(self):
        cid = 'northwood'
        self._advance_client_to_step(cid, 8)
        # Step 8
        r8 = self.client.post(f'/api/clients/{cid}/onboarding/steps/step_8_mapping/complete', data={}, content_type='application/json')
        self.assertEqual(r8.status_code, 200)
        # Step 9
        r9 = self.client.post(f'/api/clients/{cid}/onboarding/steps/step_9_sftp/complete', data={}, content_type='application/json')
        self.assertEqual(r9.status_code, 200)
        # Step 10
        r10 = self.client.post(f'/api/clients/{cid}/onboarding/steps/step_10_test_review/complete', data={'submission_text': 'Side-by-side review verified.'}, content_type='application/json')
        self.assertEqual(r10.status_code, 200)
        # Step 11
        r11 = self.client.post(f'/api/clients/{cid}/steps/step_11_send_ftp/send', data={}, content_type='application/json')
        self.assertEqual(r11.status_code, 200)

    # 17. Step 12 Email attachment in Phase 3
    def test_17_step_12_email_upload(self):
        cid = 'northwood'
        self._advance_client_to_step(cid, 12)
        signoff_lines = [
            "ONESMARTER - CLIENT EMAIL SIGNOFF ATTACHMENT",
            "Step 12 Evidence: Upload email conversation attachment",
            "Client: Northwood Administrators",
            "Signoff Date: 2026-08-14",
            "Approver: Vikram J. / Implementation Lead",
            "Confirmation: Email signoff received for test data and mapping signoff."
        ]
        dummy_attachment = self._create_nda_pdf(signoff_lines)
        r12 = self.client.post(f'/api/clients/{cid}/steps/step_12_email_attach/upload', data=dummy_attachment, content_type='application/octet-stream', HTTP_X_FILENAME='client_email_signoff.pdf')
        self.assertEqual(r12.status_code, 200)

    # 18. Step 13 schedule save
    def test_18_step_13_schedule(self):
        cid = 'northwood'
        self._advance_client_to_step(cid, 13)
        r13 = self.client.post(f'/api/clients/{cid}/steps/step_13_schedule/save', data={
            'scheduled_date': '2026-09-01',
            'scheduled_time': '14:00',
            'timezone': 'ET',
            'notes': 'Go live kickoff call'
        }, content_type='application/json')
        self.assertEqual(r13.status_code, 200)

    # 19 & 20. Steps 14 & 15 text submission and onboarding conclusion
    def test_19_20_steps_14_15_submissions(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Omega Health'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        self._advance_client_to_step(cid, 14)

        r14 = self.client.post(f'/api/clients/{cid}/steps/step_14_go_live/submit-text', data={'submission_text': 'Go live checklist passed'}, content_type='application/json')
        self.assertEqual(r14.status_code, 200)

        r15 = self.client.post(f'/api/clients/{cid}/steps/step_15_delivery/submit-text', data={'submission_text': 'First production file sent and verified'}, content_type='application/json')
        self.assertEqual(r15.status_code, 200)

        client_obj = ClientModel.objects.get(id=cid)
        self.assertEqual(client_obj.stage, 'production')

    # 21. Correct step renumbering (15 steps across 4 phases with Step 12 in Phase 3)
    def test_21_step_renumbering(self):
        steps = OnboardingStepDefinition.objects.all().order_by('step_number')
        self.assertEqual(len(steps), 15)
        step12 = steps.filter(step_number=12).first()
        self.assertEqual(step12.phase.id, 3)

    # 22 & 23. File naming convention
    def test_22_23_file_naming_and_extensions(self):
        fn1 = get_step_download_filename("Mutual NDA signed", "pdf")
        self.assertEqual(fn1, "OneSmarter_MutualNdaSigned.pdf")

        fn2 = get_step_download_filename("Sample 835 received", "edi")
        self.assertEqual(fn2, "OneSmarter_Sample835Received.edi")

    # 25. Redo / Re-open step functionality with database and file cleanup
    def test_25_redo_step(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Redo Test'}, content_type='application/json')
        cid = r_c.json()['client']['id']

        nda_bytes = self._create_nda_pdf(self._get_base_tmpl_lines())
        self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=nda_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='NDA_Signed.pdf')

        steps = self.client.get(f'/api/clients/{cid}/state/').json()['state']['steps']
        self.assertTrue(steps[0]['done'])
        self.assertTrue(steps[1]['inProgress'])

        # Redo step 1
        r_redo = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/redo')
        self.assertEqual(r_redo.status_code, 200)

        steps_after = self.client.get(f'/api/clients/{cid}/state/').json()['state']['steps']
        self.assertFalse(steps_after[0]['done'])
        self.assertTrue(steps_after[0]['inProgress'])
        self.assertEqual(steps_after[1]['status'], 'WAITING')

    # Helper for creating test PDF bytes with given stream text lines
    def _create_nda_pdf(self, lines: List[str]) -> bytes:
        stream_lines = ["BT", "/F1 12 Tf", "72 730 Td"]
        for idx, line in enumerate(lines):
            if idx == 0:
                stream_lines.append(f"({line}) Tj")
                stream_lines.append("/F2 10 Tf")
            else:
                offset = -28 if idx == 1 else -16
                stream_lines.append(f"0 {offset} Td")
                stream_lines.append(f"({line}) Tj")
        stream_lines.append("ET")
        stream_content = "\n".join(stream_lines)
        
        pdf_str = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
6 0 obj
<< /Length {len(stream_content)} >>
stream
{stream_content}
endstream
endobj
xref
0 7
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000251 00000 n 
0000000326 00000 n 
0000000396 00000 n 
trailer
<< /Size 7 /Root 1 0 R >>
startxref
1213
%%EOF
"""
        return pdf_str.encode('utf-8')

    def _get_base_tmpl_lines(self) -> List[str]:
        return [
            "Mutual Non-Disclosure Agreement",
            "Client (Disclosing/Receiving Party): {{CLIENT_LEGAL_NAME}}",
            "Provider (Disclosing/Receiving Party): {{PROVIDER_LEGAL_NAME}}",
            "Effective Date: {{NDA_EFFECTIVE_DATE}}",
            "",
            "The parties agree to protect each other's confidential information",
            "exchanged in connection with the OneSmarter MIR Relay onboarding.",
            "",
            "Client Signatory: {{CLIENT_SIGNATORY_NAME}}",
            "Client Signature Date: {{CLIENT_SIGNATURE_DATE}}",
            "Provider Signatory: {{PROVIDER_SIGNATORY_NAME}}",
            "Provider Signature Date: {{PROVIDER_SIGNATURE_DATE}}",
            "",
            "Status: Complete"
        ]

    def _get_cutover_tmpl_lines(self) -> List[str]:
        return [
            "Cutover Authorization",
            "Client (Authorizing Party): {{CLIENT_LEGAL_NAME}}",
            "Provider (Authorizing Party): {{PROVIDER_LEGAL_NAME}}",
            "Project / System: {{PROJECT_SYSTEM_NAME}}",
            "Scheduled Cutover Date: {{CUTOVER_DATE}}",
            "The parties authorize the cutover of {{PROJECT_SYSTEM_NAME}} from the",
            "staging/testing environment to the production environment, confirming that",
            "all pre-cutover validation checks for the OneSmarter MIR Relay onboarding",
            "have been completed and passed.",
            "Client Authorized Signatory: {{CLIENT_SIGNATORY_NAME}}",
            "Client Authorization Date: {{CLIENT_AUTHORIZATION_DATE}}",
            "Provider Authorized Signatory: {{PROVIDER_SIGNATORY_NAME}}",
            "Provider Authorization Date: {{PROVIDER_AUTHORIZATION_DATE}}",
            "Status: {{STATUS}}"
        ]

    def _get_baseline_tmpl_lines(self) -> List[str]:
        return [
            "Production Baseline Record",
            "Client: {{CLIENT_LEGAL_NAME}}",
            "Provider: {{PROVIDER_LEGAL_NAME}}",
            "System / Project: {{PROJECT_SYSTEM_NAME}}",
            "Baseline Version: {{BASELINE_VERSION}}",
            "Baseline Established Date: {{BASELINE_DATE}}",
            "This document records the approved production baseline for",
            "{{PROJECT_SYSTEM_NAME}} under the OneSmarter MIR Relay onboarding, against",
            "which all future changes will be tracked and measured.",
            "Baseline Established By: {{ESTABLISHED_BY_NAME}}",
            "Establishment Date: {{ESTABLISHED_DATE}}",
            "Baseline Approved By: {{APPROVED_BY_NAME}}",
            "Approval Date: {{APPROVAL_DATE}}",
            "Status: {{STATUS}}"
        ]

    # Test 1 — Original untouched template -> PASS
    def test_scenario_01_original_untouched_template(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 1 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        pdf_bytes = self._create_nda_pdf(self._get_base_tmpl_lines())
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='OneSmarter_MutualNDA_Template.pdf')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])

    # Test 2 — Only placeholder values changed -> PASS
    def test_scenario_02_only_placeholder_values_changed(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 2 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        lines = self._get_base_tmpl_lines()
        lines[1] = "Client (Disclosing/Receiving Party): Northwood Administrators"
        lines[3] = "Effective Date: 2026-08-15"
        pdf_bytes = self._create_nda_pdf(lines)
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='NDA_Northwood_Executed.pdf')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])

    # Test 3 — Static text changed -> FAIL
    def test_scenario_03_static_text_changed(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 3 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        lines = self._get_base_tmpl_lines()
        lines[1] = "Customer Name: Northwood Administrators"
        pdf_bytes = self._create_nda_pdf(lines)
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='NDA_Modified.pdf')
        self.assertEqual(r.status_code, 422)

    # Test 4 — Placeholder removed without value -> FAIL
    def test_scenario_04_placeholder_removed(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 4 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        lines = self._get_base_tmpl_lines()
        lines[1] = "Client (Disclosing/Receiving Party): "
        pdf_bytes = self._create_nda_pdf(lines)
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='NDA_Blank.pdf')
        self.assertEqual(r.status_code, 422)

    # Test 5 — Additional text added outside placeholder -> FAIL
    def test_scenario_05_additional_text_added_outside_placeholder(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 5 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        lines = self._get_base_tmpl_lines()
        lines.insert(5, "Confidential Addendum - Extra Clause")
        pdf_bytes = self._create_nda_pdf(lines)
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='NDA_ExtraText.pdf')
        self.assertEqual(r.status_code, 422)

    # Test 6 — Row / section added -> FAIL
    def test_scenario_06_row_or_section_added(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 6 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        lines = self._get_base_tmpl_lines()
        lines.append("Extra Row Section")
        pdf_bytes = self._create_nda_pdf(lines)
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='NDA_RowAdded.pdf')
        self.assertEqual(r.status_code, 422)

    # Test 7 — Row / section removed -> FAIL
    def test_scenario_07_row_or_section_removed(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 7 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        lines = self._get_base_tmpl_lines()
        lines.pop()
        pdf_bytes = self._create_nda_pdf(lines)
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='NDA_RowRemoved.pdf')
        self.assertEqual(r.status_code, 422)

    # Test 8 — Column / label added -> FAIL
    def test_scenario_08_column_or_label_added(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 8 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        lines = self._get_base_tmpl_lines()
        lines[8] = "Client Signatory & Contact Title: {{CLIENT_SIGNATORY_NAME}}"
        pdf_bytes = self._create_nda_pdf(lines)
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='NDA_LabelAdded.pdf')
        self.assertEqual(r.status_code, 422)

    # Test 9 — Column / label removed -> FAIL
    def test_scenario_09_column_or_label_removed(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 9 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        lines = self._get_base_tmpl_lines()
        lines[3] = "{{NDA_EFFECTIVE_DATE}}"
        pdf_bytes = self._create_nda_pdf(lines)
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='NDA_LabelRemoved.pdf')
        self.assertEqual(r.status_code, 422)

    # Test 10 — Template key / sheet modified -> FAIL
    def test_scenario_10_template_key_or_sheet_modified(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 10 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        lines = self._get_base_tmpl_lines()
        lines[0] = "Master Services Agreement"
        pdf_bytes = self._create_nda_pdf(lines)
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='NDA_HeadingChanged.pdf')
        self.assertEqual(r.status_code, 422)

    # Test 11 — Unexpected block added -> FAIL
    def test_scenario_11_unexpected_block_added(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 11 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        lines = self._get_base_tmpl_lines()
        lines.extend(["Unexpected Block Title", "Unexpected Block Body Content"])
        pdf_bytes = self._create_nda_pdf(lines)
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='NDA_BlockAdded.pdf')
        self.assertEqual(r.status_code, 422)

    # Test 12 — Section removed -> FAIL
    def test_scenario_12_section_removed(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 12 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        lines = self._get_base_tmpl_lines()
        del lines[5:7]
        pdf_bytes = self._create_nda_pdf(lines)
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='NDA_SectionRemoved.pdf')
        self.assertEqual(r.status_code, 422)

    # Test 13 — Static value changed -> FAIL
    def test_scenario_13_static_value_changed(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 13 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        lines = self._get_base_tmpl_lines()
        lines[-1] = "Status: Pending Review"
        pdf_bytes = self._create_nda_pdf(lines)
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='NDA_StaticValChanged.pdf')
        self.assertEqual(r.status_code, 422)

    # Test 14 — Formula / fixed rule changed -> FAIL
    def test_scenario_14_formula_or_fixed_rule_changed(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 14 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        lines = self._get_base_tmpl_lines()
        lines[5] = "The parties agree to share all data without restriction."
        pdf_bytes = self._create_nda_pdf(lines)
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='NDA_FixedRuleChanged.pdf')
        self.assertEqual(r.status_code, 422)

    # Test 15 — Valid placeholder value containing spaces/special characters -> PASS
    def test_scenario_15_valid_placeholder_with_spaces_special_chars(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 15 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        lines = self._get_base_tmpl_lines()
        lines[1] = "Client (Disclosing/Receiving Party): Northwood & Sons, Inc. (Suite #400)"
        pdf_bytes = self._create_nda_pdf(lines)
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='NDA_SpecialChars.pdf')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])

    # Test 16 — Wrong file format -> FAIL
    def test_scenario_16_wrong_file_format(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 16 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        exe_bytes = b"MZ_EXECUTABLE_BINARY_JUNK_DATA"
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=exe_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='malicious_script.exe')
        self.assertEqual(r.status_code, 422)

    # Test 17 — Corrupted file -> FAIL
    def test_scenario_17_corrupted_file(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 17 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        corrupt_bytes = b"CORRUPTED_GARBAGE_BYTES_TRASH"
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=corrupt_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='corrupt_nda.pdf')
        self.assertEqual(r.status_code, 422)

    # Test 18 — Different filename but valid content -> PASS
    def test_scenario_18_different_filename_valid_content(self):
        r_c = self.client.post('/api/clients/', data={'name': 'Test 18 Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']
        pdf_bytes = self._create_nda_pdf(self._get_base_tmpl_lines())
        r = self.client.post(f'/api/clients/{cid}/steps/step_1_nda/upload', data=pdf_bytes, content_type='application/octet-stream', HTTP_X_FILENAME='my_custom_client_nda_signed_2026.pdf')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])

    # --- 19. Documents Section Client Isolation & Download Test ---
    def test_documents_client_isolation_and_download(self):
        # Create Client A
        r_a = self.client.post('/api/clients/', data={'name': 'Alpha Doc Client'}, content_type='application/json')
        cid_a = r_a.json()['client']['id']

        # Create Client B
        r_b = self.client.post('/api/clients/', data={'name': 'Beta Doc Client'}, content_type='application/json')
        cid_b = r_b.json()['client']['id']

        # Upload doc for Client A
        pdf_bytes = self._create_nda_pdf(self._get_base_tmpl_lines())
        r_up = self.client.post(
            f'/api/clients/{cid_a}/documents/upload',
            data=pdf_bytes,
            content_type='application/octet-stream',
            HTTP_X_FILENAME='alpha_custom_agreement.pdf',
            HTTP_X_DOC_NAME='Alpha Custom Agreement',
            HTTP_X_DOC_TYPE='Legal'
        )
        self.assertEqual(r_up.status_code, 201)
        doc_id = r_up.json()['document']['id']

        # Fetch docs for Client A -> Should have 1 doc
        r_docs_a = self.client.get(f'/api/clients/{cid_a}/documents/')
        self.assertEqual(r_docs_a.status_code, 200)
        docs_a = r_docs_a.json()['documents']
        self.assertEqual(len(docs_a), 1)
        self.assertEqual(docs_a[0]['document_name'], 'Alpha Custom Agreement')

        # Fetch docs for Client B -> Should have 0 docs
        r_docs_b = self.client.get(f'/api/clients/{cid_b}/documents/')
        self.assertEqual(r_docs_b.status_code, 200)
        docs_b = r_docs_b.json()['documents']
        self.assertEqual(len(docs_b), 0)

        # Download doc by ID -> Should return proper headers
        r_down = self.client.get(f'/api/documents/{doc_id}/download')
        self.assertEqual(r_down.status_code, 200)
        self.assertEqual(r_down['Content-Type'], 'application/pdf')
        self.assertIn('attachment', r_down['Content-Disposition'])

        # Verify audit log recorded DOCUMENT_DOWNLOAD
        r_audit = self.client.get(f'/api/audit-logs?client_id={cid_a}&module=DOCUMENTS')
        self.assertEqual(r_audit.status_code, 200)
        logs = r_audit.json()['logs']
        actions = [l['action'] for l in logs]
        self.assertIn('DOCUMENT_UPLOAD', actions)
        self.assertIn('DOCUMENT_DOWNLOAD', actions)

    # --- 20. Test Environment Client Isolation & Execution Test ---
    def test_test_environment_isolation_and_execution(self):
        r_a = self.client.post('/api/clients/', data={'name': 'Alpha TestEnv Client'}, content_type='application/json')
        cid_a = r_a.json()['client']['id']

        # Get initial test env
        r_env = self.client.get(f'/api/clients/{cid_a}/test-environment/')
        self.assertEqual(r_env.status_code, 200)
        self.assertEqual(r_env.json()['test_environment']['test_status'], 'In Progress')

        # Update test env settings
        r_up = self.client.post(f'/api/clients/{cid_a}/test-environment/', data={
            'sftp_host': 'custom-sftp.test.internal',
            'watched_folder': '/custom/inbound',
            'notes': 'Custom staging notes'
        }, content_type='application/json')
        self.assertEqual(r_up.status_code, 200)
        self.assertEqual(r_up.json()['test_environment']['sftp_host'], 'custom-sftp.test.internal')

        # Run Sandbox test
        r_run = self.client.post(f'/api/clients/{cid_a}/test-environment/run-test')
        self.assertEqual(r_run.status_code, 200)
        self.assertEqual(r_run.json()['test_environment']['test_status'], 'Verified')

    # --- 21. Go Live 6-Step Sequential Workflow Test ---
    def test_golive_6_step_workflow_progression(self):
        r_c = self.client.post('/api/clients/', data={'name': 'GoLive Test Client'}, content_type='application/json')
        cid = r_c.json()['client']['id']

        # 1. Check initial Go Live state
        r_state = self.client.get(f'/api/clients/{cid}/golive/state/')
        self.assertEqual(r_state.status_code, 200)
        steps = r_state.json()['state']['steps']
        self.assertEqual(len(steps), 6)
        self.assertTrue(steps[0]['inProgress'])
        self.assertEqual(steps[1]['status'], 'WAITING')

        # 2. Step 1 Upload & Download
        r_down1 = self.client.get(f'/api/clients/{cid}/golive/steps/1/download')
        self.assertEqual(r_down1.status_code, 200)

        pdf_bytes_gl1 = self._create_nda_pdf(self._get_cutover_tmpl_lines())
        r_up1 = self.client.post(f'/api/clients/{cid}/golive/steps/1/upload', data=pdf_bytes_gl1, content_type='application/octet-stream', HTTP_X_FILENAME='Cutover_Auth.pdf')
        self.assertEqual(r_up1.status_code, 200)
        steps = r_up1.json()['state']['steps']
        self.assertTrue(steps[0]['done'])
        self.assertTrue(steps[1]['inProgress'])

        # 3. Step 2 Upload & Download
        r_down2 = self.client.get(f'/api/clients/{cid}/golive/steps/2/download')
        self.assertEqual(r_down2.status_code, 200)

        pdf_bytes_gl2 = self._create_nda_pdf(self._get_baseline_tmpl_lines())
        r_up2 = self.client.post(f'/api/clients/{cid}/golive/steps/2/upload', data=pdf_bytes_gl2, content_type='application/octet-stream', HTTP_X_FILENAME='Baseline_Compliance.pdf')
        self.assertEqual(r_up2.status_code, 200)
        steps = r_up2.json()['state']['steps']
        self.assertTrue(steps[1]['done'])
        self.assertTrue(steps[2]['inProgress'])

        # 4. Step 3 SFTP button actions & completion
        r_in = self.client.post(f'/api/clients/{cid}/golive/steps/3/sftp', data={'action': 'in_bounded'}, content_type='application/json')
        self.assertEqual(r_in.status_code, 200)

        r_sftp = self.client.post(f'/api/clients/{cid}/golive/steps/3/sftp', data={
            'watched_folder_sftp': True,
            'keys_exchanged': True,
            'no_change_to_client_system': True
        }, content_type='application/json')
        self.assertEqual(r_sftp.status_code, 200)
        steps = r_sftp.json()['state']['steps']
        self.assertTrue(steps[2]['done'])
        self.assertTrue(steps[3]['inProgress'])

        # 5. Step 4 Production Schedule (Validation: required date)
        r_sch_fail = self.client.post(f'/api/clients/{cid}/golive/steps/4/schedule', data={'production_date': '', 'production_time': '10:00'}, content_type='application/json')
        self.assertEqual(r_sch_fail.status_code, 400)
        self.assertIn('Production date is required', r_sch_fail.json()['error'])

        r_sch_ok = self.client.post(f'/api/clients/{cid}/golive/steps/4/schedule', data={'production_date': '2026-08-20', 'production_time': '10:30 AM'}, content_type='application/json')
        self.assertEqual(r_sch_ok.status_code, 200)
        steps = r_sch_ok.json()['state']['steps']
        self.assertTrue(steps[3]['done'])
        self.assertTrue(steps[4]['inProgress'])

        # 6. Step 5 Any Special Comment (Optional: empty allowed)
        r_cmt_ok = self.client.post(f'/api/clients/{cid}/golive/steps/5/comment', data={'comment_text': ''}, content_type='application/json')
        self.assertEqual(r_cmt_ok.status_code, 200)
        steps = r_cmt_ok.json()['state']['steps']
        self.assertTrue(steps[4]['done'])
        self.assertTrue(steps[5]['inProgress'])

        # 7. Step 6 Production Successful Finalization
        r_fin = self.client.post(f'/api/clients/{cid}/golive/steps/6/complete')
        self.assertEqual(r_fin.status_code, 200)
        steps = r_fin.json()['state']['steps']
        self.assertTrue(steps[5]['done'])

        # Verify client is promoted to production stage
        c_fresh = ClientModel.objects.get(id=cid)
        self.assertEqual(c_fresh.stage, 'production')
        self.assertEqual(c_fresh.state, 'Healthy')

        # 8. Test Go Live Redo Step
        r_redo = self.client.post(f'/api/clients/{cid}/golive/steps/4/redo')
        self.assertEqual(r_redo.status_code, 200)
        steps = r_redo.json()['state']['steps']
        self.assertTrue(steps[3]['inProgress'])
        self.assertEqual(steps[4]['status'], 'WAITING')
        self.assertEqual(steps[5]['status'], 'WAITING')

    # --- 22. Dynamic Last Login & Access Info Test ---
    def test_dynamic_last_login_and_access_info(self):
        # 1. Perform first login
        r1 = self.client.post('/api/auth/login/', data={'password': 'onesmarter-admin'}, content_type='application/json')
        self.assertEqual(r1.status_code, 200)

        # 2. Perform second login
        r2 = self.client.post('/api/auth/login/', data={'password': 'onesmarter-admin'}, content_type='application/json')
        self.assertEqual(r2.status_code, 200)
        data2 = r2.json()
        self.assertIn('last_login', data2)
        self.assertTrue(len(data2['last_login']) > 0)

        # 3. Check access info endpoint
        r_access = self.client.get('/api/access/info/')
        self.assertEqual(r_access.status_code, 200)
        self.assertIn('last_login', r_access.json())
        self.assertIn('staff', r_access.json())


