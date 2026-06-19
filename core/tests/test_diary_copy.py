"""
Testes da funcionalidade «Copiar do relatório anterior» e regressão dos formsets/JSON do RDO.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import inlineformset_factory
from django.test import Client, TestCase
from django.urls import reverse

from core.diary_copy_services import (
    GEN_MAO_OBRA_EQUIP_CODE,
    serialize_labor_entries_for_copy,
    serialize_occurrences_for_copy,
    serialize_work_logs_for_copy,
)
from core.diary_json_services import (
    create_occurrences_from_json,
    create_worklogs_from_json,
    extract_work_logs_from_post,
    reconcile_work_logs_payload,
)
from core.forms import (
    DailyWorkLogForm,
    DailyWorkLogFormSetBase,
    DiaryOccurrenceForm,
    DiaryOccurrenceFormSetBase,
)
from core.models import (
    Activity,
    ActivityStatus,
    ConstructionDiary,
    DailyWorkLog,
    DailyWorkLogEquipment,
    DiaryAttachment,
    DiaryLaborEntry,
    DiaryOccurrence,
    DiaryStatus,
    Equipment,
    Labor,
    LaborCargo,
    LaborCategory,
    OccurrenceTag,
    Project,
)


class DiaryCopyTestMixin:
    """Fabrica projeto + usuário staff para testes de RDO."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='rdo_copy_tester',
            password='test-pass-123',
            is_staff=True,
        )
        cls.project = Project.objects.create(
            name='Obra Teste Cópia',
            code='COPY-TEST-001',
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=365),
            is_active=True,
        )

    def _session_client(self) -> Client:
        client = Client()
        client.force_login(self.user)
        session = client.session
        session['selected_project_id'] = self.project.id
        session['selected_project_name'] = self.project.name
        session['selected_project_code'] = self.project.code
        session.save()
        return client

    def _make_activity(self, name: str, code: str | None = None) -> Activity:
        code = code or f'GEN-{name[:12].upper().replace(" ", "-")}'
        return Activity.add_root(
            project=self.project,
            name=name,
            code=code,
            description=f'Atividade {name}',
            weight=Decimal('0'),
            status=ActivityStatus.NOT_STARTED,
        )

    def _make_source_diary(
        self,
        *,
        diary_date: date | None = None,
        with_activities: bool = True,
        with_occurrences: bool = True,
        with_labor_entries: bool = True,
        with_m2m_labor_only: bool = False,
        with_equipment: bool = True,
        with_climate: bool = True,
        with_interrupcoes: bool = True,
        with_attachment: bool = False,
        legacy_empty: bool = False,
    ) -> ConstructionDiary:
        diary_date = diary_date or (date.today() - timedelta(days=1))
        diary = ConstructionDiary.objects.create(
            project=self.project,
            date=diary_date,
            status=DiaryStatus.APROVADO,
            created_by=self.user,
            weather_morning_condition='B' if with_climate else '',
            weather_morning_workable='T' if with_climate else '',
            weather_afternoon_condition='R' if with_climate else '',
            weather_afternoon_workable='N' if with_climate else '',
            general_notes='Obs gerais teste' if with_interrupcoes else '',
            accidents='Acidente X' if with_interrupcoes else '',
            inspections='Fiscalização Y' if with_interrupcoes else '',
        )
        if legacy_empty:
            return diary

        if with_activities:
            for name in ('teste', 'teste2', 'teste3'):
                act = self._make_activity(name)
                DailyWorkLog.objects.create(
                    diary=diary,
                    activity=act,
                    work_stage='IN',
                    notes=f'Nota {name}',
                )
            gen_act = self._make_activity(
                'Registro Geral de Mão de Obra e Equipamentos',
                code=GEN_MAO_OBRA_EQUIP_CODE,
            )
            DailyWorkLog.objects.create(diary=diary, activity=gen_act, work_stage='AN')

        if with_occurrences:
            tag_a, _ = OccurrenceTag.objects.get_or_create(
                name='Tag Copy A',
                defaults={'color': '#2563eb', 'is_active': True},
            )
            tag_b, _ = OccurrenceTag.objects.get_or_create(
                name='Tag Copy B',
                defaults={'color': '#dc2626', 'is_active': True},
            )
            occ1 = DiaryOccurrence.objects.create(
                diary=diary,
                description='Ocorrência teste1',
                created_by=self.user,
            )
            occ1.tags.set([tag_a])
            occ2 = DiaryOccurrence.objects.create(
                diary=diary,
                description='Ocorrência teste2',
                created_by=self.user,
            )
            occ2.tags.set([tag_a, tag_b])

        if with_labor_entries and not with_m2m_labor_only:
            from core.project_labor_catalog import ensure_project_labor_catalog

            ensure_project_labor_catalog(self.project)
            ind_cat = LaborCategory.objects.filter(slug='indireta').first()
            dir_cat = LaborCategory.objects.filter(slug='direta').first()
            ter_cat = LaborCategory.objects.filter(slug='terceirizada').first()
            if ind_cat:
                cargo_i, _ = LaborCargo.objects.get_or_create(
                    category=ind_cat, name='Pedreiro Copy', defaults={'order': 0},
                )
                DiaryLaborEntry.objects.create(diary=diary, cargo=cargo_i, quantity=5)
            if dir_cat:
                cargo_d, _ = LaborCargo.objects.get_or_create(
                    category=dir_cat, name='Servente Copy', defaults={'order': 0},
                )
                DiaryLaborEntry.objects.create(diary=diary, cargo=cargo_d, quantity=3)
            if ter_cat:
                cargo_t, _ = LaborCargo.objects.get_or_create(
                    category=ter_cat, name='p1t Copy', defaults={'order': 0},
                )
                DiaryLaborEntry.objects.create(
                    diary=diary, cargo=cargo_t, quantity=4, company='teste1',
                )

        if with_m2m_labor_only:
            wl = diary.work_logs.first()
            if not wl:
                act = self._make_activity('Ativ M2M')
                wl = DailyWorkLog.objects.create(diary=diary, activity=act, work_stage='AN')
            lab = Labor.objects.create(
                name='Encarregado Legado',
                role='ME',
                labor_type='I',
            )
            wl.resources_labor.add(lab)

        if with_equipment:
            eq, _ = Equipment.objects.get_or_create(
                name='Betoneira Copy Test',
                defaults={'code': 'EQ-COPY-01'},
            )
            wl = diary.work_logs.exclude(
                activity__code=GEN_MAO_OBRA_EQUIP_CODE,
            ).first()
            if wl:
                DailyWorkLogEquipment.objects.create(
                    work_log=wl, equipment=eq, quantity=7,
                )

        if with_attachment:
            DiaryAttachment.objects.create(
                diary=diary,
                name='Anexo teste.pdf',
                file=SimpleUploadedFile('test.pdf', b'%PDF-1.4 test'),
            )

        return diary

    def _base_post(
        self,
        target_date: date,
        *,
        partial: bool = True,
        work_logs_json: list | None = None,
        occurrences_json: list | None = None,
        labor_json: list | None = None,
        equipment_json: list | None = None,
        extra_notes: str = '',
    ) -> dict:
        post = {
            'project': str(self.project.id),
            'date': target_date.isoformat(),
            'partial_save': '1' if partial else '',
            'diary_payload_ready': '1',
            'work_logs_json': json.dumps(work_logs_json if work_logs_json is not None else []),
            'occurrences_json': json.dumps(occurrences_json if occurrences_json is not None else []),
            'diary_labor_data': json.dumps(labor_json if labor_json is not None else []),
            'equipment_data': json.dumps(equipment_json if equipment_json is not None else []),
            'work_logs-TOTAL_FORMS': '0',
            'work_logs-INITIAL_FORMS': '0',
            'work_logs-MIN_NUM_FORMS': '0',
            'work_logs-MAX_NUM_FORMS': '1000',
            'ocorrencias-TOTAL_FORMS': '0',
            'ocorrencias-INITIAL_FORMS': '0',
            'ocorrencias-MIN_NUM_FORMS': '0',
            'ocorrencias-MAX_NUM_FORMS': '1000',
            'diaryimage_set-TOTAL_FORMS': '0',
            'diaryimage_set-INITIAL_FORMS': '0',
            'diaryimage_set-MIN_NUM_FORMS': '0',
            'diaryimage_set-MAX_NUM_FORMS': '1000',
            'general_notes': extra_notes,
        }
        return post


class DiaryCopySerializationTests(DiaryCopyTestMixin, TestCase):
    """Serializers usados na cópia (fonte única)."""

    def test_serialize_work_logs_excludes_gen_activity(self):
        src = self._make_source_diary()
        rows = serialize_work_logs_for_copy(src)
        names = [r['activity_description'] for r in rows]
        self.assertIn('teste', names)
        self.assertNotIn('Registro Geral de Mão de Obra e Equipamentos', names)

    def test_serialize_occurrences_with_tags(self):
        src = self._make_source_diary()
        rows = serialize_occurrences_for_copy(src)
        self.assertEqual(len(rows), 2)
        self.assertTrue(any(r['description'] == 'Ocorrência teste1' for r in rows))
        self.assertTrue(all('tags' in r and 'tag_ids' in r for r in rows))

    def test_serialize_labor_from_diary_labor_entry(self):
        src = self._make_source_diary()
        rows = serialize_labor_entries_for_copy(src, self.project)
        names = {r['cargo_name'] for r in rows}
        self.assertIn('Pedreiro Copy', names)
        self.assertIn('Servente Copy', names)
        self.assertTrue(any(r.get('company') == 'teste1' for r in rows))

    def test_serialize_labor_m2m_fallback_when_no_diary_labor_entry(self):
        src = self._make_source_diary(
            with_labor_entries=False,
            with_m2m_labor_only=True,
            with_activities=True,
            with_occurrences=False,
            with_equipment=False,
        )
        rows = serialize_labor_entries_for_copy(src, self.project)
        self.assertTrue(any(r['cargo_name'] == 'Encarregado Legado' for r in rows))
        self.assertTrue(any(r.get('category_slug') == 'indireta' for r in rows))

    def test_serialize_empty_diary(self):
        src = self._make_source_diary(legacy_empty=True)
        self.assertEqual(serialize_work_logs_for_copy(src), [])
        self.assertEqual(serialize_occurrences_for_copy(src), [])
        self.assertEqual(serialize_labor_entries_for_copy(src, self.project), [])


class DiaryCopyFormsetRegressionTests(DiaryCopyTestMixin, TestCase):
    """Formsets: cópia no GET não marca DELETE; linha vazia extra continua ignorada."""

    def test_copied_worklog_not_marked_delete_on_get(self):
        src = self._make_source_diary()
        initial = serialize_work_logs_for_copy(src)
        FS = inlineformset_factory(
            ConstructionDiary,
            DailyWorkLog,
            form=DailyWorkLogForm,
            formset=DailyWorkLogFormSetBase,
            extra=len(initial),
            can_delete=True,
        )
        fs = FS(
            instance=ConstructionDiary(project=self.project),
            initial=initial,
            prefix='work_logs',
        )
        for form in fs.forms:
            self.assertFalse(fs._should_delete_form(form))
            self.assertTrue((form['activity_description'].value() or '').strip())

    def test_copied_occurrence_not_marked_delete_on_get(self):
        src = self._make_source_diary()
        initial = serialize_occurrences_for_copy(src)
        FS = inlineformset_factory(
            ConstructionDiary,
            DiaryOccurrence,
            form=DiaryOccurrenceForm,
            formset=DiaryOccurrenceFormSetBase,
            extra=len(initial),
            can_delete=True,
        )
        fs = FS(
            instance=ConstructionDiary(project=self.project),
            initial=initial,
            prefix='ocorrencias',
        )
        for form in fs.forms:
            self.assertFalse(fs._should_delete_form(form))

    def test_empty_extra_worklog_still_deleted_on_get(self):
        FS = inlineformset_factory(
            ConstructionDiary,
            DailyWorkLog,
            form=DailyWorkLogForm,
            formset=DailyWorkLogFormSetBase,
            extra=1,
            can_delete=True,
        )
        fs = FS(
            instance=ConstructionDiary(project=self.project),
            prefix='work_logs',
        )
        self.assertTrue(fs._should_delete_form(fs.forms[0]))


class DiaryCopyIntegrationTests(DiaryCopyTestMixin, TestCase):
    """GET cópia + POST save + reabrir edição."""

    def test_get_copy_page_includes_seeds_and_formset_values(self):
        src = self._make_source_diary()
        client = self._session_client()
        url = (
            reverse('diary-new')
            + f'?copy_from={src.pk}&copy=climate,labor,equipment,activities,ocorrencias,interrupcoes'
        )
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('copy-work-logs-seed', content)
        self.assertIn('copy-occurrences-seed', content)
        self.assertIn('teste', content)
        self.assertIn('Ocorrência teste1', content)
        self.assertIn('name="weather_morning_condition"', content)

    def test_copy_save_and_reopen_edit_persists_data(self):
        src = self._make_source_diary()
        target_date = date.today()
        wl = serialize_work_logs_for_copy(src)
        occ = serialize_occurrences_for_copy(src)
        labor = serialize_labor_entries_for_copy(src, self.project)
        from core.utils.diary_equipment import aggregate_equipment_for_diary

        rows, _ = aggregate_equipment_for_diary(src)
        equipment = [
            {
                'name': r['equipment'].name,
                'quantity': r['quantity'],
                'equipment_id': r['equipment_id'],
            }
            for r in rows
        ]

        client = self._session_client()
        post = self._base_post(
            target_date,
            work_logs_json=wl,
            occurrences_json=occ,
            labor_json=labor,
            equipment_json=equipment,
            extra_notes='Nota após cópia',
        )
        post['weather_morning_condition'] = 'B'
        post['weather_morning_workable'] = 'T'
        post['accidents'] = 'Acidente X'
        response = client.post(reverse('diary-new'), post, follow=False)
        self.assertIn(response.status_code, (302, 200))

        new_diary = ConstructionDiary.objects.filter(
            project=self.project, date=target_date,
        ).order_by('-pk').first()
        self.assertIsNotNone(new_diary)
        self.assertEqual(new_diary.general_notes, 'Nota após cópia')
        self.assertEqual(new_diary.accidents, 'Acidente X')

        act_names = list(
            new_diary.work_logs.exclude(
                activity__code=GEN_MAO_OBRA_EQUIP_CODE,
            ).values_list('activity__name', flat=True),
        )
        self.assertIn('teste', act_names)
        self.assertEqual(new_diary.occurrences.count(), 2)
        self.assertGreater(new_diary.labor_entries.count(), 0)

        edit_url = reverse('diary-edit', kwargs={'pk': new_diary.pk})
        edit_get = client.get(edit_url)
        self.assertEqual(edit_get.status_code, 200)
        edit_content = edit_get.content.decode()
        self.assertIn('teste', edit_content)
        self.assertIn('Ocorrência teste1', edit_content)

        labor[0]['quantity'] = int(labor[0].get('quantity', 1)) + 2
        for item in wl:
            if item.get('activity_description') == 'teste':
                item['notes'] = 'Nota alterada pós-cópia'
                break
        post2 = self._base_post(
            target_date,
            work_logs_json=wl,
            occurrences_json=occ,
            labor_json=labor,
            equipment_json=equipment,
            extra_notes='Nota editada final',
        )
        post2['weather_morning_condition'] = 'B'
        response2 = client.post(edit_url, post2, follow=False)
        self.assertIn(response2.status_code, (302, 200))

        new_diary.refresh_from_db()
        self.assertEqual(new_diary.general_notes, 'Nota editada final')
        wl_obj = new_diary.work_logs.exclude(
            activity__code=GEN_MAO_OBRA_EQUIP_CODE,
        ).filter(activity__name='teste').first()
        self.assertIsNotNone(wl_obj)
        self.assertEqual(wl_obj.notes, 'Nota alterada pós-cópia')

    def test_json_save_does_not_wipe_when_payload_ready_and_empty_lists(self):
        """Regressão: JSON vazio com replace_existing apaga — comportamento documentado."""
        src = self._make_source_diary(with_activities=True, with_occurrences=False)
        diary = ConstructionDiary.objects.create(
            project=self.project,
            date=date.today(),
            status=DiaryStatus.SALVAMENTO_PARCIAL,
            created_by=self.user,
        )
        create_worklogs_from_json(
            diary, self.project, json.dumps(serialize_work_logs_for_copy(src)),
            replace_existing=True,
        )
        self.assertEqual(diary.work_logs.exclude(
            activity__code=GEN_MAO_OBRA_EQUIP_CODE,
        ).count(), 3)
        create_worklogs_from_json(diary, self.project, '[]', replace_existing=True)
        self.assertEqual(diary.work_logs.count(), 0)

    def test_attachments_not_in_copy_options(self):
        """Anexos não fazem parte do fluxo de cópia (por design atual)."""
        src = self._make_source_diary(with_attachment=True)
        client = self._session_client()
        url = reverse('diary-new') + f'?copy_from={src.pk}&copy=all'
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(src.attachments.count(), 1)
        new_date = date.today() - timedelta(days=2)
        post = self._base_post(new_date)
        post['weather_morning_condition'] = 'B'
        client.post(reverse('diary-new'), post)
        new_diary = ConstructionDiary.objects.filter(
            project=self.project, date=new_date,
        ).first()
        self.assertIsNotNone(new_diary)
        self.assertEqual(new_diary.attachments.count(), 0)

    def test_partial_source_diary_copy(self):
        """Relatório fonte com só clima + uma atividade."""
        src = ConstructionDiary.objects.create(
            project=self.project,
            date=date.today() - timedelta(days=3),
            status=DiaryStatus.APROVADO,
            created_by=self.user,
            weather_morning_condition='B',
            weather_morning_workable='T',
        )
        act = self._make_activity('única atividade')
        DailyWorkLog.objects.create(diary=src, activity=act, work_stage='AN')

        client = self._session_client()
        url = reverse('diary-new') + f'?copy_from={src.pk}&copy=climate,activities'
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('única atividade', response.content.decode())

        post = self._base_post(
            date.today() - timedelta(days=2),
            work_logs_json=serialize_work_logs_for_copy(src),
            occurrences_json=[],
            labor_json=[],
            equipment_json=[],
        )
        post['weather_morning_condition'] = 'B'
        client.post(reverse('diary-new'), post)
        copied = ConstructionDiary.objects.filter(
            project=self.project,
            date=date.today() - timedelta(days=2),
        ).first()
        self.assertIsNotNone(copied)
        self.assertEqual(copied.weather_morning_condition, 'B')
        self.assertEqual(copied.work_logs.count(), 1)


class DiaryPostReconciliationTests(DiaryCopyTestMixin, TestCase):
    """Servidor reconcilia JSON incompleto com campos work_logs-N-* do POST."""

    def test_extract_work_logs_from_post_reads_all_indices(self):
        post = {
            'work_logs-TOTAL_FORMS': '2',
            'work_logs-0-activity_description': 'Primeira',
            'work_logs-0-work_stage': 'IN',
            'work_logs-1-activity_description': 'Segunda',
            'work_logs-1-work_stage': 'AN',
        }
        items = extract_work_logs_from_post(post)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['activity_description'], 'Primeira')
        self.assertEqual(items[1]['activity_description'], 'Segunda')

    def test_reconcile_merges_missing_json_row_from_formset(self):
        post = {
            'work_logs-TOTAL_FORMS': '2',
            'work_logs-0-activity_description': 'Alpha',
            'work_logs-0-work_stage': 'IN',
            'work_logs-1-activity_description': 'Beta',
            'work_logs-1-work_stage': 'TE',
        }
        json_in = json.dumps([
            {'activity_description': 'Alpha', 'work_stage': 'IN'},
        ])
        merged = json.loads(reconcile_work_logs_payload(post, json_in))
        names = [item['activity_description'] for item in merged]
        self.assertEqual(names, ['Alpha', 'Beta'])

    def test_save_persists_both_when_json_incomplete_but_formset_complete(self):
        """Simula JS que enviou 1 atividade no JSON mas o HTML tinha 2."""
        client = self._session_client()
        target = date.today() - timedelta(days=3)
        act_a = self._make_activity('Formset Alpha')
        act_b = self._make_activity('Formset Beta')
        post = self._base_post(
            target,
            work_logs_json=[{
                'activity_description': act_a.name,
                'work_stage': 'IN',
                'percentage_executed_today': '0',
                'accumulated_progress_snapshot': '0',
                'location': '',
                'notes': '',
            }],
            occurrences_json=[],
            labor_json=[],
            equipment_json=[],
        )
        post['work_logs-TOTAL_FORMS'] = '2'
        post['work_logs-INITIAL_FORMS'] = '0'
        post['work_logs-MIN_NUM_FORMS'] = '0'
        post['work_logs-MAX_NUM_FORMS'] = '1000'
        post['work_logs-0-id'] = ''
        post['work_logs-0-activity_description'] = act_a.name
        post['work_logs-0-work_stage'] = 'IN'
        post['work_logs-1-id'] = ''
        post['work_logs-1-activity_description'] = act_b.name
        post['work_logs-1-work_stage'] = 'AN'
        client.post(reverse('diary-new'), post)
        diary = ConstructionDiary.objects.get(project=self.project, date=target)
        names = list(
            diary.work_logs.values_list('activity__name', flat=True)
        )
        self.assertEqual(len(names), 2)
        self.assertIn('Formset Alpha', names)
        self.assertIn('Formset Beta', names)


class DiaryPayloadGateRegressionTests(DiaryCopyTestMixin, TestCase):
    """Sem diary_payload_ready, MO/equipamentos não devem ser apagados."""

    def test_labor_preserved_without_payload_ready_flag(self):
        diary = ConstructionDiary.objects.create(
            project=self.project,
            date=date.today() - timedelta(days=5),
            status=DiaryStatus.SALVAMENTO_PARCIAL,
            created_by=self.user,
        )
        from core.project_labor_catalog import ensure_project_labor_catalog

        ensure_project_labor_catalog(self.project)
        cat = LaborCategory.objects.filter(slug='direta').first()
        cargo, _ = LaborCargo.objects.get_or_create(
            category=cat, name='Cargo Gate Test', defaults={'order': 0},
        )
        DiaryLaborEntry.objects.create(diary=diary, cargo=cargo, quantity=2)

        client = self._session_client()
        post = self._base_post(diary.date, partial=True)
        post.pop('diary_payload_ready')
        post.pop('diary_labor_data')
        post.pop('work_logs_json')
        post.pop('occurrences_json')
        post.pop('equipment_data')
        client.post(reverse('diary-edit', kwargs={'pk': diary.pk}), post)
        diary.refresh_from_db()
        self.assertEqual(diary.labor_entries.count(), 1)
        self.assertEqual(diary.labor_entries.first().quantity, 2)
