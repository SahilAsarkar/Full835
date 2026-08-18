from django.core.management.base import BaseCommand
from datetime import datetime, timezone, timedelta
from django.contrib.auth.models import User
from api.models import (
    OnboardingPhase, OnboardingStepDefinition, EmployeeRole, Client, ClientStepStatus,
    GoLiveStepDefinition, ClientGoLiveStatus, ClientTestEnvironment, ClientDocument,
    ClientGoLiveSFTP, ClientGoLiveSchedule, ClientGoLiveComment, LoginHistory
)

class Command(BaseCommand):
    help = 'Seeds initial phases, steps, roles, go-live steps, test environments, and clients in Django database.'

    def handle(self, *args, **options):
        self.stdout.write('Seeding onboarding phases...')
        phases_data = [
            (1, 'Phase one · Paper before data'),
            (2, 'Phase two · Understand their system'),
            (3, 'Phase three · Prove it on test'),
            (4, 'Phase four · Live'),
        ]
        phases_dict = {}
        for pnum, pname in phases_data:
            p, _ = OnboardingPhase.objects.get_or_create(phase_number=pnum, defaults={'phase_name': pname})
            p.phase_name = pname
            p.save()
            phases_dict[pnum] = p

        self.stdout.write('Seeding onboarding step definitions...')
        steps_data = [
            (1, 'step_1_nda', 'Mutual NDA signed', 'Upload signed NDA template to establish confidentiality agreement.', 1, 'upload_template', 'OneSmarter_MutualNDA_Template.pdf', 'pdf'),
            (2, 'step_2_baa', 'Business associate agreement executed', 'Execute HIPAA compliant Business Associate Agreement.', 1, 'upload_template', 'OneSmarter_BAA_Template.pdf', 'pdf'),
            (3, 'step_3_security', 'Security review returned to client', 'Upload security audit review document.', 1, 'upload_template', 'OneSmarter_SecurityReview_Template.pdf', 'pdf'),
            (4, 'step_4_contacts', 'Named & after-hours contacts recorded', 'Designate after-hours contact personnel.', 1, 'contact_manager', None, None),
            (5, 'step_5_claim_sys', 'Claims system identified and verified', 'Identify client claims vendor software system.', 2, 'claim_verify', None, None),
            (6, 'step_6_transfer_method', 'Delivery method agreed', 'Configure secure transfer mechanism (SFTP, API drop).', 2, 'transfer_config', None, None),
            (7, 'step_7_835_val', 'Sample 835 received and validated', 'Validate structural integrity of sample X12 835 file.', 2, 'x12_835_validate', 'OneSmarter_Sample835_Template.edi', 'edi'),
            (8, 'step_8_mapping', 'Mapping notes written & configured', 'Open Mapping Application to configure 835 conversion.', 2, 'mapping_redirect', None, None),
            (9, 'step_9_sftp', 'Test environment created & SFTP configured', 'Open SFTP App to provision test folders and SSH keys.', 3, 'sftp_redirect', None, None),
            (10, 'step_10_test_review', 'Test conversions reviewed with client', 'Verify side-by-side conversion of sample 835 files.', 3, 'side_by_side_done', None, None),
            (11, 'step_11_send_ftp', 'Send test file to client FTP', 'Transmit verified test payload to client FTP server.', 3, 'send_ftp_action', None, None),
            (12, 'step_12_email_attach', 'Upload email conversation attachment', 'Attach email confirmation / sign-off thread from client.', 3, 'email_upload', None, None),
            (13, 'step_13_schedule', 'Schedule live onboarding go-live date', 'Set scheduled date and time for live production cutover.', 4, 'schedule_action', None, None),
            (14, 'step_14_go_live', 'Go live checklist & controls verified', 'Confirm production cutover safeguards and monitoring.', 4, 'text_submission', None, None),
            (15, 'step_15_delivery', 'First production file delivered & monitored', 'Monitor first live 835 delivery and conclude onboarding.', 4, 'text_submission_final', None, None),
        ]

        for snum, skey, title, desc, pnum, atype, dname, dext in steps_data:
            s, _ = OnboardingStepDefinition.objects.get_or_create(
                step_number=snum,
                defaults={
                    'step_key': skey, 'title': title, 'description': desc,
                    'phase': phases_dict[pnum], 'action_type': atype,
                    'download_filename': dname, 'download_extension': dext
                }
            )
            s.step_key = skey
            s.title = title
            s.description = desc
            s.phase = phases_dict[pnum]
            s.action_type = atype
            s.download_filename = dname
            s.download_extension = dext
            s.save()

        # Seed GoLive Step Definitions (Exact 6 steps as required)
        self.stdout.write('Seeding Go Live step definitions (6-step redesign)...')
        golive_steps_data = [
            (1, 'golive_step_1_auth', 'Pre-Flight Readiness & Cutover Authorization', 'Upload signed authorization document establishing production readiness.', 'golive_doc_step1', 'OneSmarter_MutualNDA_Template.pdf', 'pdf'),
            (2, 'golive_step_2_compliance', 'Baseline & Final Compliance Confirmation', 'Execute and upload final production baseline compliance confirmation.', 'golive_doc_step2', 'OneSmarter_BAA_Template.pdf', 'pdf'),
            (3, 'golive_step_3_sftp', 'Production SFTP setup', 'Configure production SFTP checklist (watched folder, SSH keys, zero change) or execute bounded routing.', 'golive_sftp', None, None),
            (4, 'golive_step_4_schedule', 'Production Schedule', 'Establish the required production go-live cutover date and optional execution time.', 'golive_schedule', None, None),
            (5, 'golive_step_5_comment', 'Any Special Comment', 'Record optional special instructions, escalation overrides, or rollout comments.', 'golive_comment', None, None),
            (6, 'golive_step_6_successful', 'Production Successful', 'Conclude production cutover and verify live production delivery health.', 'golive_complete', None, None),
        ]

        for snum, skey, title, desc, atype, dname, dext in golive_steps_data:
            g, _ = GoLiveStepDefinition.objects.get_or_create(
                step_number=snum,
                defaults={
                    'step_key': skey, 'title': title, 'description': desc,
                    'action_type': atype, 'download_filename': dname, 'download_extension': dext or 'pdf'
                }
            )
            g.step_key = skey
            g.title = title
            g.description = desc
            g.action_type = atype
            g.download_filename = dname
            g.download_extension = dext or 'pdf'
            g.save()

        self.stdout.write('Seeding default employee roles...')
        roles = ['Named Contact', 'Escalation Contact', 'After-Hours On-Call', 'Technical Lead', 'Billing Administrator']
        for rname in roles:
            EmployeeRole.objects.get_or_create(role_name=rname, defaults={'is_system': True})

        self.stdout.write('Seeding default clients...')
        clients_data = [
            ("abc", "ABC Health Plan", "ABCHP", "In-house", "14 Mar 2025", "Today 09:41", "Rushi", "Healthy", "production", "support@abc.example", 100),
            ("cardinal", "Cardinal Benefit Administrators", "CARDINAL", "Legacy AS/400", "02 May 2025", "Today 08:12", "Prajval", "Healthy", "production", "ops@cardinal.example", 100),
            ("miami", "Miami Valley TPA", "MIAMI", "Vendor hosted", "19 Jun 2025", "Yesterday", "Rushi", "Quiet 26h", "production", "claims@miamivalley.example", 100),
            ("great-lakes", "Great Lakes Benefit Trust", "GLBT", "In-house", "30 Jul 2025", "Today 07:55", "Prajval", "Healthy", "production", "admin@greatlakes.example", 100),
            ("buckeye", "Buckeye Plan Services", "BUCKEYE", "Vendor hosted", None, "Test file 4", "Rushi", "Our move", "onboarding", "contact@buckeye.example", 27),
            ("northwood", "Northwood Administrators", "NORTHWOOD", "Vendor hosted", None, None, "Vikram J.", "Waiting on client", "onboarding", "admin@northwood.example", 0),
        ]

        all_steps = list(OnboardingStepDefinition.objects.all().order_by('step_number'))
        all_gl_steps = list(GoLiveStepDefinition.objects.all().order_by('step_number'))

        for cid, name, code, claims_sys, live_since, last_file, owner, state, stage, contact, pct in clients_data:
            c, _ = Client.objects.get_or_create(
                id=cid,
                defaults={
                    'name': name, 'code': code, 'claims_system': claims_sys,
                    'live_since': live_since, 'last_file': last_file,
                    'owner': owner, 'state': state, 'stage': stage,
                    'contact_info': contact, 'progress_pct': pct
                }
            )
            c.name = name
            c.code = code
            c.claims_system = claims_sys
            c.live_since = live_since
            c.last_file = last_file
            c.owner = owner
            c.state = state
            c.stage = stage
            c.contact_info = contact
            c.progress_pct = pct
            c.save()

            # Seed Test Environment for client
            ClientTestEnvironment.objects.get_or_create(
                client=c,
                defaults={
                    'sftp_host': 'sftp-test.onesmarter.internal',
                    'sftp_port': 22,
                    'sftp_username': f"{cid}_sandbox",
                    'watched_folder': f"/inbound/{cid}_835_test",
                    'keys_status': 'Verified & Isolated',
                    'mpl_delivery_blocked': True,
                    'archive_retention_days': 90,
                    'test_status': 'Verified' if stage == 'production' else 'In Progress',
                    'notes': 'Safe isolated conversion sandbox active.'
                }
            )

            # Onboarding Step Statuses
            if stage == 'production':
                for sdef in all_steps:
                    ClientStepStatus.objects.get_or_create(client=c, step=sdef, defaults={'status': 'DONE'})
                for gdef in all_gl_steps:
                    ClientGoLiveStatus.objects.get_or_create(client=c, step=gdef, defaults={'status': 'DONE'})
            else:
                for sdef in all_steps:
                    if sdef.step_number == 1:
                        ClientStepStatus.objects.get_or_create(client=c, step=sdef, defaults={'status': 'IN_PROGRESS'})
                    else:
                        ClientStepStatus.objects.get_or_create(client=c, step=sdef, defaults={'status': 'WAITING'})
                for gdef in all_gl_steps:
                    if gdef.step_number == 1:
                        ClientGoLiveStatus.objects.get_or_create(client=c, step=gdef, defaults={'status': 'IN_PROGRESS'})
                    else:
                        ClientGoLiveStatus.objects.get_or_create(client=c, step=gdef, defaults={'status': 'WAITING'})

            # Seed Documents for client
            ClientDocument.objects.get_or_create(
                client=c,
                document_name='Mutual Non-Disclosure Agreement',
                defaults={
                    'original_filename': f'{cid}_mutual_nda_signed.pdf',
                    'storage_path': f'data/evidence/{cid}_nda.pdf',
                    'document_type': 'Legal / Confidentiality',
                    'direction': 'Client → OneSmarter',
                    'file_size': 48200,
                    'mime_type': 'application/pdf',
                    'status': 'Executed',
                    'uploaded_by': 'Admin User'
                }
            )
            ClientDocument.objects.get_or_create(
                client=c,
                document_name='Business Associate Agreement (HIPAA)',
                defaults={
                    'original_filename': f'{cid}_baa_executed.pdf',
                    'storage_path': f'data/evidence/{cid}_baa.pdf',
                    'document_type': 'HIPAA Compliance',
                    'direction': 'Client → OneSmarter',
                    'file_size': 51200,
                    'mime_type': 'application/pdf',
                    'status': 'Executed',
                    'uploaded_by': 'Admin User'
                }
            )
            ClientDocument.objects.get_or_create(
                client=c,
                document_name='Sample 835 Remittance Advice',
                defaults={
                    'original_filename': f'{cid}_sample_835.edi',
                    'storage_path': f'data/evidence/{cid}_sample835.edi',
                    'document_type': 'Test Data / Mapping',
                    'direction': 'Client → OneSmarter',
                    'file_size': 3240,
                    'mime_type': 'text/plain',
                    'status': 'Validated',
                    'uploaded_by': 'Admin User'
                }
            )

        # Seed initial login history for Last Login dynamic tracking
        if not LoginHistory.objects.exists():
            prev_login_time = datetime.now(timezone.utc) - timedelta(days=1, hours=6, minutes=25)
            LoginHistory.objects.create(
                username='admin',
                login_time=prev_login_time,
                logout_time=prev_login_time + timedelta(minutes=30),
                ip_address='192.168.1.45',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0',
                status='SUCCESS'
            )

        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@onesmarter.com', 'adminpassword')
            self.stdout.write(self.style.SUCCESS('Created default superuser "admin"'))

        self.stdout.write(self.style.SUCCESS('Successfully seeded Django database!'))
