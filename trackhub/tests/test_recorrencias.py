"""
Testes de recorrência TrackHub sem depender da data real do sistema.

Chama processar_todas_recorrencias(hoje=...) diretamente (sem management command).
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from mapa_obras.models import Obra

from trackhub.models import Pendencia, PendenciaRecorrente
from trackhub.recurrence_jobs import processar_todas_recorrencias

User = get_user_model()


def _snap_etapas_simples():
    return [
        {
            "titulo": "Etapa A",
            "responsavel_interno_id": None,
            "observacao": "",
            "requer_assinatura": False,
            "prazo_offset_dias": 1,
        },
        {
            "titulo": "Etapa B",
            "responsavel_interno_id": None,
            "observacao": "",
            "requer_assinatura": False,
            "prazo_offset_dias": None,
        },
    ]


def _snap_etapas_sem_offsets():
    """Duas etapas sem prazo_offset — prazo de etapa fica None quando não há intervalo na série."""
    return [
        {
            "titulo": "Etapa A",
            "responsavel_interno_id": None,
            "observacao": "",
            "requer_assinatura": False,
            "prazo_offset_dias": None,
        },
        {
            "titulo": "Etapa B",
            "responsavel_interno_id": None,
            "observacao": "",
            "requer_assinatura": False,
            "prazo_offset_dias": None,
        },
    ]


@patch("trackhub.views._notificar_criacao_pendencia", new_callable=MagicMock)
class RecorrenciasProcessamentoTestCase(TestCase):
    """
    Uma pendência por execução; prazo = data_ocorrência + (prazo_original − data_criacao_original).
    Etapas: status pendente; prazo da etapa = data_ocorrência + offset do snapshot.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="rectest_user",
            email="rectest@example.com",
            password="pass-test-123",
        )
        self.obra = Obra.objects.create(
            codigo_sienge="TEST-REC-UNIQUE-001",
            nome="Obra teste recorrências",
        )
        self.etapas_snapshot = _snap_etapas_simples()
        self.data_criacao_original = date(2026, 5, 10)
        self.prazo_original = date(2026, 5, 17)
        self.intervalo = self.prazo_original - self.data_criacao_original

    def _base_kwargs(self):
        return {
            "obra": self.obra,
            "criado_por": self.user,
            "titulo": "Série teste",
            "descricao": "",
            "tipo": "tarefa",
            "prioridade": "normal",
            "prazo_original": self.prazo_original,
            "data_criacao_original": self.data_criacao_original,
            "prazo_offset_dias": self.intervalo.days,
            "etapas_snapshot": self.etapas_snapshot,
            "ativo": True,
        }

    def _assert_pendencia_ocorrencia_e_etapas(
        self,
        p: Pendencia,
        esperado_dia_ocorrencia: date,
        *,
        intervalo: timedelta | None = None,
    ):
        self.assertIsNotNone(p)
        inter = intervalo if intervalo is not None else self.intervalo
        esperado_prazo = esperado_dia_ocorrencia + inter
        self.assertEqual(
            p.prazo,
            esperado_prazo,
            f"Prazo pendência: esperado {esperado_prazo}, obtido {p.prazo}",
        )
        self.assertEqual(
            p.etapas.count(),
            len(self.etapas_snapshot),
            "Número de etapas deve igualar o template",
        )
        etapas = list(p.etapas.order_by("ordem"))
        self.assertEqual(len(etapas), len(self.etapas_snapshot))
        for e in etapas:
            self.assertEqual(
                e.status,
                "pendente",
                f"Etapa {e.titulo} deve ficar pendente, obtido {e.status}",
            )
        self.assertEqual(etapas[0].titulo, "Etapa A")
        self.assertEqual(
            etapas[0].prazo,
            esperado_dia_ocorrencia + timedelta(days=1),
            "Etapa com offset 1: prazo = data_ocorrência + 1 dia",
        )
        self.assertIsNone(etapas[1].prazo)

    def _assert_pendencia_sem_prazo_etapas_sem_prazo(self, p: Pendencia, n_etapas: int):
        self.assertIsNone(p.prazo, "Pendência sem série de prazo deve ficar com prazo=None")
        self.assertEqual(p.etapas.count(), n_etapas)
        for e in p.etapas.order_by("ordem"):
            self.assertEqual(e.status, "pendente")
            self.assertIsNone(
                e.prazo,
                f"Etapa {e.titulo} sem offset no snapshot deve ter prazo=None",
            )

    def _rodar_n_vezes(
        self,
        serie: PendenciaRecorrente,
        datas_hoje: list[date],
        *,
        esperados_proxima_depois: list[date] | None = None,
    ) -> list[Pendencia]:
        if esperados_proxima_depois is not None:
            self.assertEqual(
                len(esperados_proxima_depois),
                len(datas_hoje),
                "esperados_proxima_depois deve ter uma entrada por execução",
            )
        criadas: list[Pendencia] = []
        for idx, hoje in enumerate(datas_hoje):
            n_antes = Pendencia.objects.filter(recorrencia_serie=serie).count()
            total = processar_todas_recorrencias(hoje=hoje, max_burst_por_serie=1)
            self.assertEqual(
                total,
                1,
                f"Esperada 1 ocorrência por chamada com max_burst=1 (hoje={hoje})",
            )
            n_depois = Pendencia.objects.filter(recorrencia_serie=serie).count()
            self.assertEqual(
                n_depois,
                n_antes + 1,
                f"Deve criar exatamente 1 pendência (hoje={hoje})",
            )
            serie.refresh_from_db()
            if esperados_proxima_depois is not None:
                self.assertEqual(
                    serie.proxima_execucao,
                    esperados_proxima_depois[idx],
                    f"proxima_execucao após ocorrência {idx + 1} (hoje={hoje})",
                )
            p = Pendencia.objects.filter(recorrencia_serie=serie).order_by("-pk").first()
            assert p is not None
            criadas.append(p)
        return criadas

    # --- 1. DAILY ---
    def test_daily_cinco_ocorrencias_sequencia_prazos(self, _mock_notif):
        d0 = date(2026, 5, 10)
        serie = PendenciaRecorrente.objects.create(
            **self._base_kwargs(),
            regra=PendenciaRecorrente.REGRA_DAILY,
            proxima_execucao=d0,
            parametros_json={},
        )
        datas_hoje = [d0 + timedelta(days=i) for i in range(5)]
        esperados_prox = [d0 + timedelta(days=i + 1) for i in range(5)]
        criadas = self._rodar_n_vezes(serie, datas_hoje, esperados_proxima_depois=esperados_prox)
        esperados_ocorr = [d0 + timedelta(days=i) for i in range(5)]
        for i, p in enumerate(criadas):
            self.assertEqual(p.prazo, esperados_ocorr[i] + self.intervalo)
            self._assert_pendencia_ocorrencia_e_etapas(p, esperados_ocorr[i])
        serie.refresh_from_db()
        self.assertEqual(serie.proxima_execucao, d0 + timedelta(days=5))

    # --- 2. WEEKDAYS (série a começar numa segunda) ---
    def test_weekdays_so_seg_a_sex_pula_fim_de_semana(self, _mock_notif):
        d0 = date(2026, 5, 11)  # segunda-feira
        self.assertEqual(d0.weekday(), 0)
        serie = PendenciaRecorrente.objects.create(
            **self._base_kwargs(),
            regra=PendenciaRecorrente.REGRA_WEEKDAYS,
            proxima_execucao=d0,
            parametros_json={},
        )
        esperados_ocorr = [
            date(2026, 5, 11),  # seg
            date(2026, 5, 12),  # ter
            date(2026, 5, 13),  # qua
            date(2026, 5, 14),  # qui
            date(2026, 5, 15),  # sex — sáb/dom saltados a seguir
        ]
        esperados_prox = [
            date(2026, 5, 12),
            date(2026, 5, 13),
            date(2026, 5, 14),
            date(2026, 5, 15),
            date(2026, 5, 18),  # após sex, próximo dia útil é segunda
        ]
        criadas = self._rodar_n_vezes(serie, esperados_ocorr, esperados_proxima_depois=esperados_prox)
        for occ, p in zip(esperados_ocorr, criadas):
            self.assertLess(occ.weekday(), 5, f"{occ} deve ser dia útil")
            self.assertEqual(p.prazo, occ + self.intervalo)
            self._assert_pendencia_ocorrencia_e_etapas(p, occ)

    # --- 3. WEEKLY (quarta-feira, intervalo de 7 dias entre ocorrências) ---
    def test_weekly_quarta_sete_dias_entre_ocorrencias(self, _mock_notif):
        d0 = date(2026, 5, 13)  # quarta-feira (weekday 2)
        self.assertEqual(d0.weekday(), 2)
        serie = PendenciaRecorrente.objects.create(
            **self._base_kwargs(),
            regra=PendenciaRecorrente.REGRA_WEEKLY,
            proxima_execucao=d0,
            parametros_json={"dias_semana": [2]},
            dia_semana=2,
        )
        esperados_ocorr = [d0 + timedelta(days=7 * i) for i in range(5)]
        esperados_prox = [
            date(2026, 5, 20),
            date(2026, 5, 27),
            date(2026, 6, 3),
            date(2026, 6, 10),
            date(2026, 6, 17),
        ]
        criadas = self._rodar_n_vezes(serie, esperados_ocorr, esperados_proxima_depois=esperados_prox)
        for i in range(1, len(esperados_ocorr)):
            delta = esperados_ocorr[i] - esperados_ocorr[i - 1]
            self.assertEqual(delta.days, 7)
        for occ, p in zip(esperados_ocorr, criadas):
            self.assertEqual(occ.weekday(), 2)
            self.assertEqual(p.prazo, occ + self.intervalo)
            self._assert_pendencia_ocorrencia_e_etapas(p, occ)
        serie.refresh_from_db()
        self.assertEqual(serie.proxima_execucao, date(2026, 6, 17))

    # --- 4. MONTHLY dia 10 + caso especial dia 30 com prazo +2 ---
    def test_monthly_dia_10_proxima_mes_seguinte(self, _mock_notif):
        d0 = date(2026, 5, 10)
        serie = PendenciaRecorrente.objects.create(
            **self._base_kwargs(),
            regra=PendenciaRecorrente.REGRA_MONTHLY,
            proxima_execucao=d0,
            parametros_json={"dias_mes": [10]},
            dia_mes=10,
        )
        esperados_ocorr = [
            date(2026, 5, 10),
            date(2026, 6, 10),
            date(2026, 7, 10),
            date(2026, 8, 10),
            date(2026, 9, 10),
        ]
        esperados_prox = [
            date(2026, 6, 10),
            date(2026, 7, 10),
            date(2026, 8, 10),
            date(2026, 9, 10),
            date(2026, 10, 10),
        ]
        criadas = self._rodar_n_vezes(serie, esperados_ocorr, esperados_proxima_depois=esperados_prox)
        for occ, p in zip(esperados_ocorr, criadas):
            self.assertEqual(occ.day, 10)
            self.assertEqual(p.prazo, occ + self.intervalo)
            self._assert_pendencia_ocorrencia_e_etapas(p, occ)

    def test_monthly_dia_30_fevereiro_ultimo_dia_e_prazo_coerente(self, _mock_notif):
        """Próximo mês sem dia 30 → usa último dia; prazo = ocorrência + intervalo fixo (+2)."""
        intervalo = timedelta(days=2)
        kwargs = {
            **self._base_kwargs(),
            "data_criacao_original": date(2026, 1, 30),
            "prazo_original": date(2026, 2, 1),
            "prazo_offset_dias": intervalo.days,
            "regra": PendenciaRecorrente.REGRA_MONTHLY,
            "proxima_execucao": date(2026, 1, 30),
            "parametros_json": {"dias_mes": [30]},
            "dia_mes": 30,
        }
        serie = PendenciaRecorrente.objects.create(**kwargs)
        esperados_ocorr = [date(2026, 1, 30), date(2026, 2, 28), date(2026, 3, 30)]
        datas_hoje = list(esperados_ocorr)
        esperados_prox = [date(2026, 2, 28), date(2026, 3, 30), date(2026, 4, 30)]
        criadas = self._rodar_n_vezes(serie, datas_hoje, esperados_proxima_depois=esperados_prox)
        for occ, p in zip(esperados_ocorr, criadas):
            esperado_prazo = occ + intervalo
            self.assertEqual(p.prazo, esperado_prazo)
            self._assert_pendencia_ocorrencia_e_etapas(p, occ, intervalo=intervalo)

    # --- 5. YEARLY 15/03 ---
    def test_yearly_15_marco_anual(self, _mock_notif):
        d0 = date(2026, 3, 15)
        serie = PendenciaRecorrente.objects.create(
            **self._base_kwargs(),
            regra=PendenciaRecorrente.REGRA_YEARLY,
            proxima_execucao=d0,
            parametros_json={"datas_ano": [{"m": 3, "d": 15}]},
            mes=3,
            dia_mes=15,
        )
        esperados_ocorr = [date(2026 + i, 3, 15) for i in range(5)]
        esperados_prox = [date(2027 + i, 3, 15) for i in range(5)]
        criadas = self._rodar_n_vezes(serie, esperados_ocorr, esperados_proxima_depois=esperados_prox)
        for occ, p in zip(esperados_ocorr, criadas):
            self.assertEqual((occ.month, occ.day), (3, 15))
            self.assertEqual(p.prazo, occ + self.intervalo)
            self._assert_pendencia_ocorrencia_e_etapas(p, occ)
        serie.refresh_from_db()
        self.assertEqual(serie.proxima_execucao, date(2031, 3, 15))

    # --- 6. PERSONALIZADO SEMANAL: segunda e quinta (primeira ocorrência na quinta) ---
    def test_weekly_segunda_e_quinta_sequencia(self, _mock_notif):
        d0 = date(2026, 5, 14)  # quinta — primeira execução após terça de criação do agendamento
        serie = PendenciaRecorrente.objects.create(
            **self._base_kwargs(),
            regra=PendenciaRecorrente.REGRA_WEEKLY,
            proxima_execucao=d0,
            parametros_json={"dias_semana": [0, 3]},  # seg, qui
            dia_semana=0,
        )
        esperados_ocorr = [
            date(2026, 5, 14),  # qui
            date(2026, 5, 18),  # seg
            date(2026, 5, 21),  # qui
            date(2026, 5, 25),  # seg
            date(2026, 5, 28),  # qui
        ]
        esperados_prox = [
            date(2026, 5, 18),
            date(2026, 5, 21),
            date(2026, 5, 25),
            date(2026, 5, 28),
            date(2026, 6, 1),
        ]
        criadas = self._rodar_n_vezes(serie, esperados_ocorr, esperados_proxima_depois=esperados_prox)
        for occ, p in zip(esperados_ocorr, criadas):
            self.assertIn(occ.weekday(), (0, 3), f"{occ} deve ser segunda ou quinta")
            self.assertEqual(p.prazo, occ + self.intervalo)
            self._assert_pendencia_ocorrencia_e_etapas(p, occ)

    # --- 7. PERSONALIZADO MENSAL: dias 5 e 20 ---
    def test_monthly_dias_5_e_20_sequencia(self, _mock_notif):
        d0 = date(2026, 1, 5)
        serie = PendenciaRecorrente.objects.create(
            **self._base_kwargs(),
            regra=PendenciaRecorrente.REGRA_MONTHLY,
            proxima_execucao=d0,
            parametros_json={"dias_mes": [5, 20]},
            dia_mes=5,
        )
        esperados_ocorr = [
            date(2026, 1, 5),
            date(2026, 1, 20),
            date(2026, 2, 5),
            date(2026, 2, 20),
            date(2026, 3, 5),
        ]
        esperados_prox = [
            date(2026, 1, 20),
            date(2026, 2, 5),
            date(2026, 2, 20),
            date(2026, 3, 5),
            date(2026, 3, 20),
        ]
        criadas = self._rodar_n_vezes(serie, esperados_ocorr, esperados_proxima_depois=esperados_prox)
        for occ, p in zip(esperados_ocorr, criadas):
            self.assertIn(occ.day, (5, 20))
            self.assertEqual(p.prazo, occ + self.intervalo)
            self._assert_pendencia_ocorrencia_e_etapas(p, occ)

    # --- 8. PERSONALIZADO ANUAL: 10/03 e 10/09 ---
    def test_yearly_10_marco_e_10_setembro_sequencia(self, _mock_notif):
        d0 = date(2026, 3, 10)
        serie = PendenciaRecorrente.objects.create(
            **self._base_kwargs(),
            regra=PendenciaRecorrente.REGRA_YEARLY,
            proxima_execucao=d0,
            parametros_json={"datas_ano": [{"m": 3, "d": 10}, {"m": 9, "d": 10}]},
            mes=3,
            dia_mes=10,
        )
        esperados_ocorr = [
            date(2026, 3, 10),
            date(2026, 9, 10),
            date(2027, 3, 10),
            date(2027, 9, 10),
            date(2028, 3, 10),
        ]
        esperados_prox = [
            date(2026, 9, 10),
            date(2027, 3, 10),
            date(2027, 9, 10),
            date(2028, 3, 10),
            date(2028, 9, 10),
        ]
        criadas = self._rodar_n_vezes(serie, esperados_ocorr, esperados_proxima_depois=esperados_prox)
        for occ, p in zip(esperados_ocorr, criadas):
            self.assertTrue(
                (occ.month, occ.day) in ((3, 10), (9, 10)),
                f"Ocorrência {occ} fora das datas anuais configuradas",
            )
            self.assertEqual(p.prazo, occ + self.intervalo)
            self._assert_pendencia_ocorrencia_e_etapas(p, occ)

    # --- Edge: anual 29/02 (bissexto vs último dia de fevereiro) ---
    def test_yearly_29_fevereiro_bissexto_e_clamp(self, _mock_notif):
        """
        Regra anual 29/02: em anos não bissextos usa 28/02.
        Entre 2030 e 2032 o motor agenda 28/02/2031 (âncora anual), depois 29/02/2032.
        """
        d0 = date(2028, 2, 29)
        serie = PendenciaRecorrente.objects.create(
            **self._base_kwargs(),
            regra=PendenciaRecorrente.REGRA_YEARLY,
            proxima_execucao=d0,
            parametros_json={"datas_ano": [{"m": 2, "d": 29}]},
            mes=2,
            dia_mes=29,
        )
        esperados_ocorr = [
            date(2028, 2, 29),
            date(2029, 2, 28),
            date(2030, 2, 28),
            date(2031, 2, 28),
            date(2032, 2, 29),
        ]
        esperados_prox = [
            date(2029, 2, 28),
            date(2030, 2, 28),
            date(2031, 2, 28),
            date(2032, 2, 29),
            date(2033, 2, 28),
        ]
        criadas = self._rodar_n_vezes(serie, esperados_ocorr, esperados_proxima_depois=esperados_prox)

        self.assertEqual(criadas[0].prazo, date(2028, 2, 29) + self.intervalo)
        self.assertEqual(criadas[1].prazo, date(2029, 2, 28) + self.intervalo)
        self.assertEqual(criadas[2].prazo, date(2030, 2, 28) + self.intervalo)
        self.assertEqual(criadas[4].prazo, date(2032, 2, 29) + self.intervalo)

        for occ, p in zip(esperados_ocorr, criadas):
            self._assert_pendencia_ocorrencia_e_etapas(p, occ)

        serie.refresh_from_db()
        self.assertEqual(serie.proxima_execucao, date(2033, 2, 28))

    # --- Edge: série sem prazo_original / data_criacao_original ---
    def test_serie_sem_prazo_original_pendencia_e_etapas_sem_prazo(self, _mock_notif):
        snap = _snap_etapas_sem_offsets()
        d0 = date(2035, 6, 1)
        serie = PendenciaRecorrente.objects.create(
            obra=self.obra,
            criado_por=self.user,
            titulo="Série sem prazo",
            descricao="",
            tipo="tarefa",
            prioridade="normal",
            prazo_original=None,
            data_criacao_original=None,
            prazo_offset_dias=None,
            regra=PendenciaRecorrente.REGRA_DAILY,
            proxima_execucao=d0,
            parametros_json={},
            etapas_snapshot=snap,
            ativo=True,
        )
        datas_hoje = [d0 + timedelta(days=i) for i in range(3)]
        esperados_prox = [d0 + timedelta(days=i + 1) for i in range(3)]
        criadas = self._rodar_n_vezes(serie, datas_hoje, esperados_proxima_depois=esperados_prox)

        for p in criadas:
            self._assert_pendencia_sem_prazo_etapas_sem_prazo(p, n_etapas=len(snap))

        serie.refresh_from_db()
        self.assertEqual(serie.proxima_execucao, d0 + timedelta(days=3))

    def test_timezone_localdate_mock_sem_passar_hoje(self, _mock_notif):
        """Se não passar hoje, processar_todas_recorrencias usa timezone.localdate()."""
        fake_hoje = date(2030, 1, 15)
        d0 = date(2030, 1, 10)
        serie = PendenciaRecorrente.objects.create(
            **self._base_kwargs(),
            regra=PendenciaRecorrente.REGRA_DAILY,
            proxima_execucao=d0,
            parametros_json={},
        )
        with patch("trackhub.recurrence_jobs.timezone.localdate", return_value=fake_hoje):
            total = processar_todas_recorrencias(max_burst_por_serie=1)
        self.assertEqual(total, 1)
        p = Pendencia.objects.filter(recorrencia_serie=serie).first()
        self.assertIsNotNone(p)
        self.assertEqual(p.prazo, d0 + self.intervalo)

    def test_date_today_mock_em_ref_date_snapshot(self, _mock_notif):
        """ref_date_para_etapas_snapshot usa timezone.localdate() como fallback."""
        from trackhub.recurrence_jobs import ref_date_para_etapas_snapshot

        fake_today = date(2029, 3, 1)
        pend = MagicMock()
        pend.prazo = None
        with patch("trackhub.recurrence_jobs.timezone.localdate", return_value=fake_today):
            ref = ref_date_para_etapas_snapshot(pend, None)
        self.assertEqual(ref, fake_today)
