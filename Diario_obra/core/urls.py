from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from .htmx_views import project_activities_tree, activity_children
from . import central_views
from .frontend_views import (
    login_view,
    logout_view,
    select_system_view,
    select_project_view,
    central_hub_view,
    dashboard_view,
    calendar_events_view,
    report_list_view,
    diary_detail_view,
    diary_form_view,
    diary_pdf_view,
    diary_excel_view,
    project_list_view,
    project_form_view,
    project_delete_view,
    activity_form_view,
    activity_delete_view,
    labor_list_view,
    labor_form_view,
    equipment_list_view,
    equipment_form_view,
    notifications_view,
    notification_mark_read_view,
    notification_mark_all_read_view,
    profile_view,
    analytics_view,
    filter_photos_view,
    filter_videos_view,
    filter_activities_view,
    filter_occurrences_view,
    filter_comments_view,
    filter_attachments_view,
    weather_conditions_view,
    labor_histogram_view,
    equipment_histogram_view,
    client_diary_list_view,
    client_diary_detail_view,
    client_diary_add_comment_view,
    diary_add_owner_comment_view,
)

urlpatterns = [
    # Rota raiz - página inicial = seleção de sistema (login obrigatório via select_system_view)
    path('', RedirectView.as_view(pattern_name='select-system', permanent=False), name='home'),
    # Frontend views (devem vir ANTES do router para ter prioridade)
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    # Recuperação de senha
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='core/password_reset_form.html',
        email_template_name='core/password_reset_email.html',
        subject_template_name='core/password_reset_subject.txt',
        success_url=reverse_lazy('password_reset_done'),
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='core/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='core/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete'),
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='core/password_reset_complete.html',
    ), name='password_reset_complete'),
    path('select-system/', select_system_view, name='select-system'),
    path('select-project/', select_project_view, name='select-project'),
    # Central: usuários e obras (obras = /projects/)
    path('central/', central_hub_view, name='central_hub'),
    path('central/usuarios/', central_views.central_list_users, name='central_list_users'),
    path('central/usuarios/criar/', central_views.central_create_user, name='central_create_user'),
    path('central/usuarios/<int:pk>/editar/', central_views.central_edit_user, name='central_edit_user'),
    path('central/usuarios/<int:pk>/excluir/', central_views.central_delete_user, name='central_delete_user'),
    path('central/ajuda/', central_views.central_ajuda_view, name='central_ajuda'),
    path('central/manutencao/', central_views.central_manutencao_view, name='central_manutencao'),
    path('projects/<int:project_id>/diario-emails/', central_views.central_diary_emails_view, name='central_diary_emails'),
    path('projects/<int:project_id>/diario-emails/<int:pk>/remover/', central_views.central_diary_email_remove_view, name='central_diary_email_remove'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('profile/', profile_view, name='profile'),
    path('analytics/', analytics_view, name='analytics'),
    path('calendar-events/', calendar_events_view, name='calendar-events'),
    path('reports/', report_list_view, name='report-list'),
    path('projects/', project_list_view, name='central_project_list'),  # Listagem Central (não confundir com API project-list)
    path('projects/new/', project_form_view, name='project-new'),
    path('projects/<int:pk>/edit/', project_form_view, name='project-edit'),
    path('projects/<int:pk>/delete/', project_delete_view, name='project-delete'),
    path('diaries/<int:pk>/', diary_detail_view, name='diary-detail'),
    path('diaries/<int:pk>/comentar/', diary_add_owner_comment_view, name='diary-add-owner-comment'),
    # Portal do dono da obra (cliente): visualizar diário e comentar (24h)
    path('cliente/diarios/', client_diary_list_view, name='client-diary-list'),
    path('cliente/diarios/<int:pk>/', client_diary_detail_view, name='client-diary-detail'),
    path('cliente/diarios/<int:pk>/comentar/', client_diary_add_comment_view, name='client-diary-add-comment'),
    path('diaries/<int:pk>/edit/', diary_form_view, name='diary-edit'),
    path('diaries/new/', diary_form_view, name='diary-new'),
    path('diaries/<int:pk>/pdf/', diary_pdf_view, {'pdf_type': 'normal'}, name='diary-pdf'),
    path('diaries/<int:pk>/pdf/detalhado/', diary_pdf_view, {'pdf_type': 'detailed'}, name='diary-pdf-detailed'),
    path('diaries/<int:pk>/pdf/sem-fotos/', diary_pdf_view, {'pdf_type': 'no_photos'}, name='diary-pdf-no-photos'),
    path('diaries/<int:pk>/excel/', diary_excel_view, name='diary-excel'),
    
    # HTMX views
    path('htmx/projects/<int:project_id>/activities-tree/', project_activities_tree, name='project-activities-tree'),
    path('htmx/activities/<int:activity_id>/children/', activity_children, name='activity-children'),
    
    # CRUD de Atividades EAP
    path('projects/<int:project_id>/activities/new/', activity_form_view, name='activity-new'),
    path('projects/<int:project_id>/activities/<int:pk>/edit/', activity_form_view, name='activity-edit'),
    path('projects/<int:project_id>/activities/<int:pk>/delete/', activity_delete_view, name='activity-delete'),
    path('projects/<int:project_id>/activities/new/<int:parent_id>/', activity_form_view, name='activity-new-child'),
    
    # CRUD de Mão de Obra
    path('labor/', labor_list_view, name='labor-list'),
    path('labor/new/', labor_form_view, name='labor-new'),
    path('labor/<int:pk>/edit/', labor_form_view, name='labor-edit'),
    
    # CRUD de Equipamentos
    path('equipment/', equipment_list_view, name='equipment-list'),
    path('equipment/new/', equipment_form_view, name='equipment-new'),
    path('equipment/<int:pk>/edit/', equipment_form_view, name='equipment-edit'),
    
    # Filtros de busca
    path('filters/photos/', filter_photos_view, name='filter-photos'),
    path('filters/videos/', filter_videos_view, name='filter-videos'),
    path('filters/activities/', filter_activities_view, name='filter-activities'),
    path('filters/occurrences/', filter_occurrences_view, name='filter-occurrences'),
    path('filters/comments/', filter_comments_view, name='filter-comments'),
    path('filters/attachments/', filter_attachments_view, name='filter-attachments'),
    path('filters/weather/', weather_conditions_view, name='filter-weather'),
    path('filters/labor-histogram/', labor_histogram_view, name='filter-labor-histogram'),
    path('filters/equipment-histogram/', equipment_histogram_view, name='filter-equipment-histogram'),
    
    # Notificações
    path('notifications/', notifications_view, name='notifications'),
    path('notifications/<int:pk>/read/', notification_mark_read_view, name='notification-mark-read'),
    path('notifications/mark-all-read/', notification_mark_all_read_view, name='notification-mark-all-read'),
]
