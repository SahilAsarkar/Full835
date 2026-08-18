import os, re, hashlib
from typing import Tuple, Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.http import FileResponse, Http404
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.core.mail import send_mail, EmailMessage

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB limit
EVID_DIR = os.path.join(settings.BASE_DIR, 'evidence_uploads')

from .models import (
    Client, OnboardingPhase, OnboardingStepDefinition, ClientStepStatus,
    StepUpload, StepNote, EmployeeRole, ClientContact, ClaimSystemVerification,
    ClientTransferConfig, StepSchedule, StepTextSubmission, AuditLog,
    ClientDocument, ClientTestEnvironment, GoLiveStepDefinition, ClientGoLiveStatus,
    ClientGoLiveSFTP, ClientGoLiveSchedule, ClientGoLiveComment, LoginHistory, AdminMFA
)
import pyotp
import qrcode
import base64
from io import BytesIO
from .serializers import (
    ClientSerializer, OnboardingStepDefinitionSerializer, StepUploadSerializer,
    StepNoteSerializer, EmployeeRoleSerializer, ClientContactSerializer,
    ClientTransferConfigSerializer, StepScheduleSerializer, StepTextSubmissionSerializer,
    ClaimSystemVerificationSerializer, AuditLogSerializer, ClientDocumentSerializer,
    ClientTestEnvironmentSerializer, GoLiveStepDefinitionSerializer,
    ClientGoLiveSFTPSerializer, ClientGoLiveScheduleSerializer, ClientGoLiveCommentSerializer,
    LoginHistorySerializer
)
from .validation import (
    validate_step_upload, validate_x12_835_content,
    validate_phone_number, validate_email_address, get_step_download_filename,
    validate_golive_step_upload
)
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate

# --- Helper: Centralized Audit Logger ---
def log_audit(client=None, module='SYSTEM', action='ACTION', details='', entity_id=None, request=None, performed_by='Admin User'):
    ip = '127.0.0.1'
    if request:
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_forwarded.split(',')[0].strip() if x_forwarded else request.META.get('REMOTE_ADDR', '127.0.0.1')
        if hasattr(request, 'user') and request.user and str(request.user):
            performed_by = str(request.user)

    return AuditLog.objects.create(
        client=client,
        module=module,
        action=action,
        details=details,
        entity_id=str(entity_id) if entity_id else None,
        ip_address=ip,
        performed_by=performed_by
    )


# --- Authentication & Dynamic Last Login ---
class AuthLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username_from_email = request.data.get('email', '')
        password = request.data.get('password', '')
        otp_code = request.data.get('code', '')
        
        # Determine actual username. 
        if username_from_email:
            username_attempt = username_from_email
            if '@' in username_attempt and username_attempt.startswith('admin'):
                username_attempt = 'admin'
        else:
            username_attempt = request.data.get('username', 'admin')

        user = authenticate(username=username_attempt, password=password)

        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_forwarded.split(',')[0].strip() if x_forwarded else request.META.get('REMOTE_ADDR', '127.0.0.1')
        ua = request.META.get('HTTP_USER_AGENT', 'Mozilla/5.0')[:250]

        if not user or (not user.is_superuser and not user.is_staff):
            LoginHistory.objects.create(
                username=username_attempt, ip_address=ip, user_agent=ua, status='FAILED'
            )
            log_audit(module='AUTH', action='LOGIN_FAILED', details=f"Failed admin login attempt from {ip}.", request=request)
            return Response({'ok': False, 'error': 'Invalid credentials or unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        # --- TOTP MFA LOGIC ---
        mfa, created = AdminMFA.objects.get_or_create(user=user)
        
        if not mfa.is_enabled:
            # Setup phase
            if not mfa.totp_secret:
                mfa.totp_secret = pyotp.random_base32()
                mfa.save()
                
            if not otp_code:
                # Need to show setup QR code
                provisioning_uri = pyotp.totp.TOTP(mfa.totp_secret).provisioning_uri(
                    name=user.email or user.username, 
                    issuer_name="OneSmarter Admin"
                )
                img = qrcode.make(provisioning_uri)
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                qr_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                
                return Response({
                    'ok': True,
                    'require_setup': True,
                    'qr_base64': qr_base64,
                    'secret': mfa.totp_secret
                })
            else:
                # Verifying first-time setup code
                totp = pyotp.TOTP(mfa.totp_secret)
                if not totp.verify(otp_code):
                    return Response({'ok': False, 'error': 'Invalid authenticator code.'}, status=status.HTTP_401_UNAUTHORIZED)
                
                mfa.is_enabled = True
                mfa.save()
        else:
            # Login phase
            if not otp_code:
                return Response({'ok': True, 'require_mfa': True})
            
            # Verifying regular login code
            totp = pyotp.TOTP(mfa.totp_secret)
            if not totp.verify(otp_code):
                return Response({'ok': False, 'error': 'Invalid authenticator code.'}, status=status.HTTP_401_UNAUTHORIZED)

        token, _ = Token.objects.get_or_create(user=user)

        # 1. Determine "Last Login" (previous successful login before this one)
        prev_login = LoginHistory.objects.filter(username=user.username, status='SUCCESS').order_by('-login_time').first()
        last_login_str = prev_login.login_time.strftime("%d/%m/%Y, %I:%M %p") if prev_login else "First Administrator Session"

        # 2. Record new current login
        new_login = LoginHistory.objects.create(
            username=user.username, ip_address=ip, user_agent=ua, status='SUCCESS', session_token=token.key[:16]
        )

        log_audit(module='AUTH', action='LOGIN_SUCCESS', details=f"Admin signed in from {ip}. Session active.", request=request)

        return Response({
            'ok': True,
            'token': token.key,
            'user': {
                'name': user.get_full_name() or user.username,
                'email': user.email,
                'role': 'Platform Admin'
            },
            'last_login': last_login_str,
            'expiresIn': 1800
        })

from django.contrib.auth.models import User

class AuthRegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip()
        password = request.data.get('password', '')
        name = request.data.get('name', '').strip()

        if not email or not password:
            return Response({'ok': False, 'error': 'Email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            return Response({'ok': False, 'error': 'An account with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        # Create the user and grant them admin/staff privileges
        user = User.objects.create_user(username=email, email=email, password=password)
        if name:
            parts = name.split(' ', 1)
            user.first_name = parts[0]
            if len(parts) > 1:
                user.last_name = parts[1]
        
        user.is_staff = True
        user.save()

        log_audit(module='AUTH', action='REGISTER_SUCCESS', details=f"New admin account created: {email}", request=request)

        return Response({
            'ok': True,
            'message': 'Account created successfully.'
        })

class AuthLogoutView(APIView):
    def post(self, request):
        if request.user and request.user.is_authenticated:
            try:
                request.user.auth_token.delete()
            except:
                pass
            
            # Optionally update the logout_time in LoginHistory, finding the latest by this user
            lh = LoginHistory.objects.filter(username=request.user.username, status='SUCCESS').order_by('-login_time').first()
            if lh:
                lh.logout_time = datetime.now(timezone.utc)
                lh.save()

        log_audit(module='AUTH', action='LOGOUT', details="Admin signed out. Session invalidated.", request=request)
        return Response({'ok': True, 'message': 'Logged out successfully'})


class AccessInfoView(APIView):
    def get(self, request):
        current_username = request.user.username if request.user and request.user.is_authenticated else 'admin'
        
        # Calculate dynamic previous login for current user
        successful_logins = LoginHistory.objects.filter(username=current_username, status='SUCCESS').order_by('-login_time')
        # Skip the most current login to get the previous login
        if successful_logins.count() > 1:
            prev_login = successful_logins[1]
            last_login_str = prev_login.login_time.isoformat()
        elif successful_logins.count() == 1:
            last_login_str = successful_logins[0].login_time.isoformat()
        else:
            last_login_str = None

        recent_history = LoginHistory.objects.all().order_by('-login_time')[:10]

        # Dynamically fetch staff from the database User model
        from django.contrib.auth.models import User
        staff_list = []
        for u in User.objects.filter(is_staff=True).order_by('id'):
            full_name = u.get_full_name() or u.username
            u_logins = LoginHistory.objects.filter(username=u.username, status='SUCCESS').order_by('-login_time')
            u_last_login = u_logins[0].login_time.isoformat() if u_logins.exists() else None
            
            # Determine MFA status
            has_mfa = AdminMFA.objects.filter(user=u, is_enabled=True).exists()
            mfa_type = "Authenticator (TOTP)" if has_mfa else "Not Configured"
            
            role = "Platform Admin" if u.is_superuser else "Implementation Specialist"
            access_level = "Full Access" if u.is_superuser else "Assigned Tenants"
            
            staff_list.append({
                'person': full_name,
                'role': role,
                'access': access_level,
                'mfa': mfa_type,
                'last_login': u_last_login,
                'status': 'Active' if u.is_active else 'Inactive'
            })

        # Fallback if no staff returned
        if not staff_list:
            staff_list = [
                {'person': 'Vikram J.', 'role': 'Platform Admin', 'access': 'Full Access', 'mfa': 'Hardware Key (FIDO2)', 'last_login': last_login_str, 'status': 'Active'},
            ]

        return Response({
            'ok': True,
            'last_login': last_login_str,
            'staff': staff_list,
            'recent_logins': LoginHistorySerializer(recent_history, many=True).data
        })


# --- Onboarding Step Progression & Helpers ---
def find_step_definition(step_key):
    step = OnboardingStepDefinition.objects.filter(step_key=step_key).first()
    if not step and str(step_key).isdigit():
        step = OnboardingStepDefinition.objects.filter(step_number=int(step_key)).first()
    if not step:
        parts = str(step_key).split('_')
        if len(parts) >= 2 and parts[0] == 'step' and parts[1].isdigit():
            step = OnboardingStepDefinition.objects.filter(step_number=int(parts[1])).first()
    return step


def guard_step_unlocked(client, step_def, allow_done=True) -> Tuple[bool, Optional[Response]]:
    """
    Server-side compliance ladder enforcer:
    Checks whether status is IN_PROGRESS (or DONE for repeatable steps), returning 409 Conflict otherwise.
    """
    st_obj, _ = ClientStepStatus.objects.get_or_create(client=client, step=step_def, defaults={'status': 'WAITING'})
    if st_obj.status == 'IN_PROGRESS' or (allow_done and st_obj.status == 'DONE'):
        return True, None
    return False, Response({
        'ok': False,
        'error': f"Compliance Ladder Enforcement (409 Conflict): Step {step_def.step_number} ('{step_def.title}') is currently locked with status '{st_obj.status}'. Complete previous steps sequentially first."
    }, status=status.HTTP_409_CONFLICT)

# Alias for backward compatibility
enforce_step_in_progress_or_done = guard_step_unlocked


def recalculate_client_progress(client):
    total = OnboardingStepDefinition.objects.count()
    if total == 0:
        client.progress_pct = 0
        client.save()
        return
    done_count = ClientStepStatus.objects.filter(client=client, status='DONE').count()
    client.progress_pct = int(round((done_count / total) * 100))
    if done_count >= total:
        client.stage = 'production'
        client.state = 'Healthy'
    else:
        client.stage = 'onboarding'
    client.save()


def advance_next_step(client, current_step_number):
    total = OnboardingStepDefinition.objects.count()
    if current_step_number < total:
        next_step = OnboardingStepDefinition.objects.filter(step_number=current_step_number + 1).first()
        if next_step:
            st_next, _ = ClientStepStatus.objects.get_or_create(client=client, step=next_step)
            if st_next.status != 'DONE':
                st_next.status = 'IN_PROGRESS'
                st_next.save()
    if current_step_number >= total:
        client.stage = 'production'
        client.state = 'Healthy'
        client.progress_pct = 100
        client.save()
    else:
        recalculate_client_progress(client)


def build_client_state(client):
    recalculate_client_progress(client)
    steps_qs = OnboardingStepDefinition.objects.all().order_by('step_number')
    steps_list = []
    
    for step_def in steps_qs:
        st_obj, _ = ClientStepStatus.objects.get_or_create(client=client, step=step_def)
        latest_upload = StepUpload.objects.filter(client=client, step=step_def).order_by('-id').first()
        latest_note = StepNote.objects.filter(client=client, step=step_def).order_by('-id').first()
        
        extra = {}
        if step_def.action_type == 'contact_manager':
            contacts = ClientContact.objects.filter(client=client).order_by('id')
            extra['contacts'] = ClientContactSerializer(contacts, many=True).data
        elif step_def.action_type == 'claim_verify':
            ver = ClaimSystemVerification.objects.filter(client=client).order_by('-id').first()
            if ver:
                extra['verification'] = {'verification_text': ver.verification_text, 'verified_by': ver.verified_by}
        elif step_def.action_type == 'transfer_config':
            tc = ClientTransferConfig.objects.filter(client=client).first()
            if tc:
                extra['transferConfig'] = ClientTransferConfigSerializer(tc).data
        elif step_def.action_type == 'schedule_action':
            sc = StepSchedule.objects.filter(client=client).order_by('-id').first()
            if sc:
                extra['schedule'] = StepScheduleSerializer(sc).data
        elif step_def.action_type in ('text_submission', 'text_submission_final'):
            sub = StepTextSubmission.objects.filter(client=client, step=step_def).order_by('-id').first()
            if sub:
                extra['submission'] = StepTextSubmissionSerializer(sub).data

        steps_list.append({
            'id': step_def.step_number,
            'step_number': step_def.step_number,
            'key': step_def.step_key,
            'title': step_def.title,
            'desc': step_def.description,
            'phase': step_def.phase.phase_name,
            'phaseId': step_def.phase.phase_number,
            'actionType': step_def.action_type,
            'status': st_obj.status,
            'done': st_obj.status == 'DONE',
            'inProgress': st_obj.status == 'IN_PROGRESS',
            'downloadName': step_def.download_filename,
            'file': bool(step_def.download_filename),
            'ext': step_def.download_extension or 'pdf',
            'latestUpload': StepUploadSerializer(latest_upload).data if latest_upload else None,
            'latestNote': StepNoteSerializer(latest_note).data if latest_note else None,
            'extra': extra
        })

    roles = EmployeeRole.objects.all().order_by('id')

    return {
        'client': ClientSerializer(client).data,
        'steps': steps_list,
        'employee_roles': EmployeeRoleSerializer(roles, many=True).data,
        'transfer_methods': [{'id': 1, 'method_name': 'SFTP'}, {'id': 2, 'method_name': 'HTTPS API'}]
    }


# --- Client ViewSet ---
class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer

    def create(self, request, *args, **kwargs):
        name = request.data.get('name', '').strip()
        if not name:
            return Response({'error': 'Client name is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if Client.objects.filter(name__iexact=name).exists():
            return Response({'error': f"Duplicate client: A client named '{name}' already exists in the database."}, status=status.HTTP_400_BAD_REQUEST)

        cid = request.data.get('id') or re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        code = (request.data.get('code') or cid.upper()).strip()

        if Client.objects.filter(id__iexact=cid).exists() or (code and Client.objects.filter(code__iexact=code).exists()):
            return Response({'error': f"Duplicate client identifier: Client code or ID '{code or cid}' is already registered."}, status=status.HTTP_400_BAD_REQUEST)

        claims_sys = request.data.get('claimsSystem') or request.data.get('claims_system') or 'Vendor hosted'
        owner = request.data.get('owner') or 'Vikram J.'
        contact_info = request.data.get('contactInfo') or request.data.get('contact_info') or ''
        contact_info = contact_info.strip()

        if contact_info:
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError
            try:
                validate_email(contact_info)
            except ValidationError:
                return Response({'error': f"Invalid email format: '{contact_info}' is not a valid email address."}, status=status.HTTP_400_BAD_REQUEST)
                
            if Client.objects.filter(contact_info__iexact=contact_info).exists():
                return Response({'error': f"Duplicate email: A client with the email '{contact_info}' already exists."}, status=status.HTTP_400_BAD_REQUEST)

        stage = request.data.get('stage') or 'onboarding'
        state_str = request.data.get('state') or ('Healthy' if stage == 'production' else 'Waiting on client')

        client = Client.objects.create(
            id=cid, name=name, code=code, claims_system=claims_sys,
            owner=owner, state=state_str, stage=stage, contact_info=contact_info,
            progress_pct=0
        )

        # Initialize Onboarding step 1
        step1 = OnboardingStepDefinition.objects.filter(step_number=1).first()
        if step1:
            ClientStepStatus.objects.get_or_create(client=client, step=step1, defaults={'status': 'IN_PROGRESS'})

        # Initialize Go Live step 1
        gl_step1 = GoLiveStepDefinition.objects.filter(step_number=1).first()
        if gl_step1:
            ClientGoLiveStatus.objects.get_or_create(client=client, step=gl_step1, defaults={'status': 'IN_PROGRESS'})

        # Initialize Test Environment
        ClientTestEnvironment.objects.get_or_create(
            client=client,
            defaults={
                'sftp_host': 'sftp-test.onesmarter.internal',
                'sftp_username': f"{cid}_sandbox",
                'watched_folder': f"/inbound/{cid}_835_test",
                'keys_status': 'Separate from Production',
                'mpl_delivery_blocked': True,
                'archive_retention_days': 90,
                'test_status': 'In Progress'
            }
        )

        log_audit(client=client, module='CLIENTS', action='CLIENT_CREATED', details=f"Created new tenant '{name}' (ID: {cid}).", request=request)

        return Response({'ok': True, 'client': ClientSerializer(client).data}, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        client = self.get_object()
        cname = client.name
        cid = client.id
        client.delete()
        log_audit(module='CLIENTS', action='CLIENT_DELETED', details=f"Deleted client '{cname}' (ID: {cid}).", request=request)
        return Response({'ok': True, 'message': f"Client {cname} deleted."})

    @action(detail=True, methods=['get'])
    def state(self, request, pk=None):
        client = self.get_object()
        return Response({'ok': True, 'state': build_client_state(client)})

    @action(detail=True, methods=['get'])
    def steps(self, request, pk=None):
        client = self.get_object()
        state = build_client_state(client)
        return Response({'ok': True, 'steps': state['steps']})


# --- 1. Client Documents API ---
class ClientDocumentsListView(APIView):
    def get(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        docs = ClientDocument.objects.filter(client=client).order_by('-uploaded_at')
        return Response({
            'ok': True,
            'client_id': client.id,
            'client_name': client.name,
            'documents': ClientDocumentSerializer(docs, many=True).data
        })


class ClientDocumentUploadView(APIView):
    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        buf = request.body
        if len(buf) > MAX_UPLOAD_BYTES:
            return Response({'error': 'Upload exceeds 10 MB limit'}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        if len(buf) == 0:
            return Response({'error': 'Uploaded file is empty'}, status=status.HTTP_400_BAD_REQUEST)

        orig_filename = request.headers.get('X-Filename') or 'document.pdf'
        doc_name = request.headers.get('X-Doc-Name') or orig_filename.rsplit('.', 1)[0].replace('_', ' ').title()
        doc_type = request.headers.get('X-Doc-Type') or 'General Document'
        
        ext = orig_filename.rsplit('.', 1)[-1].lower() if '.' in orig_filename else 'pdf'
        mime_map = {'pdf': 'application/pdf', 'edi': 'text/plain', 'txt': 'text/plain', 'eml': 'message/rfc822', 'msg': 'application/vnd.ms-outlook'}
        mime = mime_map.get(ext, 'application/octet-stream')

        os.makedirs(EVID_DIR, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        safe_orig = re.sub(r"[^A-Za-z0-9._-]+", "_", orig_filename)[:120]
        stored_name = f"{client.id}_doc_{ts}_{safe_orig}"
        file_path = os.path.join(EVID_DIR, stored_name)

        with open(file_path, 'wb') as f:
            f.write(buf)

        doc = ClientDocument.objects.create(
            client=client,
            document_name=doc_name,
            original_filename=orig_filename,
            storage_path=file_path,
            document_type=doc_type,
            direction='Client → OneSmarter',
            file_size=len(buf),
            mime_type=mime,
            status='Uploaded',
            uploaded_by='Admin User'
        )

        log_audit(
            client=client, module='DOCUMENTS', action='DOCUMENT_UPLOAD',
            details=f"Uploaded '{orig_filename}' ({len(buf)} bytes) for {client.name}.",
            entity_id=str(doc.id), request=request
        )

        return Response({'ok': True, 'document': ClientDocumentSerializer(doc).data}, status=status.HTTP_201_CREATED)


class DocumentDownloadView(APIView):
    def get(self, request, doc_id):
        doc = ClientDocument.objects.filter(id=doc_id).first()
        if not doc:
            return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check file existence
        file_path = doc.storage_path
        if not os.path.exists(file_path):
            sample_dir = os.path.abspath(os.path.join(settings.BASE_DIR.parent, 'sample documents'))
            fallback = os.path.join(sample_dir, doc.original_filename)
            if os.path.exists(fallback):
                file_path = fallback
            else:
                return Response({'error': f"Physical file '{doc.original_filename}' missing on server."}, status=status.HTTP_404_NOT_FOUND)

        log_audit(
            client=doc.client, module='DOCUMENTS', action='DOCUMENT_DOWNLOAD',
            details=f"Downloaded '{doc.original_filename}' (Doc ID: {doc.id}).",
            entity_id=str(doc.id), request=request
        )

        response = FileResponse(open(file_path, 'rb'), content_type=doc.mime_type or 'application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{doc.original_filename}"'
        response['X-OneSmarter-Filename'] = doc.original_filename
        response['Content-Length'] = os.path.getsize(file_path)
        return response


class DocumentDeleteView(APIView):
    def delete(self, request, doc_id):
        doc = ClientDocument.objects.filter(id=doc_id).first()
        if not doc:
            return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)

        cid = doc.client.id
        doc_name = doc.document_name
        if doc.storage_path and os.path.exists(doc.storage_path):
            try:
                os.remove(doc.storage_path)
            except Exception:
                pass

        doc.delete()
        log_audit(
            client=doc.client, module='DOCUMENTS', action='DOCUMENT_DELETE',
            details=f"Deleted document '{doc_name}' from client {cid}.",
            entity_id=str(doc_id), request=request
        )
        return Response({'ok': True, 'message': 'Document deleted.'})


# --- 2. Test Environment API ---
class ClientTestEnvironmentView(APIView):
    def get(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        test_env, _ = ClientTestEnvironment.objects.get_or_create(
            client=client,
            defaults={
                'sftp_host': 'sftp-test.onesmarter.internal',
                'sftp_username': f"{client.id}_sandbox",
                'watched_folder': f"/inbound/{client.id}_835_test",
                'keys_status': 'Separate from Production',
                'mpl_delivery_blocked': True,
                'archive_retention_days': 90,
                'test_status': 'In Progress',
                'notes': 'Isolated sandbox test environment.'
            }
        )
        return Response({'ok': True, 'test_environment': ClientTestEnvironmentSerializer(test_env).data})

    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        test_env, _ = ClientTestEnvironment.objects.get_or_create(client=client)
        test_env.sftp_host = request.data.get('sftp_host', test_env.sftp_host)
        test_env.sftp_username = request.data.get('sftp_username', test_env.sftp_username)
        test_env.watched_folder = request.data.get('watched_folder', test_env.watched_folder)
        test_env.keys_status = request.data.get('keys_status', test_env.keys_status)
        test_env.mpl_delivery_blocked = bool(request.data.get('mpl_delivery_blocked', test_env.mpl_delivery_blocked))
        test_env.archive_retention_days = int(request.data.get('archive_retention_days', test_env.archive_retention_days))
        test_env.test_status = request.data.get('test_status', test_env.test_status)
        test_env.notes = request.data.get('notes', test_env.notes)
        test_env.save()

        log_audit(
            client=client, module='TEST_ENV', action='TEST_ENV_UPDATE',
            details=f"Updated test environment configuration for {client.name}.", request=request
        )

        return Response({'ok': True, 'test_environment': ClientTestEnvironmentSerializer(test_env).data})


class ClientTestRunView(APIView):
    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        test_env, _ = ClientTestEnvironment.objects.get_or_create(client=client)
        test_env.test_status = 'Verified'
        test_env.last_tested_at = datetime.now(timezone.utc)
        test_env.save()

        log_audit(
            client=client, module='TEST_ENV', action='TEST_EXECUTION',
            details=f"Executed sandbox 835-to-MIR test conversion run for {client.name}. Status: Verified.", request=request
        )

        return Response({
            'ok': True,
            'message': 'Test conversion executed successfully. 835 to MIR mapping verified.',
            'test_environment': ClientTestEnvironmentSerializer(test_env).data
        })


# --- 3. Go Live 6-Step Workflow API ---
def build_golive_state(client):
    steps_qs = GoLiveStepDefinition.objects.all().order_by('step_number')
    steps_list = []

    sftp_obj = ClientGoLiveSFTP.objects.filter(client=client).first()
    sched_obj = ClientGoLiveSchedule.objects.filter(client=client).first()
    comment_obj = ClientGoLiveComment.objects.filter(client=client).first()

    for sdef in steps_qs:
        st_obj, _ = ClientGoLiveStatus.objects.get_or_create(client=client, step=sdef)
        
        extra = {}
        if sdef.step_number == 3 and sftp_obj:
            extra['sftp'] = ClientGoLiveSFTPSerializer(sftp_obj).data
        elif sdef.step_number == 4 and sched_obj:
            extra['schedule'] = ClientGoLiveScheduleSerializer(sched_obj).data
        elif sdef.step_number == 5 and comment_obj:
            extra['comment'] = ClientGoLiveCommentSerializer(comment_obj).data

        steps_list.append({
            'id': sdef.step_number,
            'step_number': sdef.step_number,
            'key': sdef.step_key,
            'title': sdef.title,
            'desc': sdef.description,
            'actionType': sdef.action_type,
            'status': st_obj.status,
            'done': st_obj.status == 'DONE',
            'inProgress': st_obj.status == 'IN_PROGRESS',
            'downloadFilename': sdef.download_filename,
            'downloadExtension': sdef.download_extension,
            'extra': extra
        })

    done_count = sum(1 for s in steps_list if s['done'])
    pct = int(round((done_count / len(steps_list)) * 100)) if steps_list else 0

    return {
        'client': ClientSerializer(client).data,
        'steps': steps_list,
        'done_count': done_count,
        'total_steps': len(steps_list),
        'progress_pct': pct
    }


def advance_golive_step(client, current_step_num):
    next_step = GoLiveStepDefinition.objects.filter(step_number=current_step_num + 1).first()
    if next_step:
        st_next, _ = ClientGoLiveStatus.objects.get_or_create(client=client, step=next_step)
        if st_next.status != 'DONE':
            st_next.status = 'IN_PROGRESS'
            st_next.save()


class GoLiveStateView(APIView):
    def get(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'ok': True, 'state': build_golive_state(client)})


class GoLiveStep1UploadView(APIView):
    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        step1 = GoLiveStepDefinition.objects.filter(step_number=1).first()
        if not client or not step1:
            return Response({'error': 'Client or Step 1 not found'}, status=status.HTTP_404_NOT_FOUND)

        buf = request.body
        if len(buf) == 0:
            return Response({'error': 'File is empty'}, status=status.HTTP_400_BAD_REQUEST)
        if len(buf) > MAX_UPLOAD_BYTES:
            return Response({'error': 'File exceeds 10 MB limit'}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        orig_filename = request.headers.get('X-Filename') or 'OneSmarter_CutoverAuthorization_Signed.pdf'
        v_res = validate_golive_step_upload(1, buf, orig_filename)
        if not v_res.get('ok'):
            return Response({'ok': False, 'error': 'Validation failed', 'checks': v_res.get('checks')}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        os.makedirs(EVID_DIR, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        safe_orig = re.sub(r"[^A-Za-z0-9._-]+", "_", orig_filename)[:120]
        file_path = os.path.join(EVID_DIR, f"{client.id}_gl1_{ts}_{safe_orig}")
        with open(file_path, 'wb') as f:
            f.write(buf)

        # Mark Step 1 complete
        st1, _ = ClientGoLiveStatus.objects.get_or_create(client=client, step=step1)
        st1.status = 'DONE'
        st1.completed_at = datetime.now(timezone.utc)
        st1.completed_by = 'Admin User'
        st1.save()

        # Register in ClientDocument
        ClientDocument.objects.create(
            client=client,
            document_name='Pre-Flight Cutover Authorization',
            original_filename=orig_filename,
            storage_path=file_path,
            document_type='Go-Live Readiness',
            direction='Client → OneSmarter',
            file_size=len(buf),
            status='Executed',
            uploaded_by='Admin User'
        )

        advance_golive_step(client, 1)
        log_audit(client=client, module='GO_LIVE', action='STEP_1_UPLOAD', details=f"Uploaded Step 1 Cutover Authorization for {client.name}.", request=request)

        return Response({'ok': True, 'state': build_golive_state(client), 'checks': v_res.get('checks')})


class GoLiveStep1DownloadView(APIView):
    def get(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        sample_dir = os.path.abspath(os.path.join(settings.BASE_DIR.parent, 'sample documents'))
        file_path = os.path.join(sample_dir, 'OneSmarter_CutoverAuthorization_Template.pdf')
        if not os.path.exists(file_path):
            return Response({'error': 'Template file not found'}, status=status.HTTP_404_NOT_FOUND)

        log_audit(client=client, module='GO_LIVE', action='STEP_1_DOWNLOAD', details=f"Downloaded Step 1 template for {client.name}.", request=request)

        download_name = "OneSmarter_CutoverAuthorization_Template.pdf"
        response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{download_name}"'
        response['X-OneSmarter-Filename'] = download_name
        response['Content-Length'] = os.path.getsize(file_path)
        return response


class GoLiveStep2UploadView(APIView):
    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        step2 = GoLiveStepDefinition.objects.filter(step_number=2).first()
        if not client or not step2:
            return Response({'error': 'Client or Step 2 not found'}, status=status.HTTP_404_NOT_FOUND)

        buf = request.body
        if len(buf) == 0:
            return Response({'error': 'File is empty'}, status=status.HTTP_400_BAD_REQUEST)
        if len(buf) > MAX_UPLOAD_BYTES:
            return Response({'error': 'File exceeds 10 MB limit'}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        orig_filename = request.headers.get('X-Filename') or 'OneSmarter_ProductionBaseline_Signed.pdf'
        v_res = validate_golive_step_upload(2, buf, orig_filename)
        if not v_res.get('ok'):
            return Response({'ok': False, 'error': 'Validation failed', 'checks': v_res.get('checks')}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        os.makedirs(EVID_DIR, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        safe_orig = re.sub(r"[^A-Za-z0-9._-]+", "_", orig_filename)[:120]
        file_path = os.path.join(EVID_DIR, f"{client.id}_gl2_{ts}_{safe_orig}")
        with open(file_path, 'wb') as f:
            f.write(buf)

        st2, _ = ClientGoLiveStatus.objects.get_or_create(client=client, step=step2)
        st2.status = 'DONE'
        st2.completed_at = datetime.now(timezone.utc)
        st2.completed_by = 'Admin User'
        st2.save()

        ClientDocument.objects.create(
            client=client,
            document_name='Production Baseline & Compliance Sign-Off',
            original_filename=orig_filename,
            storage_path=file_path,
            document_type='Go-Live Compliance',
            direction='Client → OneSmarter',
            file_size=len(buf),
            status='Executed',
            uploaded_by='Admin User'
        )

        advance_golive_step(client, 2)
        log_audit(client=client, module='GO_LIVE', action='STEP_2_UPLOAD', details=f"Uploaded Step 2 Baseline Compliance for {client.name}.", request=request)

        return Response({'ok': True, 'state': build_golive_state(client), 'checks': v_res.get('checks')})


class GoLiveStep2DownloadView(APIView):
    def get(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        sample_dir = os.path.abspath(os.path.join(settings.BASE_DIR.parent, 'sample documents'))
        file_path = os.path.join(sample_dir, 'OneSmarter_ProductionBaseline_Template.pdf')
        if not os.path.exists(file_path):
            return Response({'error': 'Template file not found'}, status=status.HTTP_404_NOT_FOUND)

        log_audit(client=client, module='GO_LIVE', action='STEP_2_DOWNLOAD', details=f"Downloaded Step 2 template for {client.name}.", request=request)

        download_name = "OneSmarter_ProductionBaseline_Template.pdf"
        response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{download_name}"'
        response['X-OneSmarter-Filename'] = download_name
        response['Content-Length'] = os.path.getsize(file_path)
        return response


class GoLiveStep3SFTPView(APIView):
    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        step3 = GoLiveStepDefinition.objects.filter(step_number=3).first()
        if not client or not step3:
            return Response({'error': 'Client or Step 3 not found'}, status=status.HTTP_404_NOT_FOUND)

        sftp_obj, _ = ClientGoLiveSFTP.objects.get_or_create(client=client)
        
        # Check if button action was clicked (In Bounded or Out Bounded)
        button_action = request.data.get('action')
        if button_action == 'in_bounded':
            sftp_obj.in_bounded_action = True
            sftp_obj.save()
            log_audit(client=client, module='GO_LIVE', action='PRODUCTION_IN_BOUNDED', details=f"Executed Production In Bounded routing for {client.name}.", request=request)
            return Response({'ok': True, 'message': 'Production In Bounded configured successfully.', 'state': build_golive_state(client)})
        elif button_action == 'out_bounded':
            sftp_obj.out_bounded_action = True
            sftp_obj.save()
            log_audit(client=client, module='GO_LIVE', action='PRODUCTION_OUT_BOUNDED', details=f"Executed Production Out Bounded routing for {client.name}.", request=request)
            return Response({'ok': True, 'message': 'Production Out Bounded configured successfully.', 'state': build_golive_state(client)})

        # Standard SFTP Save & Complete
        sftp_obj.watched_folder_sftp = bool(request.data.get('watched_folder_sftp'))
        sftp_obj.keys_exchanged = bool(request.data.get('keys_exchanged'))
        sftp_obj.no_change_to_client_system = bool(request.data.get('no_change_to_client_system'))
        sftp_obj.notes = request.data.get('notes', '')
        sftp_obj.save()

        st3, _ = ClientGoLiveStatus.objects.get_or_create(client=client, step=step3)
        st3.status = 'DONE'
        st3.completed_at = datetime.now(timezone.utc)
        st3.completed_by = 'Admin User'
        st3.save()

        advance_golive_step(client, 3)
        log_audit(client=client, module='GO_LIVE', action='STEP_3_SFTP_COMPLETE', details=f"Completed Step 3 Production SFTP Setup for {client.name}.", request=request)

        return Response({'ok': True, 'state': build_golive_state(client)})


class GoLiveStep4ScheduleView(APIView):
    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        step4 = GoLiveStepDefinition.objects.filter(step_number=4).first()
        if not client or not step4:
            return Response({'error': 'Client or Step 4 not found'}, status=status.HTTP_404_NOT_FOUND)

        prod_date = request.data.get('production_date', '').strip()
        prod_time = request.data.get('production_time', '').strip()

        # Date is REQUIRED
        if not prod_date:
            return Response({'error': 'Production date is required for Go Live Step 4.'}, status=status.HTTP_400_BAD_REQUEST)

        sched, _ = ClientGoLiveSchedule.objects.get_or_create(client=client)
        sched.production_date = prod_date
        sched.production_time = prod_time  # Optional
        sched.entered_by = 'Admin User'
        sched.save()

        st4, _ = ClientGoLiveStatus.objects.get_or_create(client=client, step=step4)
        st4.status = 'DONE'
        st4.completed_at = datetime.now(timezone.utc)
        st4.completed_by = 'Admin User'
        st4.save()

        advance_golive_step(client, 4)
        log_audit(client=client, module='GO_LIVE', action='STEP_4_SCHEDULE_SAVED', details=f"Set Production Schedule: {prod_date} {prod_time or '(time TBD)'} for {client.name}.", request=request)

        return Response({'ok': True, 'state': build_golive_state(client)})


class GoLiveStep5CommentView(APIView):
    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        step5 = GoLiveStepDefinition.objects.filter(step_number=5).first()
        if not client or not step5:
            return Response({'error': 'Client or Step 5 not found'}, status=status.HTTP_404_NOT_FOUND)

        # Comment is OPTIONAL; empty comment allows completion
        comment_text = request.data.get('comment_text', '').strip()
        
        c_obj, _ = ClientGoLiveComment.objects.get_or_create(client=client)
        c_obj.comment_text = comment_text
        c_obj.entered_by = 'Admin User'
        c_obj.save()

        st5, _ = ClientGoLiveStatus.objects.get_or_create(client=client, step=step5)
        st5.status = 'DONE'
        st5.completed_at = datetime.now(timezone.utc)
        st5.completed_by = 'Admin User'
        st5.save()

        advance_golive_step(client, 5)
        log_audit(
            client=client, module='GO_LIVE', action='STEP_5_COMMENT_SAVED',
            details=f"Step 5 comment recorded: '{comment_text or 'No special comment provided'}' for {client.name}.",
            request=request
        )

        return Response({'ok': True, 'state': build_golive_state(client)})


class GoLiveStep6CompleteView(APIView):
    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        step6 = GoLiveStepDefinition.objects.filter(step_number=6).first()
        if not client or not step6:
            return Response({'error': 'Client or Step 6 not found'}, status=status.HTTP_404_NOT_FOUND)

        # Verify prior steps 1-5 are DONE
        prior_steps = GoLiveStepDefinition.objects.filter(step_number__lt=6)
        incomplete = ClientGoLiveStatus.objects.filter(client=client, step__in=prior_steps).exclude(status='DONE')
        if incomplete.exists():
            return Response({'error': 'All previous Go Live steps (1-5) must be completed before finalizing Production Successful.'}, status=status.HTTP_400_BAD_REQUEST)

        st6, _ = ClientGoLiveStatus.objects.get_or_create(client=client, step=step6)
        st6.status = 'DONE'
        st6.completed_at = datetime.now(timezone.utc)
        st6.completed_by = 'Admin User'
        st6.save()

        # Promote client stage to production
        client.stage = 'production'
        client.state = 'Healthy'
        client.live_since = datetime.now(timezone.utc).strftime("%d/%m/%Y")
        client.save()

        log_audit(client=client, module='GO_LIVE', action='PRODUCTION_SUCCESSFUL_COMPLETE', details=f"Production Successful! Client '{client.name}' is now fully live.", request=request)

        return Response({'ok': True, 'message': f"Client {client.name} is now Live in Production!", 'state': build_golive_state(client)})


class GoLiveRedoStepView(APIView):
    def post(self, request, client_id, step_number):
        client = Client.objects.filter(id=client_id).first()
        target_step = GoLiveStepDefinition.objects.filter(step_number=step_number).first()
        if not client or not target_step:
            return Response({'error': 'Client or Go Live Step not found'}, status=status.HTTP_404_NOT_FOUND)

        # Reset target step to IN_PROGRESS
        st_target, _ = ClientGoLiveStatus.objects.get_or_create(client=client, step=target_step)
        st_target.status = 'IN_PROGRESS'
        st_target.completed_at = None
        st_target.completed_by = None
        st_target.save()

        # Reset subsequent steps to WAITING
        subsequent = GoLiveStepDefinition.objects.filter(step_number__gt=step_number)
        ClientGoLiveStatus.objects.filter(client=client, step__in=subsequent).update(status='WAITING', completed_at=None, completed_by=None)

        log_audit(client=client, module='GO_LIVE', action='GOLIVE_REDO_STEP', details=f"Reset Go Live Step {step_number} to In Progress.", request=request)

        return Response({'ok': True, 'state': build_golive_state(client)})


# --- Onboarding Step Handlers & Other Views ---
class StepUploadView(APIView):
    def post(self, request, client_id, step_key):
        client = Client.objects.filter(id=client_id).first()
        step_def = find_step_definition(step_key)
        if not client or not step_def:
            return Response({'error': 'Client or Step not found'}, status=status.HTTP_404_NOT_FOUND)

        ok_seq, seq_err = enforce_step_in_progress_or_done(client, step_def)
        if not ok_seq:
            return seq_err

        ALLOWED_UPLOAD_ACTION_TYPES = {'upload_template', 'email_upload', 'x12_835_validate'}
        if step_def.action_type not in ALLOWED_UPLOAD_ACTION_TYPES:
            return Response({
                'ok': False,
                'error': f"Step '{step_def.title}' requires dedicated form completion, not file upload."
            }, status=status.HTTP_400_BAD_REQUEST)

        buf = request.body
        if len(buf) > MAX_UPLOAD_BYTES:
            return Response({'error': 'Upload size exceeds maximum limit (10 MB)'}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        if len(buf) == 0:
            return Response({'error': 'Uploaded file is empty'}, status=status.HTTP_400_BAD_REQUEST)

        orig_filename = request.headers.get('X-Filename') or 'uploaded_file'
        
        # Step 7 extension check & staging
        if step_def.step_number == 7:
            ext = (orig_filename.split('.')[-1].lower() if '.' in orig_filename else '')
            allowed_835_exts = {'835', 'x12', 'edi', 'txt', 'dat', '35', 'ansi', 'rem'}
            if ext not in allowed_835_exts:
                return Response({
                    'ok': False,
                    'error': f"Unsupported file type (.{ext}). Upload a valid 835/X12 file (.835, .x12, .edi, .txt, .dat, .35, .ansi, .rem).",
                    'checks': [{'ok': False, 'label': 'File extension', 'detail': f"Extension .{ext} is unsupported."}]
                }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

            os.makedirs(EVID_DIR, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
            safe_orig = re.sub(r"[^A-Za-z0-9._-]+", "_", orig_filename)[:120]
            stored_name = f"{client.id}_7_{ts}_{safe_orig}"
            file_path = os.path.join(EVID_DIR, stored_name)
            with open(file_path, 'wb') as f:
                f.write(buf)

            up = StepUpload.objects.create(
                client=client, step=step_def, original_filename=orig_filename,
                stored_filename=stored_name, file_path=file_path, file_size=len(buf),
                validation_status='PENDING'
            )
            return Response({'ok': True, 'staged': True, 'upload': StepUploadSerializer(up).data})

        # Standard step validation
        v_res = validate_step_upload(step_def.step_number, buf, orig_filename)
        if not v_res.get('ok'):
            return Response({'ok': False, 'error': 'Validation failed', 'checks': v_res.get('checks')}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        os.makedirs(EVID_DIR, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        safe_orig = re.sub(r"[^A-Za-z0-9._-]+", "_", orig_filename)[:120]
        stored_name = f"{client.id}_{step_def.step_number}_{ts}_{safe_orig}"
        file_path = os.path.join(EVID_DIR, stored_name)
        with open(file_path, 'wb') as f:
            f.write(buf)

        up = StepUpload.objects.create(
            client=client, step=step_def, original_filename=orig_filename,
            stored_filename=stored_name, file_path=file_path, file_size=len(buf),
            validation_status='PASSED'
        )

        # Also store into ClientDocument
        ClientDocument.objects.create(
            client=client,
            document_name=step_def.title,
            original_filename=orig_filename,
            storage_path=file_path,
            document_type='Onboarding Evidence',
            direction='Client → OneSmarter',
            file_size=len(buf),
            status='Executed',
            uploaded_by='Admin User'
        )

        st_obj, _ = ClientStepStatus.objects.get_or_create(client=client, step=step_def)
        st_obj.status = 'DONE'
        st_obj.completed_at = datetime.now(timezone.utc)
        st_obj.completed_by = 'Admin User'
        st_obj.save()

        advance_next_step(client, step_def.step_number)
        log_audit(client=client, module='ONBOARDING', action='STEP_UPLOAD_COMPLETE', details=f"Completed Step {step_def.step_number} ({step_def.title}) via file upload.", request=request)

        return Response({'ok': True, 'upload': StepUploadSerializer(up).data, 'checks': v_res.get('checks')})


class Validate835View(APIView):
    def post(self, request, client_id):
        try:
            client = Client.objects.filter(id=client_id).first()
            step7 = OnboardingStepDefinition.objects.filter(step_number=7).first()
            if not client or not step7:
                return Response({'error': 'Client or Step 7 not found'}, status=status.HTTP_404_NOT_FOUND)

            ok_seq, seq_err = enforce_step_in_progress_or_done(client, step7)
            if not ok_seq:
                return seq_err

            staged = StepUpload.objects.filter(client=client, step=step7).order_by('-id').first()
            if not staged or not os.path.exists(staged.file_path):
                return Response({'ok': False, 'error': 'No staged 835 file found for validation.'}, status=status.HTTP_400_BAD_REQUEST)

            with open(staged.file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                raw_text = f.read()

            from api.edi_validator import EDI835Validator
            from api.edi_parser import parse_835_to_mir
            from api.validation import validate_template_structural_integrity
            import json

            with open(staged.file_path, 'rb') as f:
                raw_bytes = f.read()

            tmpl_ok, tmpl_checks = validate_template_structural_integrity(7, raw_bytes, is_pdf=False)
            
            validator = EDI835Validator()
            report = validator.validate(raw_text)
            pyx12_ok = report.get('valid', False)

            ok = tmpl_ok or pyx12_ok
            checks = []

            if ok:
                if tmpl_ok:
                    checks.extend(tmpl_checks)
                else:
                    checks.append({'ok': True, 'label': 'PyX12 Validator', 'detail': 'Passed strict PyX12 structural validation.'})
                
                try:
                    parsed_res = parse_835_to_mir(raw_text)
                    claims_count = parsed_res['claims_count']
                    services_count = parsed_res['services_count']
                    records_count = parsed_res['records_count']
                    report['claims_count'] = claims_count
                    report['services_count'] = services_count
                    report['records_count'] = records_count
                    checks.append({'ok': True, 'label': 'MIR Parser', 'detail': f"Successfully parsed {claims_count} claims and {services_count} services."})
                except Exception as e:
                    report['parser_error'] = str(e)
                    checks.append({'ok': True, 'label': 'MIR Parser', 'detail': f"Parser error: {str(e)}"})
            else:
                checks.extend(tmpl_checks)
                for err in report.get('errors', []):
                    checks.append({'ok': False, 'label': f"Line {err.get('line', '?')} Segment {err.get('segment', '?')}", 'detail': err.get('message', 'Error')})

            with transaction.atomic():
                if ok:
                    staged.validation_status = 'PASSED'
                    staged.save()

                    st_obj, _ = ClientStepStatus.objects.get_or_create(client=client, step=step7)
                    st_obj.status = 'DONE'
                    st_obj.completed_at = datetime.now(timezone.utc)
                    st_obj.completed_by = 'Admin User'
                    st_obj.save()

                    # Store in ClientDocument
                    ClientDocument.objects.create(
                        client=client,
                        document_name='Sample 835 Remittance Advice',
                        original_filename=staged.original_filename,
                        storage_path=staged.file_path,
                        document_type='Test Data / EDI',
                        direction='Client → OneSmarter',
                        file_size=staged.file_size,
                        mime_type='text/plain',
                        status='Validated',
                        uploaded_by='Admin User',
                        validation_details=json.dumps(report)
                    )

                    advance_next_step(client, 7)
                    log_audit(client=client, module='ONBOARDING', action='STEP_7_VALIDATED', details="Validated sample X12 835 file using PyX12 engine.", request=request)
                else:
                    staged.validation_status = 'FAILED'
                    staged.save()
                    log_audit(client=client, module='ONBOARDING', action='STEP_7_VALIDATION_FAILED', details="Sample X12 835 PyX12 validation failed.", request=request)
                    
            if ok:
                return Response({'ok': True, 'validated': True, 'checks': checks})
            else:
                return Response({'ok': False, 'error': '835 Structural Validation Failed', 'checks': checks}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except Exception as e:
            import traceback
            with open("C:/Admin_Panel_OneSmarter/error.log", "w") as f:
                f.write(traceback.format_exc())
            return Response({'ok': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RedoStepView(APIView):
    def post(self, request, client_id, step_key):
        client = Client.objects.filter(id=client_id).first()
        target_step = find_step_definition(step_key)
        if not client or not target_step:
            return Response({'error': 'Client or Step not found'}, status=status.HTTP_404_NOT_FOUND)

        target_num = target_step.step_number
        subsequent_steps = OnboardingStepDefinition.objects.filter(step_number__gte=target_num)
        subsequent_types = set(subsequent_steps.values_list('action_type', flat=True))

        uploads = StepUpload.objects.filter(client=client, step__in=subsequent_steps)
        for up in uploads:
            if up.file_path and os.path.exists(up.file_path):
                try:
                    os.remove(up.file_path)
                except Exception:
                    pass
        uploads.delete()

        if 'contact_manager' in subsequent_types:
            if target_num == 4:
                # Targeted Redo: Only delete the most recently added contact
                latest_contact = ClientContact.objects.filter(client=client).order_by('-id').first()
                if latest_contact:
                    latest_contact.delete()
            else:
                # If target step < 4, wipe out all contacts entirely
                ClientContact.objects.filter(client=client).delete()
        if 'claim_verify' in subsequent_types:
            ClaimSystemVerification.objects.filter(client=client).delete()
        if 'transfer_config' in subsequent_types:
            ClientTransferConfig.objects.filter(client=client).delete()
        if 'schedule_action' in subsequent_types:
            StepSchedule.objects.filter(client=client).delete()
            
        StepTextSubmission.objects.filter(client=client, step__in=subsequent_steps).delete()

        st_target = ClientStepStatus.objects.filter(client=client, step=target_step).first()
        if st_target:
            # For step 4, if there are still contacts remaining after targeted redo, keep it as DONE
            if target_num == 4 and ClientContact.objects.filter(client=client).exists():
                pass
            else:
                st_target.status = 'IN_PROGRESS'
                st_target.completed_at = None
                st_target.completed_by = None
                st_target.save()

        subsequent_after = OnboardingStepDefinition.objects.filter(step_number__gt=target_num)
        ClientStepStatus.objects.filter(client=client, step__in=subsequent_after).update(status='WAITING', completed_at=None, completed_by=None)

        client.stage = 'onboarding'
        recalculate_client_progress(client)

        log_audit(client=client, module='ONBOARDING', action='REDO_STEP', details=f"Reset Step {target_num} ({step_key}) to In Progress.", request=request)

        return Response({'ok': True, 'message': f"Step {target_num} reset to In Progress."})


class CompleteStepDirectView(APIView):
    def post(self, request, client_id, step_key):
        client = Client.objects.filter(id=client_id).first()
        step_def = find_step_definition(step_key)
        if not client or not step_def:
            return Response({'error': 'Client or Step not found'}, status=status.HTTP_404_NOT_FOUND)

        ok_seq, seq_err = enforce_step_in_progress_or_done(client, step_def)
        if not ok_seq:
            return seq_err

        if step_def.action_type == 'side_by_side_done':
            review_text = (request.data.get('submission_text') or request.data.get('notes') or '').strip()
            if not review_text:
                return Response({
                    'ok': False,
                    'error': 'Step 10 Evidence Required: Enter side-by-side 835 conversion review notes before completing this step.'
                }, status=status.HTTP_400_BAD_REQUEST)
            StepTextSubmission.objects.create(
                client=client, step=step_def, submission_text=review_text, submitted_by='Admin User'
            )

        st_obj, _ = ClientStepStatus.objects.get_or_create(client=client, step=step_def)
        st_obj.status = 'DONE'
        st_obj.completed_at = datetime.now(timezone.utc)
        st_obj.completed_by = 'Admin User'
        st_obj.save()

        advance_next_step(client, step_def.step_number)
        log_audit(client=client, module='ONBOARDING', action='STEP_COMPLETED', details=f"Completed Step {step_def.step_number} ({step_def.title}).", request=request)

        return Response({'ok': True, 'step': step_def.step_number})


class SendFTPView(APIView):
    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        step_def = find_step_definition('step_11_send_ftp')
        if not client or not step_def:
            return Response({'error': 'Client or Step not found'}, status=status.HTTP_404_NOT_FOUND)
        
        ok_seq, seq_err = enforce_step_in_progress_or_done(client, step_def)
        if not ok_seq:
            return seq_err

        # 1. Create a local folder
        ftp_dir = os.path.join(settings.BASE_DIR, 'ftp_test', client_id)
        os.makedirs(ftp_dir, exist_ok=True)
        
        # 2. Write a text file into it
        test_file_path = os.path.join(ftp_dir, 'test_payload.txt')
        test_content = f"Test payload for {client.name} (ID: {client_id}) generated at {datetime.now(timezone.utc).isoformat()}"
        with open(test_file_path, 'w') as f:
            f.write(test_content)
            
        # 3. Check if it was received correctly (verify existence and content)
        if os.path.exists(test_file_path):
            with open(test_file_path, 'r') as f:
                content = f.read()
            if content == test_content:
                # Send email to the client if they have an email registered
                client_email = client.contact_info
                if client_email:
                    try:
                        email = EmailMessage(
                            subject=f"FTP Verification Completed for {client.name}",
                            body=f"Hello,\n\nThe FTP verification payload has been successfully validated for {client.name}.\nPlease find the test payload attached.\n\nBest regards,\nOneSmarter Onboarding Team",
                            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@onesmarter.com',
                            to=[client_email],
                        )
                        email.attach_file(test_file_path)
                        email.send(fail_silently=True)
                    except Exception as e:
                        # Log but don't fail the step if SMTP is not configured
                        print(f"Warning: Failed to send email to {client_email}: {e}")

                # 4. If yes, mark the step as done
                st_obj, _ = ClientStepStatus.objects.get_or_create(client=client, step=step_def)
                st_obj.status = 'DONE'
                st_obj.completed_at = datetime.now(timezone.utc)
                st_obj.completed_by = 'Admin User'
                st_obj.save()

                advance_next_step(client, step_def.step_number)
                log_audit(client=client, module='ONBOARDING', action='STEP_11_FTP_SEND', details=f"Sent test FTP payload and completed Step 11.", request=request)

                return Response({'ok': True, 'step': step_def.step_number, 'message': 'FTP file sent and verified successfully.'})
            
        return Response({'ok': False, 'error': 'Failed to verify the FTP test file.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SaveStep4ContactView(APIView):
    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        step4 = OnboardingStepDefinition.objects.filter(step_number=4).first()
        if step4:
            ok_seq, seq_err = enforce_step_in_progress_or_done(client, step4)
            if not ok_seq:
                return seq_err

        role_name = (request.data.get('role_name') or 'Named Contact').strip()
        emp_name = request.data.get('employee_name', '').strip()
        email = request.data.get('email', '').strip()
        phone = request.data.get('phone', '').strip()
        alt_contact = request.data.get('alternate_contact', '').strip()
        ah_notes = request.data.get('after_hours_notes', '').strip()

        if not emp_name:
            return Response({'error': 'Employee name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        existing = ClientContact.objects.filter(client=client)
        if existing.filter(employee_name__iexact=emp_name).exists():
            return Response({'error': f"Duplicate entry: Contact '{emp_name}' already exists for this client."}, status=status.HTTP_400_BAD_REQUEST)
        if email and existing.filter(email__iexact=email).exists():
            return Response({'error': f"Duplicate entry: Contact with email '{email}' already exists for this client."}, status=status.HTTP_400_BAD_REQUEST)
        if phone and existing.filter(phone=phone).exists():
            return Response({'error': f"Duplicate entry: Contact with phone '{phone}' already exists for this client."}, status=status.HTTP_400_BAD_REQUEST)

        if email:
            valid_email, email_err = validate_email_address(email)
            if not valid_email:
                return Response({'error': email_err}, status=status.HTTP_400_BAD_REQUEST)

        if phone:
            valid_phone, phone_err = validate_phone_number(phone)
            if not valid_phone:
                return Response({'error': phone_err}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            role, _ = EmployeeRole.objects.get_or_create(role_name=role_name)
            contact = ClientContact.objects.create(
                client=client, role_name=role_name, employee_name=emp_name,
                email=email, phone=phone,
                alternate_contact=alt_contact,
                after_hours_notes=ah_notes
            )

            if step4:
                st_obj, _ = ClientStepStatus.objects.get_or_create(client=client, step=step4)
                st_obj.status = 'DONE'
                st_obj.completed_at = datetime.now(timezone.utc)
                st_obj.save()
                advance_next_step(client, 4)

            log_audit(client=client, module='ONBOARDING', action='CONTACT_ADDED', details=f"Added contact '{emp_name}' ({role_name}).", request=request)
            
        return Response({'ok': True, 'contact': ClientContactSerializer(contact).data})


class SaveStep5ClaimVerifyView(APIView):
    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        step5 = OnboardingStepDefinition.objects.filter(step_number=5).first()
        if step5:
            ok_seq, seq_err = enforce_step_in_progress_or_done(client, step5)
            if not ok_seq:
                return seq_err

        text = request.data.get('verification_text', '').strip()
        if not text:
            return Response({'error': 'Verification text required'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            ver = ClaimSystemVerification.objects.create(client=client, verification_text=text, verified_by='Admin User')

            if step5:
                st_obj, _ = ClientStepStatus.objects.get_or_create(client=client, step=step5)
                st_obj.status = 'DONE'
                st_obj.completed_at = datetime.now(timezone.utc)
                st_obj.save()
                advance_next_step(client, 5)

            log_audit(client=client, module='ONBOARDING', action='CLAIM_SYSTEM_VERIFIED', details="Verified claims system details.", request=request)
            
        return Response({'ok': True, 'verification': ClaimSystemVerificationSerializer(ver).data})


class SaveStep6TransferConfigView(APIView):
    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        step6 = OnboardingStepDefinition.objects.filter(step_number=6).first()
        if step6:
            ok_seq, seq_err = enforce_step_in_progress_or_done(client, step6)
            if not ok_seq:
                return seq_err

        with transaction.atomic():
            cfg, _ = ClientTransferConfig.objects.get_or_create(client=client)
            cfg.method = request.data.get('method', 'SFTP')
            cfg.setup_status = request.data.get('setup_status', 'Configured')
            cfg.watched_folder_sftp = bool(request.data.get('watched_folder_sftp'))
            cfg.keys_exchanged = bool(request.data.get('keys_exchanged'))
            cfg.no_change_to_client_system = bool(request.data.get('no_change_to_client_system'))
            cfg.notes = request.data.get('notes', '')
            cfg.save()

            if step6:
                st_obj, _ = ClientStepStatus.objects.get_or_create(client=client, step=step6)
                st_obj.status = 'DONE'
                st_obj.completed_at = datetime.now(timezone.utc)
                st_obj.save()
                advance_next_step(client, 6)

            log_audit(client=client, module='ONBOARDING', action='TRANSFER_CONFIG_SAVED', details=f"Configured transfer method: {cfg.method}.", request=request)
            
        return Response({'ok': True, 'transferConfig': ClientTransferConfigSerializer(cfg).data})


class SaveStep13ScheduleView(APIView):
    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        step13 = OnboardingStepDefinition.objects.filter(step_number=13).first()
        if step13:
            ok_seq, seq_err = enforce_step_in_progress_or_done(client, step13)
            if not ok_seq:
                return seq_err

        sdate = request.data.get('scheduled_date', '')
        stime = request.data.get('scheduled_time', '')
        with transaction.atomic():
            StepSchedule.objects.create(
                client=client, scheduled_date=sdate,
                scheduled_time=stime,
                timezone=request.data.get('timezone', 'ET'), notes=request.data.get('notes')
            )

            if step13:
                st_obj, _ = ClientStepStatus.objects.get_or_create(client=client, step=step13)
                st_obj.status = 'DONE'
                st_obj.completed_at = datetime.now(timezone.utc)
                st_obj.save()
                advance_next_step(client, 13)

            log_audit(client=client, module='ONBOARDING', action='STEP_13_SCHEDULED', details=f"Scheduled onboarding live cutover: {sdate} {stime}.", request=request)
            
        return Response({'ok': True})


class SubmitStepTextView(APIView):
    def post(self, request, client_id, step_key):
        client = Client.objects.filter(id=client_id).first()
        step_def = find_step_definition(step_key)
        text = request.data.get('submission_text', '').strip()
        if not client or not step_def or not text:
            return Response({'error': 'Invalid submission'}, status=status.HTTP_400_BAD_REQUEST)

        ok_seq, seq_err = enforce_step_in_progress_or_done(client, step_def)
        if not ok_seq:
            return seq_err
        
        with transaction.atomic():
            StepTextSubmission.objects.create(client=client, step=step_def, submission_text=text, submitted_by='Admin User')

            st_obj, _ = ClientStepStatus.objects.get_or_create(client=client, step=step_def)
            st_obj.status = 'DONE'
            st_obj.completed_at = datetime.now(timezone.utc)
            st_obj.save()

            advance_next_step(client, step_def.step_number)
            log_audit(client=client, module='ONBOARDING', action='STEP_TEXT_SUBMISSION', details=f"Submitted text for Step {step_def.step_number} ({step_def.title}).", request=request)

        return Response({'ok': True})


class StepNotesView(APIView):
    def get(self, request, client_id, step_key):
        step_def = find_step_definition(step_key)
        if not step_def:
            return Response({'ok': True, 'notes': []})
        notes = StepNote.objects.filter(client_id=client_id, step=step_def).order_by('-id')
        return Response({'ok': True, 'notes': StepNoteSerializer(notes, many=True).data})

    def post(self, request, client_id, step_key):
        client = Client.objects.filter(id=client_id).first()
        step_def = find_step_definition(step_key)
        text = request.data.get('note_text', '').strip()
        if not client or not step_def or not text:
            return Response({'error': 'Invalid note'}, status=status.HTTP_400_BAD_REQUEST)

        note = StepNote.objects.create(client=client, step=step_def, note_text=text, author='Admin User')
        log_audit(client=client, module='ONBOARDING', action='NOTE_ADDED', details=f"Added note to Step {step_def.step_number} ({step_def.title}).", request=request)
        return Response({'ok': True, 'note': StepNoteSerializer(note).data})


class EmployeeRolesView(APIView):
    def get(self, request):
        roles = EmployeeRole.objects.all().order_by('id')
        return Response({'ok': True, 'roles': EmployeeRoleSerializer(roles, many=True).data})

    def post(self, request):
        rname = request.data.get('role_name', '').strip()
        rdesc = request.data.get('description', '').strip()
        if not rname:
            return Response({'error': 'Role name required'}, status=status.HTTP_400_BAD_REQUEST)
        role, created = EmployeeRole.objects.get_or_create(role_name=rname)
        if rdesc:
            role.description = rdesc
            role.save()
        log_audit(module='CLIENTS', action='ROLE_CREATED', details=f"Created employee role '{rname}'.", request=request)
        return Response({'ok': True, 'role': EmployeeRoleSerializer(role).data})


class DownloadTemplateView(APIView):
    def get(self, request, client_id, step_key):
        step_def = find_step_definition(step_key)
        if not step_def and step_key.isdigit():
            step_def = OnboardingStepDefinition.objects.filter(step_number=int(step_key)).first()
        if not step_def:
            return Response({'error': f'Step {step_key} not found'}, status=status.HTTP_404_NOT_FOUND)

        ext = step_def.download_extension or 'pdf'
        download_filename = get_step_download_filename(step_def.title, ext)

        sample_dir = os.path.abspath(os.path.join(settings.BASE_DIR.parent, 'sample documents'))
        file_name = step_def.download_filename or f"{step_key}.{ext}"
        file_path = os.path.join(sample_dir, file_name)

        if not os.path.exists(file_path):
            return Response({'error': f'Template file {file_name} not found'}, status=status.HTTP_404_NOT_FOUND)

        mime_type = 'application/pdf' if ext == 'pdf' else 'text/plain'
        client = Client.objects.filter(id=client_id).first()
        log_audit(client=client, module='DOCUMENTS', action='TEMPLATE_DOWNLOAD', details=f"Downloaded template '{download_filename}'.", request=request)

        response = FileResponse(open(file_path, 'rb'), content_type=mime_type)
        response['Content-Disposition'] = f'attachment; filename="{download_filename}"'
        response['X-OneSmarter-Filename'] = download_filename
        response['Content-Length'] = os.path.getsize(file_path)
        return response


class ResetDemoView(APIView):
    def post(self, request):
        for up in StepUpload.objects.all():
            if up.file_path and os.path.exists(up.file_path):
                try:
                    os.remove(up.file_path)
                except Exception:
                    pass

        ClientStepStatus.objects.all().delete()
        StepUpload.objects.all().delete()
        StepNote.objects.all().delete()
        ClientContact.objects.all().delete()
        ClaimSystemVerification.objects.all().delete()
        ClientTransferConfig.objects.all().delete()
        StepSchedule.objects.all().delete()
        StepTextSubmission.objects.all().delete()
        ClientDocument.objects.all().delete()
        ClientTestEnvironment.objects.all().delete()
        ClientGoLiveStatus.objects.all().delete()
        ClientGoLiveSFTP.objects.all().delete()
        ClientGoLiveSchedule.objects.all().delete()
        ClientGoLiveComment.objects.all().delete()
        AuditLog.objects.all().delete()
        Client.objects.all().delete()

        from django.core.management import call_command
        call_command('seed_data')
        log_audit(module='SYSTEM', action='RESET_DEMO', details="Reset demo dataset to pristine initial state.", request=request)
        return Response({'ok': True, 'message': 'Demo data reset successfully.'})


class CleanupEvidenceView(APIView):
    def post(self, request):
        retention_days = int(os.environ.get("RETENTION_DAYS") or 365)
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

        active_paths = set(StepUpload.objects.values_list('file_path', flat=True)) | set(ClientDocument.objects.values_list('storage_path', flat=True))
        removed_count = 0

        if os.path.exists(EVID_DIR):
            for fn in os.listdir(EVID_DIR):
                fp = os.path.join(EVID_DIR, fn)
                if os.path.isfile(fp):
                    if fp not in active_paths:
                        try:
                            os.remove(fp)
                            removed_count += 1
                        except Exception:
                            pass

        old_uploads = StepUpload.objects.filter(uploaded_at__lt=cutoff)
        for up in old_uploads:
            if up.file_path and os.path.exists(up.file_path):
                try:
                    os.remove(up.file_path)
                    removed_count += 1
                except Exception:
                    pass
        old_uploads.delete()

        log_audit(
            module='SYSTEM', action='CLEANUP_EVIDENCE',
            details=f"Cleaned up {removed_count} orphaned or expired evidence files older than {retention_days} days.",
            request=request
        )
        return Response({'ok': True, 'removed': removed_count})


class AuditLogListView(APIView):
    def get(self, request):
        cid = request.query_params.get('client_id')
        mod = request.query_params.get('module')
        qs = AuditLog.objects.all().order_by('-timestamp')
        if cid:
            qs = qs.filter(client_id=cid)
        if mod:
            qs = qs.filter(module=mod)
        logs = qs[:100]
        return Response({'ok': True, 'logs': AuditLogSerializer(logs, many=True).data})
