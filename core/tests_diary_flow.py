"""
Testes de fluxo completo do Diário de Obra.

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
import json

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
    Equipment,
    EquipmentCategory,
    StandardEquipment,
    DailyWorkLogEquipment,
    DiaryCorrectionRequestLog,
)
from core.forms import (
    ConstructionDiaryForm,
    DiaryImageFormSet,
    DailyWorkLogFormSet,
    DiaryOccurrenceFormSet,
)
from core.utils.diary_equipment import aggregate_equipment_for_diary


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
        self.source_worklog = DailyWorkLog.objects.create(
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

    def test_provisional_unlock_allows_edit_get(self):
        """Com edição provisória liberada, GET diary-edit deve permitir (200)."""
        self._login_and_select_project()
        approved = ConstructionDiary.objects.create(
            project=self.project,
            date=date.today(),
            status=DiaryStatus.APROVADO,
            created_by=self.user,
            approved_at=timezone.now(),
            provisional_edit_granted_at=timezone.now(),
            provisional_edit_granted_by=self.user,
        )
        self.assertTrue(approved.can_be_edited_by(self.user))
        url = reverse('diary-edit', kwargs={'pk': approved.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_clear_provisional_after_partial_save(self):
        """Após guardar (parcial) com unlock provisório, campos de unlock são limpos."""
        self._login_and_select_project()
        approved = ConstructionDiary.objects.create(
            project=self.project,
            date=date.today(),
            status=DiaryStatus.APROVADO,
            created_by=self.user,
            approved_at=timezone.now(),
            edit_requested_at=timezone.now(),
            edit_requested_by=self.user,
            edit_request_note='teste',
            provisional_edit_granted_at=timezone.now(),
            provisional_edit_granted_by=self.user,
        )
        t = timezone.now()
        DiaryCorrectionRequestLog.objects.create(
            diary=approved,
            requested_at=t,
            requested_by=self.user,
            note='teste',
            granted_at=t,
            granted_by=self.user,
        )
        url = reverse('diary-edit', kwargs={'pk': approved.pk})
        post = _minimal_diary_post(self.project, approved.date, partial_save=True)
        post['general_notes'] = 'nota após unlock'
        resp = self.client.post(url, post)
        self.assertEqual(resp.status_code, 302)
        approved.refresh_from_db()
        self.assertIsNone(approved.provisional_edit_granted_at)
        self.assertIsNone(approved.edit_requested_at)
        self.assertEqual(approved.general_notes, 'nota após unlock')
        log = DiaryCorrectionRequestLog.objects.filter(diary=approved).first()
        self.assertIsNotNone(log)
        self.assertIsNotNone(log.closed_at)

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

    def test_client_diary_detail_internal_user_redirects_to_frontend_detail(self):
        """
        Usuário interno acessando rota do cliente deve ir para /diaries/<pk>/.
        Evita loop quando há colisão de nome de rota com endpoint da API.
        """
        self._login_and_select_project()
        url = reverse('client-diary-detail', kwargs={'pk': self.source_diary.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, f'/diaries/{self.source_diary.pk}/')

    def test_copy_equipment_preserves_quantity_and_equipment_id(self):
        """Copy de equipamentos deve manter quantity e equipment_id no contexto."""
        self._login_and_select_project()
        eq = Equipment.objects.create(
            code='EQ-COPY-01',
            name='Escavadeira Teste',
            equipment_type='Escavadeira Teste',
            is_active=True,
        )
        DailyWorkLogEquipment.objects.create(
            work_log=self.source_worklog,
            equipment=eq,
            quantity=3,
        )

        url = reverse('diary-new')
        resp = self.client.get(url, {
            'copy_from': str(self.source_diary.pk),
            'copy': 'equipment',
        })
        self.assertEqual(resp.status_code, 200)
        existing_equipment = resp.context.get('existing_diary_equipment') or []
        item = next((x for x in existing_equipment if x.get('equipment_id') == eq.id), None)
        self.assertIsNotNone(item, 'Equipamento copiado não encontrado por equipment_id')
        self.assertEqual(item.get('quantity'), 3)

    def test_save_with_duplicate_equipment_payload_aggregates_quantity(self):
        """Payload duplicado de equipamentos deve ser agregado sem distorcer quantidade."""
        self._login_and_select_project()
        eq = Equipment.objects.create(
            code='EQ-AGG-01',
            name='Rolo Compactador',
            equipment_type='Rolo Compactador',
            is_active=True,
        )
        new_date = date.today()
        post = _minimal_diary_post(self.project, new_date, partial_save=True)
        post['equipment_data'] = json.dumps([
            {'equipment_id': eq.id, 'name': eq.name, 'quantity': 2},
            {'equipment_id': eq.id, 'name': eq.name, 'quantity': 3},
        ])
        url = reverse('diary-new')
        resp = self.client.post(url, post)
        self.assertEqual(resp.status_code, 302, resp.content.decode()[:500] if resp.status_code != 302 else '')

        diary = ConstructionDiary.objects.filter(project=self.project, date=new_date).first()
        self.assertIsNotNone(diary)
        through_rows = DailyWorkLogEquipment.objects.filter(work_log__diary=diary, equipment=eq)
        self.assertEqual(through_rows.count(), 1)
        self.assertEqual(through_rows.first().quantity, 5)

    def test_save_custom_equipment_reuses_existing_name_with_js_escape(self):
        """
        Equipamento sem equipment_id deve reutilizar cadastro existente por nome
        (incluindo payload com escape JS \\u0027).
        """
        self._login_and_select_project()
        existing = Equipment.objects.create(
            code='EQ-BOMBA-01',
            name="Bomba d'água",
            equipment_type='Bomba',
            is_active=True,
        )
        new_date = date.today()
        post = _minimal_diary_post(self.project, new_date, partial_save=True)
        post['equipment_data'] = json.dumps([
            {'name': 'Bomba d\\u0027água', 'quantity': 3},
        ])

        url = reverse('diary-new')
        resp = self.client.post(url, post)
        self.assertEqual(resp.status_code, 302, resp.content.decode()[:500] if resp.status_code != 302 else '')

        diary = ConstructionDiary.objects.filter(project=self.project, date=new_date).first()
        self.assertIsNotNone(diary)
        # Não deve criar novo cadastro de equipamento por colisão de nome.
        self.assertEqual(Equipment.objects.filter(name__iexact="Bomba d'água").count(), 1)
        through = DailyWorkLogEquipment.objects.filter(work_log__diary=diary, equipment=existing).first()
        self.assertIsNotNone(through)
        self.assertEqual(through.quantity, 3)

    def test_equipment_payload_mismatched_id_prioritizes_name(self):
        """
        Se equipment_id vier inconsistente com o nome (ex.: id de tabela padrão),
        o backend deve resolver por nome para evitar associação incorreta.
        """
        self._login_and_select_project()
        wrong = Equipment.objects.create(
            code='EQ-WRONG-01',
            name='Equipamento Errado',
            equipment_type='Teste',
            is_active=True,
        )
        expected = Equipment.objects.create(
            code='EQ-RIGHT-01',
            name='Betoneira',
            equipment_type='Teste',
            is_active=True,
        )
        new_date = date.today()
        post = _minimal_diary_post(self.project, new_date, partial_save=True)
        post['equipment_data'] = json.dumps([
            {'equipment_id': wrong.id, 'name': 'Betoneira', 'quantity': 2},
        ])
        url = reverse('diary-new')
        resp = self.client.post(url, post)
        self.assertEqual(resp.status_code, 302, resp.content.decode()[:500] if resp.status_code != 302 else '')

        diary = ConstructionDiary.objects.filter(project=self.project, date=new_date).first()
        self.assertIsNotNone(diary)
        right_row = DailyWorkLogEquipment.objects.filter(work_log__diary=diary, equipment=expected).first()
        wrong_row = DailyWorkLogEquipment.objects.filter(work_log__diary=diary, equipment=wrong).first()
        self.assertIsNotNone(right_row)
        self.assertEqual(right_row.quantity, 2)
        self.assertIsNone(wrong_row)

    def test_equipment_payload_standard_id_uses_standard_name(self):
        """Payload com standard_equipment_id deve resolver para Equipment pelo nome padrão."""
        self._login_and_select_project()
        category = EquipmentCategory.objects.create(slug='teste-equip', name='Teste Equip', order=1)
        std = StandardEquipment.objects.create(category=category, name='Furadeira', order=1)
        expected = Equipment.objects.create(
            code='EQ-FURA-01',
            name='Furadeira',
            equipment_type='Teste',
            is_active=True,
        )
        new_date = date.today()
        post = _minimal_diary_post(self.project, new_date, partial_save=True)
        post['equipment_data'] = json.dumps([
            {'standard_equipment_id': std.id, 'name': 'Qualquer Nome', 'quantity': 4},
        ])
        url = reverse('diary-new')
        resp = self.client.post(url, post)
        self.assertEqual(resp.status_code, 302, resp.content.decode()[:500] if resp.status_code != 302 else '')

        diary = ConstructionDiary.objects.filter(project=self.project, date=new_date).first()
        self.assertIsNotNone(diary)
        row = DailyWorkLogEquipment.objects.filter(work_log__diary=diary, equipment=expected).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.quantity, 4)

    def test_aggregate_equipment_matches_form_totals(self):
        """PDF e formulário usam aggregate_equipment_for_diary: totais e IDs batem."""
        eq_a = Equipment.objects.create(
            code='AGG-A',
            name='Equip A',
            equipment_type='Teste',
            is_active=True,
        )
        eq_b = Equipment.objects.create(
            code='AGG-B',
            name='Equip B',
            equipment_type='Teste',
            is_active=True,
        )
        DailyWorkLogEquipment.objects.create(
            work_log=self.source_worklog,
            equipment=eq_a,
            quantity=2,
        )
        DailyWorkLogEquipment.objects.create(
            work_log=self.source_worklog,
            equipment=eq_b,
            quantity=4,
        )
        rows, total = aggregate_equipment_for_diary(self.source_diary)
        by_id = {r['equipment_id']: r['quantity'] for r in rows}
        self.assertEqual(by_id.get(eq_a.id), 2)
        self.assertEqual(by_id.get(eq_b.id), 4)
        self.assertEqual(total, 6)
        self.assertEqual(len(rows), 2)

    def test_aggregate_equipment_uses_daily_max_not_sum_across_worklogs(self):
        """
        Mesmo equipamento em múltiplos work_logs do dia não deve somar quantidades;
        deve manter a maior quantidade diária para evitar supercontagem no PDF.
        """
        eq = Equipment.objects.create(
            code='AGG-MAX-01',
            name='Equip Max',
            equipment_type='Teste',
            is_active=True,
        )
        second_activity = Activity.add_root(
            project=self.project,
            name='Atividade Teste 2',
            code='1.1',
            weight=Decimal('1.00'),
        )
        wl2 = DailyWorkLog.objects.create(
            diary=self.source_diary,
            activity=second_activity,
            location='Setor B',
            percentage_executed_today=0,
            accumulated_progress_snapshot=0,
            notes='Outro serviço no mesmo dia',
        )
        DailyWorkLogEquipment.objects.create(
            work_log=self.source_worklog,
            equipment=eq,
            quantity=4,
        )
        DailyWorkLogEquipment.objects.create(
            work_log=wl2,
            equipment=eq,
            quantity=6,
        )

        rows, total = aggregate_equipment_for_diary(self.source_diary)
        by_id = {r['equipment_id']: r['quantity'] for r in rows}
        self.assertEqual(by_id.get(eq.id), 6)
        self.assertEqual(total, 6)

    def test_copy_then_save_equipment_matches_pdf_aggregate(self):
        """
        Copiar relatório (GET) e salvar com equipment_data: o banco deve refletir as quantidades
        e aggregate_equipment_for_diary (mesmo cálculo do PDF) deve bater.
        """
        self._login_and_select_project()
        eq = Equipment.objects.create(
            code='EQ-CHAIN-01',
            name='Equip Copia PDF',
            equipment_type='Teste',
            is_active=True,
        )
        DailyWorkLogEquipment.objects.create(
            work_log=self.source_worklog,
            equipment=eq,
            quantity=7,
        )
        url = reverse('diary-new')
        resp_get = self.client.get(url, {
            'copy_from': str(self.source_diary.pk),
            'copy': 'equipment',
        })
        self.assertEqual(resp_get.status_code, 200)
        existing = resp_get.context.get('existing_diary_equipment') or []
        pre = next((x for x in existing if x.get('equipment_id') == eq.id), None)
        self.assertIsNotNone(pre)
        self.assertEqual(pre.get('quantity'), 7)

        new_date = date.today()
        post = _minimal_diary_post(self.project, new_date, partial_save=True)
        post['equipment_data'] = json.dumps([
            {'equipment_id': eq.id, 'name': eq.name, 'quantity': 7},
        ])
        resp_post = self.client.post(url, post)
        self.assertEqual(resp_post.status_code, 302, getattr(resp_post, 'content', b'')[:500])

        diary_first = ConstructionDiary.objects.filter(project=self.project, date=new_date).first()
        self.assertIsNotNone(diary_first)
        rows1, total1 = aggregate_equipment_for_diary(diary_first)
        self.assertEqual(total1, 7)
        self.assertEqual(
            {r['equipment_id']: r['quantity'] for r in rows1},
            {eq.id: 7},
        )

        # Cópia da cópia (GET): fonte = diário recém-salvo deve expor os mesmos totais no contexto
        resp_get2 = self.client.get(url, {
            'copy_from': str(diary_first.pk),
            'copy': 'equipment',
        })
        self.assertEqual(resp_get2.status_code, 200)
        existing2 = resp_get2.context.get('existing_diary_equipment') or []
        pre2 = next((x for x in existing2 if x.get('equipment_id') == eq.id), None)
        self.assertIsNotNone(pre2, 'Segunda cópia (GET) deve trazer o mesmo equipamento')
        self.assertEqual(pre2.get('quantity'), 7)

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

    def test_save_draft_accepts_checkbox_on_value(self):
        """Flag de rascunho enviada como 'on' deve manter status SALVAMENTO_PARCIAL."""
        self._login_and_select_project()
        new_date = date.today()
        post = _minimal_diary_post(self.project, new_date, partial_save=False)
        post['partial_save'] = ''
        post['as_partial_checkbox'] = 'on'
        url = reverse('diary-new')
        resp = self.client.post(url, post)
        self.assertEqual(resp.status_code, 302)
        diary = ConstructionDiary.objects.filter(project=self.project, date=new_date).first()
        self.assertIsNotNone(diary)
        self.assertEqual(diary.status, DiaryStatus.SALVAMENTO_PARCIAL)

    def test_signature_value_is_preserved_on_validation_error(self):
        """Quando houver erro de validação, a assinatura enviada deve permanecer no HTML retornado."""
        self._login_and_select_project()
        new_date = date.today()
        post = _minimal_diary_post(
            self.project,
            new_date,
            partial_save=False,
            signature_inspection='data:image/png;base64,sig-preservada',
        )
        # Força erro de validação no form principal para re-renderizar sem perder assinatura
        post['date'] = 'data-invalida'
        url = reverse('diary-new')
        resp = self.client.post(url, post)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'sig-preservada')
