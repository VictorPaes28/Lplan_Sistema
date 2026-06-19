"""
Cenários de produção: frentes, aprovação, PDF, RDO complexo.
Evidências para validação pré-commit.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core.diary_copy_services import (
    serialize_labor_entries_for_copy,
    serialize_occurrences_for_copy,
    serialize_work_logs_for_copy,
)
from core.models import (
    Activity,
    ActivityStatus,
    ConstructionDiary,
    DailyWorkLog,
    DailyWorkLogEquipment,
    DiaryApprovalHistory,
    DiaryLaborEntry,
    DiaryOccurrence,
    DiaryStatus,
    Equipment,
    LaborCargo,
    LaborCategory,
    OccurrenceTag,
    Project,
    ProjectDiaryApprover,
    ProjectFront,
)
from core.tests.test_diary_audit import _detail_url, _full_post
from core.tests.test_diary_copy import DiaryCopyTestMixin, GEN_MAO_OBRA_EQUIP_CODE
from core.utils.diary_equipment import aggregate_equipment_for_diary
from core.utils.diary_labor import (
    build_labor_entries_by_category,
    merge_labor_entries_m2m_fallback_for_html,
)


def _pdf_text(pdf_buffer: BytesIO) -> str:
    from PyPDF2 import PdfReader
    reader = PdfReader(pdf_buffer)
    return '\n'.join((page.extract_text() or '') for page in reader.pages)


def _labor_snapshot(diary) -> dict[str, int]:
    merged = merge_labor_entries_m2m_fallback_for_html(
        build_labor_entries_by_category(diary), diary,
    ) or {}
    out: dict[str, int] = {}
    for slug in ('indireta', 'direta'):
        for row in merged.get(slug) or []:
            name = (row.get('cargo_name') or '').strip()
            if name:
                out[name] = int(row.get('quantity') or 0)
    for block in merged.get('terceirizada') or []:
        for row in block.get('items') or []:
            name = (row.get('cargo_name') or '').strip()
            if name:
                out[name] = int(row.get('quantity') or 0)
    return out


class FrontScenarioMixin(DiaryCopyTestMixin):
    """Projeto com duas frentes ativas."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.front_a = ProjectFront.objects.create(
            project=cls.project,
            name='Frente Norte Audit',
            code='FN-AUD',
            is_active=True,
        )
        cls.front_b = ProjectFront.objects.create(
            project=cls.project,
            name='Frente Sul Audit',
            code='FS-AUD',
            is_active=True,
        )

    def _new_url(self, front: ProjectFront, extra: str = '') -> str:
        base = reverse('diary-new') + f'?front={front.pk}'
        return base + ('&' + extra.lstrip('&') if extra else '')

    def _make_front_diary(
        self,
        front: ProjectFront,
        diary_date: date,
        *,
        marker: str,
    ) -> ConstructionDiary:
        act = self._make_activity(f'Ativ {marker}')
        tag, _ = OccurrenceTag.objects.get_or_create(
            name=f'Tag {marker}', defaults={'color': '#333', 'is_active': True},
        )
        from core.project_labor_catalog import ensure_project_labor_catalog
        ensure_project_labor_catalog(self.project)
        cat = LaborCategory.objects.filter(slug='direta').first()
        cargo, _ = LaborCargo.objects.get_or_create(
            category=cat, name=f'Cargo {marker}', defaults={'order': 0},
        )
        eq, _ = Equipment.objects.get_or_create(
            name=f'Equip {marker}', defaults={'code': f'EQ-{marker[:8]}'},
        )
        diary = ConstructionDiary.objects.create(
            project=self.project,
            front=front,
            date=diary_date,
            status=DiaryStatus.SALVAMENTO_PARCIAL,
            created_by=self.user,
            general_notes=f'Notas {marker}',
            accidents=f'Acidente {marker}',
            weather_morning_condition='B',
            weather_morning_workable='T',
        )
        wl = DailyWorkLog.objects.create(
            diary=diary, activity=act, work_stage='IN', notes=f'Nota WL {marker}',
        )
        occ = DiaryOccurrence.objects.create(
            diary=diary, description=f'Ocorrência {marker}', created_by=self.user,
        )
        occ.tags.set([tag])
        DiaryLaborEntry.objects.create(diary=diary, cargo=cargo, quantity=3)
        DailyWorkLogEquipment.objects.create(work_log=wl, equipment=eq, quantity=2)
        return diary


class DiaryFrontLifecycleTests(FrontScenarioMixin, TestCase):
    """Frentes: vínculo correto em todo o ciclo."""

    def test_create_draft_preserves_front_and_sections(self):
        client = self._session_client()
        target = date.today() - timedelta(days=20)
        act = self._make_activity('Front Create Act')
        tag, _ = OccurrenceTag.objects.get_or_create(
            name='Tag Front Create', defaults={'color': '#111', 'is_active': True},
        )
        from core.project_labor_catalog import ensure_project_labor_catalog
        ensure_project_labor_catalog(self.project)
        cat = LaborCategory.objects.filter(slug='direta').first()
        cargo, _ = LaborCargo.objects.get_or_create(
            category=cat, name='Cargo Front Create', defaults={'order': 0},
        )
        eq, _ = Equipment.objects.get_or_create(
            name='Equip Front Create', defaults={'code': 'EQ-FR-CREATE'},
        )
        post = _full_post(
            self.project, target,
            work_logs_json=[{
                'activity_description': act.name,
                'work_stage': 'IN',
                'percentage_executed_today': '5',
                'accumulated_progress_snapshot': '10',
                'location': 'Trecho FN',
                'notes': 'WL front',
            }],
            occurrences_json=[{
                'description': 'Occ front create',
                'tags': [tag.pk],
                'tag_ids': [tag.pk],
            }],
            labor_json=[{
                'cargo_name': cargo.name,
                'quantity': 4,
                'company': '',
                'category_slug': 'direta',
                'cargo_id': cargo.id,
            }],
            equipment_json=[{'equipment_id': eq.id, 'name': eq.name, 'quantity': 5}],
            front=str(self.front_a.pk),
            general_notes='Notas frente A',
        )
        resp = client.post(self._new_url(self.front_a), post)
        self.assertIn(resp.status_code, (302, 200))
        diary = ConstructionDiary.objects.get(
            project=self.project, date=target, front=self.front_a,
        )
        self.assertEqual(diary.front_id, self.front_a.pk)
        self.assertEqual(diary.occurrences.count(), 1)
        self.assertEqual(diary.labor_entries.first().quantity, 4)

        detail = client.get(_detail_url(diary.pk))
        html = detail.content.decode()
        self.assertIn('Frente Norte Audit', html)
        self.assertIn('Front Create Act', html)
        self.assertIn('Occ front create', html)
        self.assertIn('Notas frente A', html)

    def test_copy_only_from_same_front(self):
        client = self._session_client()
        src_a = self._make_front_diary(
            self.front_a, date.today() - timedelta(days=21), marker='FA',
        )
        self._make_front_diary(
            self.front_b, date.today() - timedelta(days=21), marker='FB',
        )
        url = self._new_url(
            self.front_a,
            f'copy_from={src_a.pk}&copy=activities,ocorrencias',
        )
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Ativ FA', resp.content.decode())
        self.assertNotIn('Ativ FB', resp.content.decode())

    def test_copy_save_reopen_keeps_front(self):
        client = self._session_client()
        src = self._make_front_diary(
            self.front_a, date.today() - timedelta(days=22), marker='CopyFront',
        )
        target = date.today() - timedelta(days=19)
        post = _full_post(
            self.project, target,
            work_logs_json=serialize_work_logs_for_copy(src),
            occurrences_json=serialize_occurrences_for_copy(src),
            labor_json=serialize_labor_entries_for_copy(src, self.project),
            equipment_json=[],
            front=str(self.front_a.pk),
        )
        client.post(self._new_url(self.front_a), post)
        copied = ConstructionDiary.objects.get(
            project=self.project, date=target, front=self.front_a,
        )
        self.assertEqual(copied.front_id, self.front_a.pk)
        self.assertEqual(copied.work_logs.exclude(
            activity__code=GEN_MAO_OBRA_EQUIP_CODE,
        ).count(), 1)

        post['general_notes'] = 'Editado frente A'
        client.post(reverse('diary-edit', kwargs={'pk': copied.pk}), post)
        copied.refresh_from_db()
        self.assertEqual(copied.general_notes, 'Editado frente A')
        self.assertEqual(copied.front_id, self.front_a.pk)

    def test_report_list_filter_by_front(self):
        client = self._session_client()
        d_a = self._make_front_diary(
            self.front_a, date.today() - timedelta(days=23), marker='ListA',
        )
        d_b = self._make_front_diary(
            self.front_b, date.today() - timedelta(days=24), marker='ListB',
        )
        resp_all = client.get(reverse('report-list'))
        self.assertIn(d_a.date.strftime('%d/%m/%Y'), resp_all.content.decode())
        self.assertIn(d_b.date.strftime('%d/%m/%Y'), resp_all.content.decode())

        resp_a = client.get(reverse('report-list') + f'?front={self.front_a.pk}')
        html_a = resp_a.content.decode()
        self.assertIn(d_a.date.strftime('%d/%m/%Y'), html_a)
        self.assertNotIn(d_b.date.strftime('%d/%m/%Y'), html_a)

    def test_two_fronts_same_date_allowed(self):
        """Unique (project, front, date) permite mesmo dia em frentes diferentes."""
        d1 = self._make_front_diary(
            self.front_a, date.today() - timedelta(days=25), marker='SameDayA',
        )
        d2 = self._make_front_diary(
            self.front_b, date.today() - timedelta(days=25), marker='SameDayB',
        )
        self.assertNotEqual(d1.pk, d2.pk)
        self.assertEqual(d1.date, d2.date)


class DiaryApprovalFlowTests(DiaryCopyTestMixin, TestCase):
    """Ciclo rascunho → envio → aprovação/reprovação → reedição."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.approver = User.objects.create_user(
            username='rdo_approver_audit',
            password='test-pass-123',
            is_staff=True,
        )
        ProjectDiaryApprover.objects.create(
            project=cls.project, user=cls.approver, is_active=True,
        )

    def _approver_client(self) -> Client:
        client = Client()
        client.force_login(self.approver)
        session = client.session
        session['selected_project_id'] = self.project.id
        session['selected_project_name'] = self.project.name
        session['selected_project_code'] = self.project.code
        session.save()
        return client

    def _complex_payload(self, marker: str) -> dict:
        act1 = self._make_activity(f'Approv Act1 {marker}')
        act2 = self._make_activity(f'Approv Act2 {marker}')
        tag, _ = OccurrenceTag.objects.get_or_create(
            name=f'Approv Tag {marker}', defaults={'color': '#222', 'is_active': True},
        )
        from core.project_labor_catalog import ensure_project_labor_catalog
        ensure_project_labor_catalog(self.project)
        cat = LaborCategory.objects.filter(slug='indireta').first()
        cargo, _ = LaborCargo.objects.get_or_create(
            category=cat, name=f'Approv Cargo {marker}', defaults={'order': 0},
        )
        eq, _ = Equipment.objects.get_or_create(
            name=f'Approv Equip {marker}', defaults={'code': f'EQ-APP-{marker[:4]}'},
        )
        return {
            'work_logs_json': [
                {
                    'activity_description': act1.name,
                    'work_stage': 'IN',
                    'percentage_executed_today': '10',
                    'accumulated_progress_snapshot': '20',
                    'location': 'L1',
                    'notes': f'n1 {marker}',
                },
                {
                    'activity_description': act2.name,
                    'work_stage': 'AN',
                    'percentage_executed_today': '5',
                    'accumulated_progress_snapshot': '15',
                    'location': 'L2',
                    'notes': f'n2 {marker}',
                },
            ],
            'occurrences_json': [{
                'description': f'Approv Occ {marker}',
                'tags': [tag.pk],
                'tag_ids': [tag.pk],
            }],
            'labor_json': [{
                'cargo_name': cargo.name,
                'quantity': 7,
                'company': '',
                'category_slug': 'indireta',
                'cargo_id': cargo.id,
            }],
            'equipment_json': [{
                'equipment_id': eq.id,
                'name': eq.name,
                'quantity': 3,
            }],
            'general_notes': f'Notas fluxo {marker}',
        }

    def _counts(self, diary) -> dict:
        return {
            'activities': diary.work_logs.exclude(
                activity__code=GEN_MAO_OBRA_EQUIP_CODE,
            ).count(),
            'occurrences': diary.occurrences.count(),
            'labor_qty': sum(
                int(e.quantity or 0) for e in diary.labor_entries.all()
            ),
            'equip_total': aggregate_equipment_for_diary(diary)[1],
        }

    def test_full_approval_cycle_preserves_data(self):
        client = self._session_client()
        target = date.today() - timedelta(days=5)
        payload = self._complex_payload('approve')
        post = _full_post(
            self.project, target,
            partial=False,
            work_logs_json=payload['work_logs_json'],
            occurrences_json=payload['occurrences_json'],
            labor_json=payload['labor_json'],
            equipment_json=payload['equipment_json'],
            general_notes=payload['general_notes'],
            signature_inspection='data:image/png;base64,iVBORw0KGgo=',
            signature_production='data:image/png;base64,iVBORw0KGgo=',
        )
        client.post(reverse('diary-new'), post)
        diary = ConstructionDiary.objects.get(project=self.project, date=target)
        self.assertEqual(diary.status, DiaryStatus.AGUARDANDO_APROVACAO_GESTOR)
        before = self._counts(diary)

        approver = self._approver_client()
        approver.post(
            reverse('diary-review-decision', kwargs={'pk': diary.pk}),
            {'decision': 'approve', 'comment': 'OK audit'},
        )
        diary.refresh_from_db()
        self.assertEqual(diary.status, DiaryStatus.APROVADO)
        after = self._counts(diary)
        self.assertEqual(before, after)
        self.assertEqual(
            DiaryApprovalHistory.objects.filter(
                diary=diary, decision=DiaryApprovalHistory.DECISAO_APROVAR,
            ).count(),
            1,
        )
        detail = client.get(_detail_url(diary.pk))
        self.assertIn('Notas fluxo approve', detail.content.decode())

    def test_reject_edit_resubmit_preserves_and_updates(self):
        client = self._session_client()
        target = date.today() - timedelta(days=6)
        payload = self._complex_payload('reject')
        post = _full_post(
            self.project, target,
            partial=False,
            work_logs_json=payload['work_logs_json'],
            occurrences_json=payload['occurrences_json'],
            labor_json=payload['labor_json'],
            equipment_json=payload['equipment_json'],
            general_notes=payload['general_notes'],
            signature_inspection='data:image/png;base64,iVBORw0KGgo=',
            signature_production='data:image/png;base64,iVBORw0KGgo=',
        )
        client.post(reverse('diary-new'), post)
        diary = ConstructionDiary.objects.get(project=self.project, date=target)
        before = self._counts(diary)

        approver = self._approver_client()
        approver.post(
            reverse('diary-review-decision', kwargs={'pk': diary.pk}),
            {'decision': 'reject', 'comment': 'Ajustar MO'},
        )
        diary.refresh_from_db()
        self.assertEqual(diary.status, DiaryStatus.REPROVADO_GESTOR)
        self.assertEqual(self._counts(diary), before)

        edit_post = _full_post(
            self.project, target,
            partial=False,
            work_logs_json=payload['work_logs_json'],
            occurrences_json=payload['occurrences_json'],
            labor_json=payload['labor_json'],
            equipment_json=payload['equipment_json'],
            general_notes='Notas corrigidas pós-reprovação',
            signature_inspection='data:image/png;base64,iVBORw0KGgo=',
            signature_production='data:image/png;base64,iVBORw0KGgo=',
        )
        client.post(reverse('diary-edit', kwargs={'pk': diary.pk}), edit_post)
        diary.refresh_from_db()
        self.assertEqual(diary.status, DiaryStatus.AGUARDANDO_APROVACAO_GESTOR)
        self.assertEqual(diary.general_notes, 'Notas corrigidas pós-reprovação')
        self.assertEqual(self._counts(diary), before)

    def test_draft_then_submit_no_duplication(self):
        client = self._session_client()
        target = date.today() - timedelta(days=7)
        payload = self._complex_payload('draft')
        draft_post = _full_post(
            self.project, target,
            partial=True,
            work_logs_json=payload['work_logs_json'],
            occurrences_json=payload['occurrences_json'],
            labor_json=payload['labor_json'],
            equipment_json=payload['equipment_json'],
        )
        resp = client.post(reverse('diary-new'), draft_post)
        self.assertIn(resp.status_code, (302, 200))
        diary = ConstructionDiary.objects.get(project=self.project, date=target)
        self.assertEqual(diary.status, DiaryStatus.SALVAMENTO_PARCIAL)
        c1 = self._counts(diary)

        full_post = _full_post(
            self.project, target,
            partial=False,
            work_logs_json=payload['work_logs_json'],
            occurrences_json=payload['occurrences_json'],
            labor_json=payload['labor_json'],
            equipment_json=payload['equipment_json'],
            signature_inspection='data:image/png;base64,iVBORw0KGgo=',
            signature_production='data:image/png;base64,iVBORw0KGgo=',
        )
        client.post(reverse('diary-edit', kwargs={'pk': diary.pk}), full_post)
        diary.refresh_from_db()
        self.assertEqual(diary.status, DiaryStatus.AGUARDANDO_APROVACAO_GESTOR)
        self.assertEqual(self._counts(diary), c1)


class DiaryPdfParityTests(DiaryCopyTestMixin, TestCase):
    """Paridade banco ↔ detalhe ↔ PDF."""

    def _build_complex_diary(self, marker: str = 'PDF') -> ConstructionDiary:
        diary = self._make_source_diary(
            diary_date=date.today() - timedelta(days=8),
            with_activities=True,
            with_occurrences=True,
            with_labor_entries=True,
            with_equipment=True,
            with_interrupcoes=True,
            with_climate=True,
        )
        diary.general_notes = f'Notas PDF {marker}'
        diary.accidents = f'Acidente PDF {marker}'
        diary.save(update_fields=['general_notes', 'accidents'])
        return diary

    def test_db_detail_pdf_contain_same_markers(self):
        diary = self._build_complex_diary()
        client = self._session_client()
        detail = client.get(_detail_url(diary.pk))
        self.assertEqual(detail.status_code, 200)
        html = detail.content.decode()

        labor_db = _labor_snapshot(diary)
        equip_rows, equip_total = aggregate_equipment_for_diary(diary)
        act_names = list(
            diary.work_logs.exclude(activity__code=GEN_MAO_OBRA_EQUIP_CODE)
            .values_list('activity__name', flat=True),
        )
        occ_texts = list(diary.occurrences.values_list('description', flat=True))

        for name in act_names:
            self.assertIn(name, html)
        for occ in occ_texts:
            self.assertIn(occ, html)
        self.assertIn('Notas PDF PDF', html)
        self.assertIn('Acidente PDF PDF', html)
        self.assertEqual(detail.context['equipment_total_quantity'], equip_total)

        from core.utils.pdf_generator import PDFGenerator
        pdf_buf = PDFGenerator.generate_diary_pdf(diary.pk)
        self.assertIsNotNone(pdf_buf)
        pdf_text = _pdf_text(pdf_buf)

        for name in act_names:
            self.assertIn(name, pdf_text, f'Atividade {name} ausente no PDF')
        for occ in occ_texts:
            self.assertIn(occ, pdf_text, f'Ocorrência ausente no PDF')
        self.assertIn('Notas PDF PDF', pdf_text)
        self.assertIn('Acidente PDF PDF', pdf_text)
        for cargo_name, qty in labor_db.items():
            self.assertIn(cargo_name, pdf_text)
            self.assertIn(str(qty), pdf_text)
        for row in equip_rows:
            self.assertIn(row['equipment'].name, pdf_text)

    def test_pdf_labor_totals_match_detail_context(self):
        diary = self._build_complex_diary('Totals')
        client = self._session_client()
        detail = client.get(_detail_url(diary.pk))
        ctx = detail.context
        self.assertEqual(
            ctx['total_direct_labor'] + ctx['total_indirect_labor'] + ctx['total_third_party_labor'],
            ctx['total_labor_efetivo'],
        )
        labor_db = _labor_snapshot(diary)
        self.assertEqual(
            sum(labor_db.values()),
            ctx['total_labor_efetivo'],
        )

    def test_pdf_terceirizada_grouped_by_company_like_detail(self):
        """PDF deve separar empresas terceirizadas com subtotal por empresa."""
        from core.project_labor_catalog import ensure_project_labor_catalog
        from core.utils.pdf_generator import PDFGenerator

        ensure_project_labor_catalog(self.project)
        ter_cat = LaborCategory.objects.filter(slug='terceirizada').first()
        self.assertIsNotNone(ter_cat)
        cargo_e, _ = LaborCargo.objects.get_or_create(
            category=ter_cat, name='Eletricista terceirizado', defaults={'order': 0},
        )
        cargo_p, _ = LaborCargo.objects.get_or_create(
            category=ter_cat, name='Encanador terceirizado', defaults={'order': 1},
        )
        diary = ConstructionDiary.objects.create(
            project=self.project,
            date=date.today() - timedelta(days=9),
            status=DiaryStatus.SALVAMENTO_PARCIAL,
            created_by=self.user,
        )
        for company in ('teste', 'teste2'):
            DiaryLaborEntry.objects.create(
                diary=diary, cargo=cargo_e, quantity=6, company=company,
            )
            DiaryLaborEntry.objects.create(
                diary=diary, cargo=cargo_p, quantity=6, company=company,
            )

        client = self._session_client()
        detail = client.get(_detail_url(diary.pk))
        blocks = detail.context['labor_entries_by_category']['terceirizada']
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]['company_total'], 12)
        self.assertEqual(blocks[1]['company_total'], 12)
        self.assertEqual(detail.context['total_third_party_labor'], 24)

        pdf_buf = PDFGenerator.generate_diary_pdf(diary.pk)
        self.assertIsNotNone(pdf_buf)
        pdf_text = _pdf_text(pdf_buf)
        self.assertIn('teste', pdf_text)
        self.assertIn('teste2', pdf_text)
        self.assertIn('TOTAL TERCEIROS: 24', pdf_text.replace('\n', ' '))
        self.assertNotIn('teste Eletricista terceirizado', pdf_text)
        self.assertNotIn('teste2 Eletricista terceirizado', pdf_text)
        self.assertGreaterEqual(pdf_text.count('Total: 12'), 2)


class ComplexRdoRealisticScenarioTests(DiaryCopyTestMixin, TestCase):
    """
    RDO complexo (múltiplas atividades, ocorrências, MO, equipamentos):
    cópia → edição → save → reopen → detalhe → PDF.
    """

    def test_complex_rdo_full_lifecycle(self):
        client = self._session_client()
        src = self._make_source_diary(
            diary_date=date.today() - timedelta(days=10),
            with_activities=True,
            with_occurrences=True,
            with_labor_entries=True,
            with_equipment=True,
            with_interrupcoes=True,
        )
        target = date.today() - timedelta(days=3)
        wl = serialize_work_logs_for_copy(src)
        occ = serialize_occurrences_for_copy(src)
        labor = serialize_labor_entries_for_copy(src, self.project)
        from core.utils.diary_equipment import aggregate_equipment_for_diary
        rows, _ = aggregate_equipment_for_diary(src)
        equip = [
            {'equipment_id': r['equipment_id'], 'name': r['equipment'].name, 'quantity': r['quantity']}
            for r in rows
        ]

        post = _full_post(
            self.project, target,
            work_logs_json=wl,
            occurrences_json=occ,
            labor_json=labor,
            equipment_json=equip,
            general_notes='Complexo pós-cópia',
            accidents='Acidente complexo',
        )
        client.post(reverse('diary-new'), post)
        diary = ConstructionDiary.objects.get(project=self.project, date=target)
        self.assertEqual(diary.occurrences.count(), 2)
        self.assertEqual(
            diary.work_logs.exclude(activity__code=GEN_MAO_OBRA_EQUIP_CODE).count(), 3,
        )

        for item in wl:
            if item.get('activity_description') == 'teste':
                item['notes'] = 'Alteração complexa'
        labor[0]['quantity'] = int(labor[0].get('quantity', 1)) + 1
        post2 = _full_post(
            self.project, target,
            work_logs_json=wl,
            occurrences_json=occ,
            labor_json=labor,
            equipment_json=equip,
            general_notes='Complexo final',
        )
        client.post(reverse('diary-edit', kwargs={'pk': diary.pk}), post2)
        diary.refresh_from_db()
        self.assertEqual(diary.general_notes, 'Complexo final')
        wl_obj = diary.work_logs.filter(activity__name='teste').first()
        self.assertEqual(wl_obj.notes, 'Alteração complexa')

        detail = client.get(_detail_url(diary.pk))
        html = detail.content.decode()
        self.assertIn('Alteração complexa', html)
        self.assertIn('Ocorrência teste1', html)
        self.assertIn('Complexo final', html)

        from core.utils.pdf_generator import PDFGenerator
        pdf_text = _pdf_text(PDFGenerator.generate_diary_pdf(diary.pk))
        self.assertIn('Alteração complexa', pdf_text)
        self.assertIn('Ocorrência teste1', pdf_text)
        self.assertIn('Complexo final', pdf_text)
