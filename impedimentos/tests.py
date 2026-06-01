from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import QueryDict
from django.test import TestCase

from django.utils import timezone

from gestao_aprovacao.models import Empresa, Obra

from .models import Impedimento, StatusImpedimento
from .views import (
    _has_descendant_not_final,
    _impedimentos_table_queryset,
    _normalize_table_prioridade_filter,
    _ultimo_status_obra,
)

User = get_user_model()


class StatusImpedimentoSignalTests(TestCase):
    def test_cria_status_padrao_quando_obra_e_criada(self):
        empresa = Empresa.objects.create(codigo="EMP-TST-IMP", nome="Empresa Teste")
        obra = Obra.objects.create(
            empresa=empresa,
            codigo="OBR-TST-IMP",
            nome="Obra Teste",
            sigla="TIM",
            ativo=True,
        )

        nomes = list(
            StatusImpedimento.objects.filter(obra=obra)
            .order_by("ordem")
            .values_list("nome", flat=True)
        )
        self.assertEqual(nomes, ["Não iniciado", "Em progresso", "Finalizado"])


class ImpedimentoSubtarefaTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(codigo="EMP-TST-SUB", nome="Empresa Sub")
        self.obra = Obra.objects.create(
            empresa=empresa,
            codigo="OBR-TST-SUB",
            nome="Obra Sub",
            sigla="SUB",
            ativo=True,
        )
        self.user = User.objects.create_user(username="tst_sub_imp", password="x")
        statuses = list(
            StatusImpedimento.objects.filter(obra=self.obra).order_by("ordem")
        )
        self.assertGreaterEqual(len(statuses), 2)
        self.st_aberto = statuses[0]
        self.ultimo = _ultimo_status_obra(self.obra)
        self.assertIsNotNone(self.ultimo)

    def test_clean_impede_quarto_nivel(self):
        root = Impedimento.objects.create(
            obra=self.obra,
            titulo="Raiz",
            status=self.st_aberto,
            criado_por=self.user,
            prioridade=Impedimento.PRIORIDADE_NORMAL,
        )
        sub = Impedimento.objects.create(
            obra=self.obra,
            parent=root,
            titulo="Sub",
            status=self.st_aberto,
            criado_por=self.user,
            prioridade=Impedimento.PRIORIDADE_NORMAL,
        )
        subsub = Impedimento.objects.create(
            obra=self.obra,
            parent=sub,
            titulo="Sub-sub",
            status=self.st_aberto,
            criado_por=self.user,
            prioridade=Impedimento.PRIORIDADE_NORMAL,
        )
        ilegal = Impedimento(
            obra=self.obra,
            parent=subsub,
            titulo="Nível 4",
            status=self.st_aberto,
            criado_por=self.user,
            prioridade=Impedimento.PRIORIDADE_NORMAL,
        )
        with self.assertRaises(ValidationError):
            ilegal.full_clean()

    def test_has_descendant_not_final_filho_e_neto(self):
        root = Impedimento.objects.create(
            obra=self.obra,
            titulo="R",
            status=self.ultimo,
            criado_por=self.user,
            prioridade=Impedimento.PRIORIDADE_NORMAL,
        )
        sub = Impedimento.objects.create(
            obra=self.obra,
            parent=root,
            titulo="S",
            status=self.st_aberto,
            criado_por=self.user,
            prioridade=Impedimento.PRIORIDADE_NORMAL,
        )
        self.assertTrue(_has_descendant_not_final(root, self.ultimo))
        sub.status = self.ultimo
        sub.save(update_fields=["status"])
        self.assertFalse(_has_descendant_not_final(root, self.ultimo))

        sub.status = self.st_aberto
        sub.save(update_fields=["status"])
        Impedimento.objects.create(
            obra=self.obra,
            parent=sub,
            titulo="Neto",
            status=self.st_aberto,
            criado_por=self.user,
            prioridade=Impedimento.PRIORIDADE_NORMAL,
        )
        self.assertTrue(_has_descendant_not_final(root, self.ultimo))


class ImpedimentosTableFilterTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(codigo="EMP-TST-TBL", nome="Empresa Tbl")
        self.obra = Obra.objects.create(
            empresa=empresa,
            codigo="OBR-TST-TBL",
            nome="Obra Tbl",
            sigla="TBL",
            ativo=True,
        )
        self.user = User.objects.create_user(username="tst_tbl_imp", password="x")
        statuses = list(
            StatusImpedimento.objects.filter(obra=self.obra).order_by("ordem")
        )
        self.st_aberto = statuses[0]

    def test_normalize_prioridade_aceita_alias_critica(self):
        self.assertEqual(
            _normalize_table_prioridade_filter("critica"),
            Impedimento.PRIORIDADE_CRITICA,
        )

    def test_filter_prioridade_critica_na_tabela(self):
        critica = Impedimento.objects.create(
            obra=self.obra,
            titulo="Crítica",
            status=self.st_aberto,
            criado_por=self.user,
            prioridade=Impedimento.PRIORIDADE_CRITICA,
        )
        normal = Impedimento.objects.create(
            obra=self.obra,
            titulo="Normal",
            status=self.st_aberto,
            criado_por=self.user,
            prioridade=Impedimento.PRIORIDADE_NORMAL,
        )
        qs = _impedimentos_table_queryset(
            self.obra, QueryDict("prioridade=critica")
        )
        ids = set(qs.values_list("pk", flat=True))
        self.assertIn(critica.pk, ids)
        self.assertNotIn(normal.pk, ids)

    def test_vencidas_true_filtra_prazo_anterior_a_hoje(self):
        ontem = timezone.localdate() - timedelta(days=1)
        vencida = Impedimento.objects.create(
            obra=self.obra,
            titulo="Vencida",
            status=self.st_aberto,
            criado_por=self.user,
            prioridade=Impedimento.PRIORIDADE_NORMAL,
            prazo=ontem,
        )
        no_prazo = Impedimento.objects.create(
            obra=self.obra,
            titulo="No prazo",
            status=self.st_aberto,
            criado_por=self.user,
            prioridade=Impedimento.PRIORIDADE_NORMAL,
            prazo=timezone.localdate(),
        )
        qs = _impedimentos_table_queryset(
            self.obra, QueryDict("vencidas=true")
        )
        ids = set(qs.values_list("pk", flat=True))
        self.assertIn(vencida.pk, ids)
        self.assertNotIn(no_prazo.pk, ids)

    def test_filter_data_fim_prazo_vencido(self):
        ontem = timezone.localdate() - timedelta(days=1)
        vencida = Impedimento.objects.create(
            obra=self.obra,
            titulo="Vencida",
            status=self.st_aberto,
            criado_por=self.user,
            prioridade=Impedimento.PRIORIDADE_NORMAL,
            prazo=ontem,
        )
        no_prazo = Impedimento.objects.create(
            obra=self.obra,
            titulo="No prazo",
            status=self.st_aberto,
            criado_por=self.user,
            prioridade=Impedimento.PRIORIDADE_NORMAL,
            prazo=timezone.localdate(),
        )
        qs = _impedimentos_table_queryset(
            self.obra, QueryDict(f"data_fim={ontem.isoformat()}")
        )
        ids = set(qs.values_list("pk", flat=True))
        self.assertIn(vencida.pk, ids)
        self.assertNotIn(no_prazo.pk, ids)

    def test_filter_data_inicio_e_fim(self):
        inicio = date(2026, 5, 10)
        meio = date(2026, 5, 15)
        fim = date(2026, 5, 20)
        dentro = Impedimento.objects.create(
            obra=self.obra,
            titulo="Dentro",
            status=self.st_aberto,
            criado_por=self.user,
            prioridade=Impedimento.PRIORIDADE_NORMAL,
            prazo=meio,
        )
        fora = Impedimento.objects.create(
            obra=self.obra,
            titulo="Fora",
            status=self.st_aberto,
            criado_por=self.user,
            prioridade=Impedimento.PRIORIDADE_NORMAL,
            prazo=fim,
        )
        qs = _impedimentos_table_queryset(
            self.obra,
            QueryDict(
                f"data_inicio={inicio.isoformat()}&data_fim={meio.isoformat()}"
            ),
        )
        ids = set(qs.values_list("pk", flat=True))
        self.assertIn(dentro.pk, ids)
        self.assertNotIn(fora.pk, ids)
