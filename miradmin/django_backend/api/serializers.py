from rest_framework import serializers
from .models import (
    Client, OnboardingPhase, OnboardingStepDefinition, ClientStepStatus,
    StepUpload, StepNote, EmployeeRole, ClientContact, ClaimSystemVerification,
    ClientTransferConfig, StepSchedule, StepTextSubmission, AuditLog,
    ClientDocument, ClientTestEnvironment, GoLiveStepDefinition, ClientGoLiveStatus,
    ClientGoLiveSFTP, ClientGoLiveSchedule, ClientGoLiveComment, LoginHistory
)

class ClientSerializer(serializers.ModelSerializer):
    claimsSystem = serializers.CharField(source='claims_system', read_only=True)
    contactInfo = serializers.CharField(source='contact_info', read_only=True)
    liveSince = serializers.CharField(source='live_since', read_only=True)
    lastFile = serializers.CharField(source='last_file', read_only=True)

    class Meta:
        model = Client
        fields = [
            'id', 'name', 'code', 'claims_system', 'claimsSystem',
            'owner', 'state', 'stage', 'contact_info', 'contactInfo',
            'live_since', 'liveSince', 'last_file', 'lastFile',
            'progress_pct', 'created_at', 'updated_at'
        ]


class OnboardingPhaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingPhase
        fields = ['id', 'phase_number', 'phase_name']


class OnboardingStepDefinitionSerializer(serializers.ModelSerializer):
    phase_name = serializers.CharField(source='phase.phase_name', read_only=True)
    phase_number = serializers.IntegerField(source='phase.phase_number', read_only=True)

    class Meta:
        model = OnboardingStepDefinition
        fields = [
            'id', 'step_number', 'step_key', 'title', 'description',
            'phase', 'phase_name', 'phase_number', 'action_type',
            'download_filename', 'download_extension'
        ]


class StepUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = StepUpload
        fields = [
            'id', 'client', 'step', 'original_filename', 'stored_filename',
            'file_size', 'validation_status', 'uploaded_at'
        ]


class StepNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = StepNote
        fields = ['id', 'client', 'step', 'note_text', 'author', 'created_at']


class EmployeeRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeRole
        fields = ['id', 'role_name', 'description', 'is_system']


class ClientContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientContact
        fields = [
            'id', 'client', 'role_name', 'employee_name', 'email',
            'phone', 'alternate_contact', 'after_hours_notes', 'created_at'
        ]


class ClientTransferConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientTransferConfig
        fields = [
            'id', 'client', 'method', 'watched_folder_sftp', 'keys_exchanged',
            'no_change_to_client_system', 'setup_status', 'notes', 'updated_at'
        ]


class StepScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = StepSchedule
        fields = ['id', 'client', 'scheduled_date', 'scheduled_time', 'timezone', 'notes', 'created_at']


class StepTextSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StepTextSubmission
        fields = ['id', 'client', 'step', 'submission_text', 'submitted_by', 'submitted_at']


class ClaimSystemVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimSystemVerification
        fields = ['id', 'client', 'verification_text', 'verified_by', 'verified_at']


# --- 1. Client Document Serializer ---
class ClientDocumentSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)

    class Meta:
        model = ClientDocument
        fields = [
            'id', 'client', 'client_name', 'document_name', 'original_filename',
            'storage_path', 'document_type', 'direction', 'file_size', 'mime_type',
            'status', 'uploaded_by', 'uploaded_at', 'updated_at', 'validation_details'
        ]


# --- 2. Test Environment Serializer ---
class ClientTestEnvironmentSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)

    class Meta:
        model = ClientTestEnvironment
        fields = [
            'id', 'client', 'client_name', 'sftp_host', 'sftp_port', 'sftp_username',
            'watched_folder', 'keys_status', 'mpl_delivery_blocked',
            'archive_retention_days', 'test_status', 'last_tested_at', 'notes', 'updated_at'
        ]


# --- 3. Go Live Serializers ---
class GoLiveStepDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoLiveStepDefinition
        fields = [
            'id', 'step_number', 'step_key', 'title', 'description',
            'action_type', 'download_filename', 'download_extension'
        ]


class ClientGoLiveSFTPSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientGoLiveSFTP
        fields = [
            'id', 'client', 'watched_folder_sftp', 'keys_exchanged',
            'no_change_to_client_system', 'in_bounded_action', 'out_bounded_action',
            'notes', 'updated_at'
        ]


class ClientGoLiveScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientGoLiveSchedule
        fields = [
            'id', 'client', 'production_date', 'production_time',
            'entered_by', 'created_at', 'updated_at'
        ]


class ClientGoLiveCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientGoLiveComment
        fields = [
            'id', 'client', 'comment_text', 'entered_by', 'created_at', 'updated_at'
        ]


# --- 4. Login History Serializer ---
class LoginHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginHistory
        fields = [
            'id', 'username', 'login_time', 'logout_time', 'ip_address',
            'user_agent', 'status'
        ]


# --- 5. Audit Log Serializer ---
class AuditLogSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'client', 'client_name', 'module', 'action', 'details',
            'entity_id', 'ip_address', 'performed_by', 'timestamp'
        ]
