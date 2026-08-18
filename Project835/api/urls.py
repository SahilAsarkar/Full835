from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ClientViewSet, StepUploadView, Validate835View, RedoStepView, CompleteStepDirectView,
    SendFTPView,
    SaveStep4ContactView, SaveStep5ClaimVerifyView, SaveStep6TransferConfigView,
    SaveStep13ScheduleView, SubmitStepTextView, StepNotesView, EmployeeRolesView,
    DownloadTemplateView, ResetDemoView, CleanupEvidenceView, AuditLogListView,
    AuthLoginView, AuthLogoutView, AccessInfoView, AuthRegisterView,
    ClientDocumentsListView, ClientDocumentUploadView, DocumentDownloadView, DocumentDeleteView,
    ClientTestEnvironmentView, ClientTestRunView,
    GoLiveStateView, GoLiveStep1UploadView, GoLiveStep1DownloadView,
    GoLiveStep2UploadView, GoLiveStep2DownloadView, GoLiveStep3SFTPView,
    GoLiveStep4ScheduleView, GoLiveStep5CommentView, GoLiveStep6CompleteView, GoLiveRedoStepView
)

router = DefaultRouter()
router.register(r'clients', ClientViewSet, basename='client')

urlpatterns = [
    path('', include(router.urls)),
    
    # Authentication & Access Matrix
    path('auth/login', AuthLoginView.as_view(), name='auth-login'),
    path('auth/login/', AuthLoginView.as_view(), name='auth-login-slash'),
    path('auth/register', AuthRegisterView.as_view(), name='auth-register'),
    path('auth/register/', AuthRegisterView.as_view(), name='auth-register-slash'),
    path('auth/logout', AuthLogoutView.as_view(), name='auth-logout'),
    path('auth/logout/', AuthLogoutView.as_view(), name='auth-logout-slash'),
    path('access/info', AccessInfoView.as_view(), name='access-info'),
    path('access/info/', AccessInfoView.as_view(), name='access-info-slash'),
    
    # Documents Section API
    path('clients/<str:client_id>/documents', ClientDocumentsListView.as_view(), name='client-docs-list'),
    path('clients/<str:client_id>/documents/', ClientDocumentsListView.as_view(), name='client-docs-list-slash'),
    path('clients/<str:client_id>/documents/upload', ClientDocumentUploadView.as_view(), name='client-docs-upload'),
    path('clients/<str:client_id>/documents/upload/', ClientDocumentUploadView.as_view(), name='client-docs-upload-slash'),
    path('documents/<int:doc_id>/download', DocumentDownloadView.as_view(), name='doc-download'),
    path('documents/<int:doc_id>/download/', DocumentDownloadView.as_view(), name='doc-download-slash'),
    path('documents/<int:doc_id>', DocumentDeleteView.as_view(), name='doc-delete'),
    path('documents/<int:doc_id>/', DocumentDeleteView.as_view(), name='doc-delete-slash'),
    
    # Test Environment Section API
    path('clients/<str:client_id>/test-environment', ClientTestEnvironmentView.as_view(), name='client-test-env'),
    path('clients/<str:client_id>/test-environment/', ClientTestEnvironmentView.as_view(), name='client-test-env-slash'),
    path('clients/<str:client_id>/test-environment/run-test', ClientTestRunView.as_view(), name='client-test-run'),
    path('clients/<str:client_id>/test-environment/run-test/', ClientTestRunView.as_view(), name='client-test-run-slash'),
    
    # Go Live 6-Step Workflow API
    path('clients/<str:client_id>/golive/state', GoLiveStateView.as_view(), name='golive-state'),
    path('clients/<str:client_id>/golive/state/', GoLiveStateView.as_view(), name='golive-state-slash'),
    path('clients/<str:client_id>/golive/steps/1/upload', GoLiveStep1UploadView.as_view(), name='golive-step1-upload'),
    path('clients/<str:client_id>/golive/steps/1/download', GoLiveStep1DownloadView.as_view(), name='golive-step1-download'),
    path('clients/<str:client_id>/golive/steps/2/upload', GoLiveStep2UploadView.as_view(), name='golive-step2-upload'),
    path('clients/<str:client_id>/golive/steps/2/download', GoLiveStep2DownloadView.as_view(), name='golive-step2-download'),
    path('clients/<str:client_id>/golive/steps/3/sftp', GoLiveStep3SFTPView.as_view(), name='golive-step3-sftp'),
    path('clients/<str:client_id>/golive/steps/4/schedule', GoLiveStep4ScheduleView.as_view(), name='golive-step4-schedule'),
    path('clients/<str:client_id>/golive/steps/5/comment', GoLiveStep5CommentView.as_view(), name='golive-step5-comment'),
    path('clients/<str:client_id>/golive/steps/6/complete', GoLiveStep6CompleteView.as_view(), name='golive-step6-complete'),
    path('clients/<str:client_id>/golive/steps/<int:step_number>/redo', GoLiveRedoStepView.as_view(), name='golive-step-redo'),
    
    # Downloads & Demo Reset & Cleanup & Audit
    path('download/<str:client_id>/<str:step_key>', DownloadTemplateView.as_view(), name='download-template'),
    path('reset-demo', ResetDemoView.as_view(), name='reset-demo'),
    path('cleanup', CleanupEvidenceView.as_view(), name='cleanup-evidence'),
    path('audit-logs', AuditLogListView.as_view(), name='audit-logs'),
    path('audit-logs/', AuditLogListView.as_view(), name='audit-logs-slash'),
    
    # Step-specific actions
    path('clients/<str:client_id>/steps/<str:step_key>/upload', StepUploadView.as_view(), name='step-upload'),
    path('clients/<str:client_id>/steps/step_7_835_val/validate-uploaded', Validate835View.as_view(), name='validate-835'),
    path('clients/<str:client_id>/steps/<str:step_key>/redo', RedoStepView.as_view(), name='redo-step'),
    path('clients/<str:client_id>/onboarding/steps/<str:step_key>/complete', CompleteStepDirectView.as_view(), name='complete-step'),
    
    path('clients/<str:client_id>/steps/step_4_contacts/save', SaveStep4ContactView.as_view(), name='save-step4'),
    path('clients/<str:client_id>/steps/step_5_claim_sys/save', SaveStep5ClaimVerifyView.as_view(), name='save-step5'),
    path('clients/<str:client_id>/steps/step_6_transfer_method/save', SaveStep6TransferConfigView.as_view(), name='save-step6'),
    path('clients/<str:client_id>/steps/step_11_send_ftp/send', SendFTPView.as_view(), name='send-ftp-step11'),
    path('clients/<str:client_id>/steps/step_13_schedule/save', SaveStep13ScheduleView.as_view(), name='save-step13'),
    path('clients/<str:client_id>/steps/<str:step_key>/submit-text', SubmitStepTextView.as_view(), name='submit-step-text'),
    
    # Notes & Roles
    path('clients/<str:client_id>/steps/<str:step_key>/notes', StepNotesView.as_view(), name='step-notes'),
    path('employee-roles', EmployeeRolesView.as_view(), name='employee-roles'),
    path('employee-roles/', EmployeeRolesView.as_view(), name='employee-roles-slash'),
]
