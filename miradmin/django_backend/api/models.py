from django.db import models
from django.contrib.auth.models import User

class AdminMFA(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='mfa')
    totp_secret = models.CharField(max_length=32, null=True, blank=True)
    is_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_mfa'
        
class Client(models.Model):
    id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, null=True, blank=True)
    claims_system = models.CharField(max_length=128, default='Vendor hosted')
    owner = models.CharField(max_length=128, default='Vikram J.')
    state = models.CharField(max_length=64, default='Waiting on client')
    stage = models.CharField(max_length=32, default='onboarding')
    contact_info = models.CharField(max_length=255, null=True, blank=True)
    live_since = models.CharField(max_length=64, null=True, blank=True)
    last_file = models.CharField(max_length=128, null=True, blank=True)
    progress_pct = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clients'

    def __str__(self):
        return f"{self.name} ({self.id})"


class OnboardingPhase(models.Model):
    phase_number = models.IntegerField(unique=True)
    phase_name = models.CharField(max_length=128)

    class Meta:
        db_table = 'onboarding_phases'

    def __str__(self):
        return self.phase_name


class OnboardingStepDefinition(models.Model):
    step_number = models.IntegerField(unique=True)
    step_key = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    phase = models.ForeignKey(OnboardingPhase, on_delete=models.CASCADE, related_name='steps')
    action_type = models.CharField(max_length=64, default='upload_template')
    download_filename = models.CharField(max_length=255, null=True, blank=True)
    download_extension = models.CharField(max_length=16, null=True, blank=True)

    class Meta:
        db_table = 'onboarding_step_definitions'
        ordering = ['step_number']

    def __str__(self):
        return f"Step {self.step_number}: {self.title}"


class ClientStepStatus(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='step_statuses')
    step = models.ForeignKey(OnboardingStepDefinition, on_delete=models.CASCADE, related_name='client_statuses')
    status = models.CharField(max_length=32, default='WAITING')  # DONE, IN_PROGRESS, WAITING
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.CharField(max_length=128, null=True, blank=True)

    class Meta:
        db_table = 'client_step_statuses'
        unique_together = ('client', 'step')


class StepUpload(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='uploads')
    step = models.ForeignKey(OnboardingStepDefinition, on_delete=models.CASCADE, related_name='uploads')
    original_filename = models.CharField(max_length=255)
    stored_filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=512)
    file_size = models.IntegerField(default=0)
    validation_status = models.CharField(max_length=32, default='PASSED')  # PENDING, PASSED, FAILED
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'step_uploads'
        ordering = ['-id']


class StepNote(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='notes')
    step = models.ForeignKey(OnboardingStepDefinition, on_delete=models.CASCADE, related_name='notes')
    note_text = models.TextField()
    author = models.CharField(max_length=128, default='Admin User')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'step_notes'
        ordering = ['-id']


class EmployeeRole(models.Model):
    role_name = models.CharField(max_length=128, unique=True)
    description = models.TextField(null=True, blank=True)
    is_system = models.BooleanField(default=False)

    class Meta:
        db_table = 'employee_roles'


class ClientContact(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='contacts')
    role_name = models.CharField(max_length=128)
    employee_name = models.CharField(max_length=255)
    email = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=64, null=True, blank=True)
    alternate_contact = models.CharField(max_length=255, null=True, blank=True)
    after_hours_notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'client_contacts'


class ClaimSystemVerification(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='verifications')
    verification_text = models.TextField()
    verified_by = models.CharField(max_length=128, default='Admin User')
    verified_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'claim_system_verifications'


class ClientTransferConfig(models.Model):
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='transfer_config')
    method = models.CharField(max_length=64, default='SFTP')
    watched_folder_sftp = models.BooleanField(default=False)
    keys_exchanged = models.BooleanField(default=False)
    no_change_to_client_system = models.BooleanField(default=False)
    setup_status = models.CharField(max_length=64, default='Configured')
    notes = models.TextField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'client_transfer_configurations'


class StepSchedule(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='schedules')
    scheduled_date = models.CharField(max_length=32)
    scheduled_time = models.CharField(max_length=32)
    timezone = models.CharField(max_length=32, default='ET')
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'step_schedules'


class StepTextSubmission(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='text_submissions')
    step = models.ForeignKey(OnboardingStepDefinition, on_delete=models.CASCADE, related_name='text_submissions')
    submission_text = models.TextField()
    submitted_by = models.CharField(max_length=128, default='Admin User')
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'step_text_submissions'


# --- 1. Client Document Database ---
class ClientDocument(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='documents')
    document_name = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    storage_path = models.CharField(max_length=512)
    document_type = models.CharField(max_length=128, default='General')  # Legal / Confidentiality, HIPAA Compliance, Test Data, Security, Go-Live
    direction = models.CharField(max_length=64, default='Client → OneSmarter')
    file_size = models.IntegerField(default=0)
    mime_type = models.CharField(max_length=128, default='application/pdf')
    status = models.CharField(max_length=32, default='Executed')  # Executed, Validated, Uploaded, Archived
    uploaded_by = models.CharField(max_length=128, default='Admin User')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    validation_details = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'client_documents'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.document_name} ({self.client.name})"


# --- 2. Test Environment Model ---
class ClientTestEnvironment(models.Model):
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='test_environment')
    sftp_host = models.CharField(max_length=255, default='sftp-test.onesmarter.internal')
    sftp_port = models.IntegerField(default=22)
    sftp_username = models.CharField(max_length=128, default='sandbox_admin')
    watched_folder = models.CharField(max_length=255, default='/inbound/835_test')
    keys_status = models.CharField(max_length=128, default='Separate from Production')
    mpl_delivery_blocked = models.BooleanField(default=True)
    archive_retention_days = models.IntegerField(default=90)
    test_status = models.CharField(max_length=64, default='In Progress')  # In Progress, Verified, Idle
    last_tested_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'client_test_environments'

    def __str__(self):
        return f"TestEnv: {self.client.name}"


# --- 3. Go Live 6-Step Workflow Models ---
class GoLiveStepDefinition(models.Model):
    step_number = models.IntegerField(unique=True)
    step_key = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    action_type = models.CharField(max_length=64)  # golive_doc_step1, golive_doc_step2, golive_sftp, golive_schedule, golive_comment, golive_complete
    download_filename = models.CharField(max_length=255, null=True, blank=True)
    download_extension = models.CharField(max_length=16, default='pdf')

    class Meta:
        db_table = 'golive_step_definitions'
        ordering = ['step_number']

    def __str__(self):
        return f"GoLive Step {self.step_number}: {self.title}"


class ClientGoLiveStatus(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='golive_statuses')
    step = models.ForeignKey(GoLiveStepDefinition, on_delete=models.CASCADE, related_name='client_statuses')
    status = models.CharField(max_length=32, default='WAITING')  # DONE, IN_PROGRESS, WAITING
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.CharField(max_length=128, null=True, blank=True)

    class Meta:
        db_table = 'client_golive_statuses'
        unique_together = ('client', 'step')


class ClientGoLiveSFTP(models.Model):
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='golive_sftp')
    watched_folder_sftp = models.BooleanField(default=False)
    keys_exchanged = models.BooleanField(default=False)
    no_change_to_client_system = models.BooleanField(default=False)
    in_bounded_action = models.BooleanField(default=False)
    out_bounded_action = models.BooleanField(default=False)
    notes = models.TextField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'client_golive_sftp'


class ClientGoLiveSchedule(models.Model):
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='golive_schedule')
    production_date = models.CharField(max_length=32)  # REQUIRED
    production_time = models.CharField(max_length=32, null=True, blank=True)  # OPTIONAL
    entered_by = models.CharField(max_length=128, default='Admin User')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'client_golive_schedules'


class ClientGoLiveComment(models.Model):
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='golive_comment')
    comment_text = models.TextField(null=True, blank=True)  # OPTIONAL
    entered_by = models.CharField(max_length=128, default='Admin User')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'client_golive_comments'


# --- 4. Login History Database ---
class LoginHistory(models.Model):
    username = models.CharField(max_length=128, default='admin')
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    ip_address = models.CharField(max_length=64, default='127.0.0.1')
    user_agent = models.CharField(max_length=255, default='Mozilla/5.0')
    status = models.CharField(max_length=32, default='SUCCESS')  # SUCCESS, FAILED
    session_token = models.CharField(max_length=128, null=True, blank=True)

    class Meta:
        db_table = 'login_history'
        ordering = ['-login_time']


# --- 5. Centralized Audit Log System ---
class AuditLog(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True, related_name='audit_logs')
    module = models.CharField(max_length=64, default='SYSTEM')  # CLIENTS, DOCUMENTS, ONBOARDING, TEST_ENV, GO_LIVE, AUTH
    action = models.CharField(max_length=128)
    details = models.TextField(null=True, blank=True)
    entity_id = models.CharField(max_length=128, null=True, blank=True)
    ip_address = models.CharField(max_length=64, default='127.0.0.1')
    performed_by = models.CharField(max_length=128, default='Admin User')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.module}] {self.action} by {self.performed_by} at {self.timestamp}"
