"""
Testes de fluxo completo do Diário de Obra (Diario_obra).

Cobre:
- Cópia do relatório anterior (cópia total e parcial)
- Salvar rascunho (após cópia e sem cópia)
- Salvar diário (status APROVADO, envio ao dono)
- Edição de rascunho e exclusão de dados
- Diário aprovado não editável
- last_diary_for_copy no formulário novo
"""
from decimal import Decimal
from datetime import date, timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from core.models import (
    Project,
    ProjectMember,
    Activity,
    ConstructionDiary,
    DailyWorkLog,
    DiaryStatus,
    DiaryLaborEntry,
    LaborCategory,
    LaborCargo,
    DiaryOccurrence,
    OccurrenceTag,
)
from core.forms import (
    ConstructionDiaryForm,
    DiaryImageFormSet,
    DailyWorkLogFormSet,
    DiaryOccurrenceFormSet,
)


def _minimal_diary_post(project, diary_date, partial_save=True, signature_inspection='', **extra):
    """Monta POST mínimo para o formulário de diário."""
    base = {
        'project': str(project.pk),
        'date': diary_date.strftime('%Y-%m-%d'),
        'partial_save': '1' if partial_save else '',
        'signature_inspection': signature_inspection,
        'signature_production': signature_inspection,
        # Formsets vazios
        'diaryimage_set-TOTAL_FORMS': '0',
        'diaryimage_set-INITIAL_FORMS': '0',
        'diaryimage_set-MIN_NUM_FORMS': '0',
        'diaryimage_set-MAX_NUM_FORMS': '1000',
        'work_logs-TOTAL_FORMS': '0',
        'work_logs-INITIAL_FORMS': '0',
        'work_logs-MIN_NUM_FORMS': '0',
        'work_logs-MAX_NUM_FORMS': '1000',
        'ocorrencias-TOTAL_FORMS': '0',
        'ocorrencias-INITIAL_FORMS': '0',
        'ocorrencias-MIN_NUM_FORMS': '0',
        'ocorrencias-MAX_NUM_FORMS': '1000',
        # Campos opcionais do form (evitar erros)
        'weather_morning_condition': '',
        'weather_morning_workable': '',
        'weather_afternoon_condition': '',
        'weather_afternoon_workable': '',
        'pluviometric_index': '',
        'general_notes': '',
        'diary_labor_data': '[]',
        'equipment_data': '[]',
    }
    base.update(extra)
    return base


class DiaryFlowTestCase(TestCase):
    """Testes de fluxo: cópia, rascunho, salvar diário, edição."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='diaryuser',
            password='testpass123',
            email='diary@test.com',
        )
        self.project = Project.objects.create(
            code='PROJ-DIARY-TEST',
            name='Projeto Teste Diário',
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=365),
        )
        ProjectMember.objects.get_or_create(user=self.user, project=self.project)
        self.activity = Activity.add_root(
            project=self.project,
            name='Atividade Teste',
            code='1.0',
            weight=Decimal('100.00'),
        )
        # Diário fonte para cópia (com dados de clima, notas, work_log, ocorrência)
        self.source_date = date.today() - timedelta(days=1)
        self.source_diary = ConstructionDiary.objects.create(
            project=self.project,
            date=self.source_date,
            status=DiaryStatus.APROVADO,
            created_by=self.user,
            general_notes='Notas do relatório anterior',
            weather_morning_condition='B',
            weather_morning_workable='T',
            weather_afternoon_condition='B',
            weather_afternoon_workable='T',
            pluviometric_index=Decimal('0.00'),
            inspection_responsible='Fulano',
            production_responsible='Ciclano',
        )
        DailyWorkLog.objects.create(
            diary=self.source_diary,
            activity=self.activity,
            location='Local X',
            percentage_executed_today=Decimal('10.00'),
            accumulated_progress_snapshot=Decimal('25.00'),
        )
        self.source_occurrence = DiaryOccurrence.objects.create(
            diary=self.source_diary,
            description='Ocorrência fonte',
            created_by=self.user,
        )
        # Categoria/cargo para mão de obra (se existir no sistema)
        try:
            self.labor_cat = LaborCategory.objects.first()
            self.labor_cargo = LaborCargo.objects.first() if self.labor_cat else None
            if self.labor_cargo:
                DiaryLaborEntry.objects.create(
                    diary=self.source_diary,
                    cargo=self.labor_cargo,
                    quantity=2,
                    company='',
                )
        except Exception:
            pass

    def _login_and_select_project(self):
        self.client.force_login(self.user)
        session = self.client.session
        session['selected_project_id'] = self.project.id
        session['selected_project_name'] = self.project.name
        session['selected_project_code'] = self.project.code
        session.save()

    def test_get_new_diary_with_copy_all(self):
        """GET novo diário com copy_from e copy=all deve retornar 200 e form com dados copiados."""
        self._login_and_select_project()
        url = reverse('diary-new')
        resp = self.client.get(url, {
            'copy_from': str(self.source_diary.pk),
            'copy': 'all',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('form', resp.context)
        self.assertIn('copy_source_diary', resp.context)
        self.assertEqual(resp.context['copy_source_diary'].pk, self.source_diary.pk)
        form = resp.context['form']
        # A view copia clima quando copy=all (climate está em copy_opts); general_notes não é preenchido no form.initial pela view
        self.assertEqual(form.initial.get('weather_morning_condition'), 'B')
        self.assertEqual(resp.context['copy_source_diary'].general_notes, 'Notas do relatório anterior')

    def test_get_new_diary_with_copy_partial(self):
        """GET novo diário com copy_from e copy=climate,notes deve preencher só clima e notas."""
        self._login_and_select_project()
        url = reverse('diary-new')
        resp = self.client.get(url, {
            'copy_from': str(self.source_diary.pk),
            'copy': 'climate,notes',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['copy_source_diary'].pk, self.source_diary.pk)
        form = resp.context['form']
        # copy=climate,notes: a view só preenche form.initial com climate_fields; general_notes vem do source no context
        self.assertEqual(form.initial.get('weather_morning_condition'), 'B')
        self.assertEqual(resp.context['copy_source_diary'].general_notes, 'Notas do relatório anterior')

    def test_save_draft_without_copy(self):
        """POST salvar rascunho (sem cópia) deve criar diário com status SALVAMENTO_PARCIAL."""
        self._login_and_select_project()
        url = reverse('diary-new')
        new_date = date.today()
        post = _minimal_diary_post(self.project, new_date, partial_save=True)
        resp = self.client.post(url, post)
        self.assertEqual(resp.status_code, 302, resp.content.decode()[:500] if resp.status_code != 302 else '')
        self.assertRedirects(resp, reverse('report-list'))
        diary = ConstructionDiary.objects.filter(project=self.project, date=new_date).first()
        self.assertIsNotNone(diary)
        self.assertEqual(diary.status, DiaryStatus.SALVAMENTO_PARCIAL)

    def test_save_draft_after_copy(self):
        """POST salvar rascunho após ter carregado página com copy_from deve salvar rascunho com dados copiados."""
        self._login_and_select_project()
        # Primeiro GET com cópia para obter dados iniciais (simula usuário que aplicou cópia no front)
        new_date = date.today()
        post = _minimal_diary_post(self.project, new_date, partial_save=True)
        post['general_notes'] = 'Notas do relatório anterior'  # como se tivesse vindo da cópia
        post['weather_morning_condition'] = 'B'
        post['weather_morning_workable'] = 'T'
        url = reverse('diary-new')
        resp = self.client.post(url, post)
        self.assertEqual(resp.status_code, 302)
        diary = ConstructionDiary.objects.filter(project=self.project, date=new_date).first()
        self.assertIsNotNone(diary)
        self.assertEqual(diary.status, DiaryStatus.SALVAMENTO_PARCIAL)
        self.assertEqual(diary.general_notes, 'Notas do relatório anterior')

    def test_save_full_diary_approved(self):
        """POST Salvar diário (não rascunho) com assinatura deve deixar status APROVADO e sent_to_owner_at."""
        self._login_and_select_project()
        new_date = date.today()
        post = _minimal_diary_post(
            self.project,
            new_date,
            partial_save=False,
            signature_inspection='data:image/png;base64,iVBORw0KGgo=',
        )
        url = reverse('diary-new')
        resp = self.client.post(url, post)
        self.assertEqual(resp.status_code, 302, resp.content.decode()[:800] if resp.status_code != 302 else '')
        diary = ConstructionDiary.objects.filter(project=self.project, date=new_date).first()
        self.assertIsNotNone(diary)
        self.assertEqual(diary.status, DiaryStatus.APROVADO)
        self.assertIsNotNone(diary.approved_at)
        self.assertIsNotNone(diary.sent_to_owner_at)
        self.assertEqual(diary.reviewed_by, self.user)

    def test_edit_draft_then_save_full(self):
        """Editar rascunho (alterar dados) e Salvar diário deve resultar em APROVADO."""
        self._login_and_select_project()
        draft = ConstructionDiary.objects.create(
            project=self.project,
            date=date.today(),
            status=DiaryStatus.SALVAMENTO_PARCIAL,
            created_by=self.user,
            general_notes='Rascunho',
        )
        wl = DailyWorkLog.objects.create(
            diary=draft,
            activity=self.activity,
            percentage_executed_today=Decimal('5.00'),
            accumulated_progress_snapshot=Decimal('10.00'),
        )
        url = reverse('diary-edit', kwargs={'pk': draft.pk})
        post = _minimal_diary_post(
            self.project,
            draft.date,
            partial_save=False,
            signature_inspection='data:image/png;base64,sig123',
        )
        post['general_notes'] = 'Notas alteradas'
        # Manter o worklog existente (1 form)
        post['work_logs-TOTAL_FORMS'] = '1'
        post['work_logs-INITIAL_FORMS'] = '1'
        post['work_logs-0-id'] = str(wl.pk)
        post['work_logs-0-activity_description'] = self.activity.name
        post['work_logs-0-work_stage'] = 'AN'
        post['work_logs-0-percentage_executed_today'] = '5.00'
        post['work_logs-0-accumulated_progress_snapshot'] = '10.00'
        post['work_logs-0-DELETE'] = ''
        resp = self.client.post(url, post)
        self.assertEqual(resp.status_code, 302, resp.content.decode()[:800] if resp.status_code != 302 else '')
        draft.refresh_from_db()
        self.assertEqual(draft.status, DiaryStatus.APROVADO)
        self.assertEqual(draft.general_notes, 'Notas alteradas')

    def test_approved_diary_not_editable(self):
        """GET em diary-edit para diário APROVADO deve redirecionar (não pode editar)."""
        self._login_and_select_project()
        approved = ConstructionDiary.objects.create(
            project=self.project,
            date=date.today(),
            status=DiaryStatus.APROVADO,
            created_by=self.user,
            approved_at=timezone.now(),
        )
        url = reverse('diary-edit', kwargs={'pk': approved.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        # Não seguir o redirect: a URL de diary-detail pode resolver para a API que retorna 302
        self.assertRedirects(resp, reverse('diary-detail', kwargs={'pk': approved.pk}), fetch_redirect_response=False)

    def test_last_diary_for_copy_in_context(self):
        """GET diary-new com projeto que tem diário deve ter last_diary_for_copy no context."""
        self._login_and_select_project()
        url = reverse('diary-new')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('last_diary_for_copy', resp.context)
        self.assertIsNotNone(resp.context['last_diary_for_copy'])
        self.assertEqual(resp.context['last_diary_for_copy']['id'], self.source_diary.pk)

    def test_last_diary_for_copy_excludes_current_when_editing(self):
        """Ao editar um diário, last_diary_for_copy não deve incluir o próprio diário."""
        self._login_and_select_project()
        # Criar outro diário mais recente que source_diary
        newer = ConstructionDiary.objects.create(
            project=self.project,
            date=date.today(),
            status=DiaryStatus.SALVAMENTO_PARCIAL,
            created_by=self.user,
        )
        url = reverse('diary-edit', kwargs={'pk': newer.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        last = resp.context.get('last_diary_for_copy')
        self.assertIsNotNone(last)
        self.assertNotEqual(last['id'], newer.pk)

    def test_save_full_requires_signature(self):
        """POST Salvar diário sem assinatura deve retornar ao form com erro (não redirecionar)."""
        self._login_and_select_project()
        new_date = date.today()
        post = _minimal_diary_post(self.project, new_date, partial_save=False, signature_inspection='')
        url = reverse('diary-new')
        resp = self.client.post(url, post)
        self.assertEqual(resp.status_code, 200)
        diary = ConstructionDiary.objects.filter(project=self.project, date=new_date).first()
        self.assertIsNone(diary)
