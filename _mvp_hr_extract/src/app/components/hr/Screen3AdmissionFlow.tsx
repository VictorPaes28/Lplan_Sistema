import { useState } from "react";
import {
  CheckCircle, Circle, Clock, FileText, UserCheck,
  PenLine, Shield, ChevronRight, Upload, AlertTriangle,
  User, Stethoscope, Building2, BookOpen,
} from "lucide-react";
import { ModalNovoColaborador, type RequisicaoData } from "./ModalNovoColaborador";

const STEPS = [
  { id: 1, label: "Requisição", icon: FileText },
  { id: 2, label: "Coleta de Docs", icon: FileText },
  { id: 3, label: "Aprovação RH", icon: Shield },
  { id: 4, label: "Ass. Contrato", icon: PenLine },
  { id: 5, label: "Ativo", icon: UserCheck },
];

// Sub-grupos da Etapa 2 de coleta de documentos
type DocItem = { name: string; status: "ok" | "pending" | "missing"; obs?: string };
type DocGroup = { id: string; label: string; icon: React.ElementType; color: string; docs: DocItem[] };

const DOC_GROUPS_FERNANDA: DocGroup[] = [
  {
    id: "pessoais",
    label: "Documentos Pessoais",
    icon: User,
    color: "text-blue-600",
    docs: [
      { name: "RG (frente e verso)", status: "ok" },
      { name: "CPF", status: "ok" },
      { name: "Título de Eleitor", status: "missing" },
      { name: "Certidão de Nascimento / Casamento", status: "ok" },
      { name: "PIS / NIS", status: "missing" },
      { name: "CTPS – Carteira de Trabalho", status: "missing" },
    ],
  },
  {
    id: "residencia",
    label: "Comprovantes",
    icon: Building2,
    color: "text-purple-600",
    docs: [
      { name: "Comprovante de endereço (máx. 90 dias)", status: "ok" },
      { name: "Comprovante bancário / dados para pagamento", status: "pending", obs: "Aguardando confirmação do banco" },
    ],
  },
  {
    id: "saude",
    label: "Saúde e Segurança",
    icon: Stethoscope,
    color: "text-red-600",
    docs: [
      { name: "ASO – Atestado de Saúde Ocupacional", status: "missing", obs: "Exame admissional a agendar" },
    ],
  },
  {
    id: "treinamentos",
    label: "Treinamentos e NRs",
    icon: BookOpen,
    color: "text-green-600",
    docs: [
      { name: "NR-35 – Trabalho em Altura", status: "missing", obs: "Obrigatório para o cargo" },
    ],
  },
];

const DOC_GROUPS_RICARDO: DocGroup[] = [
  {
    id: "pessoais",
    label: "Documentos Pessoais",
    icon: User,
    color: "text-blue-600",
    docs: [
      { name: "RG (frente e verso)", status: "ok" },
      { name: "CPF", status: "ok" },
      { name: "Título de Eleitor", status: "ok" },
      { name: "Certidão de Nascimento / Casamento", status: "ok" },
      { name: "PIS / NIS", status: "ok" },
      { name: "CTPS – Carteira de Trabalho", status: "ok" },
    ],
  },
  {
    id: "residencia",
    label: "Comprovantes",
    icon: Building2,
    color: "text-purple-600",
    docs: [
      { name: "Comprovante de endereço (máx. 90 dias)", status: "ok" },
      { name: "Comprovante bancário / dados para pagamento", status: "ok" },
    ],
  },
  {
    id: "saude",
    label: "Saúde e Segurança",
    icon: Stethoscope,
    color: "text-red-600",
    docs: [
      { name: "ASO – Atestado de Saúde Ocupacional", status: "ok" },
    ],
  },
  {
    id: "treinamentos",
    label: "Treinamentos e NRs",
    icon: BookOpen,
    color: "text-green-600",
    docs: [
      { name: "NR-18 – Condições e Meio Ambiente do Trabalho", status: "ok" },
    ],
  },
];

const docGroupsMap: Record<string, DocGroup[]> = {
  a1: DOC_GROUPS_FERNANDA,
  a2: DOC_GROUPS_RICARDO,
};

const DocGroupPanel = ({ group }: { group: DocGroup }) => {
  const Icon = group.icon;
  const total = group.docs.length;
  const done = group.docs.filter((d) => d.status === "ok").length;
  const allDone = done === total;
  const hasMissing = group.docs.some((d) => d.status === "missing");

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <div className={`flex items-center justify-between px-4 py-3 ${allDone ? "bg-green-50 border-b border-green-100" : hasMissing ? "bg-red-50 border-b border-red-100" : "bg-yellow-50 border-b border-yellow-100"}`}>
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${group.color}`} />
          <span className="text-sm font-medium text-gray-800">{group.label}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium tabular-nums ${allDone ? "text-green-600" : hasMissing ? "text-red-600" : "text-yellow-600"}`}>
            {done}/{total}
          </span>
          <div className="w-16 h-1.5 rounded-full bg-gray-200 overflow-hidden">
            <div
              className={`h-full rounded-full ${allDone ? "bg-green-500" : hasMissing ? "bg-red-400" : "bg-yellow-400"}`}
              style={{ width: `${(done / total) * 100}%` }}
            />
          </div>
        </div>
      </div>
      <div className="divide-y divide-gray-50 bg-white">
        {group.docs.map((doc) => (
          <div key={doc.name} className="flex items-center gap-3 px-4 py-2.5">
            {doc.status === "ok" && <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />}
            {doc.status === "pending" && <AlertTriangle className="w-4 h-4 text-yellow-500 flex-shrink-0" />}
            {doc.status === "missing" && <Circle className="w-4 h-4 text-red-300 flex-shrink-0" />}
            <div className="flex-1 min-w-0">
              <span className={`text-sm ${doc.status === "missing" ? "text-gray-500" : "text-gray-800"}`}>{doc.name}</span>
              {doc.obs && <p className="text-xs text-gray-400 mt-0.5">{doc.obs}</p>}
            </div>
            <div className="flex items-center gap-1.5">
              {doc.status !== "ok" && (
                <button className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded border border-gray-200 text-gray-600 hover:border-blue-300 hover:text-blue-600 transition-colors">
                  <Upload className="w-3 h-3" /> Upload
                </button>
              )}
              {doc.status === "ok" && (
                <span className="text-xs text-green-600 font-medium">Recebido</span>
              )}
              {doc.status === "pending" && (
                <span className="text-xs text-yellow-600 font-medium">Pendente</span>
              )}
              {doc.status === "missing" && (
                <span className="text-xs text-red-500 font-medium">Faltando</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const ADMISSIONS = [
  {
    id: "a1",
    name: "Fernanda Lima Souza",
    cargo: "Auxiliar Administrativa",
    obra: "Obra Lapa",
    currentStep: 2,
    startDate: "05/06/2026",
    history: [
      { step: 1, label: "Requisição criada", date: "05/06/2026 09:14", user: "RH — Carla Moreira", done: true },
      { step: 1, label: "Candidato aprovado na entrevista", date: "06/06/2026 14:30", user: "Ger. — Paulo Saraiva", done: true },
      { step: 2, label: "Link de coleta enviado ao candidato", date: "07/06/2026 08:00", user: "Sistema automático", done: true },
      { step: 2, label: "RG, CPF, certidão e endereço recebidos", date: "07/06/2026 15:22", user: "Fernanda Lima Souza", done: true },
      { step: 2, label: "Aguardando: Título de Eleitor, PIS, CTPS, ASO, NR-35", date: "10/06/2026 —", user: "Pendente", done: false },
    ],
  },
  {
    id: "a2",
    name: "Ricardo Souza Neto",
    cargo: "Servente",
    obra: "Obra Tatuapé",
    currentStep: 3,
    startDate: "02/06/2026",
    history: [
      { step: 1, label: "Requisição criada", date: "02/06/2026 10:00", user: "RH — Carla Moreira", done: true },
      { step: 1, label: "Candidato aprovado", date: "03/06/2026 16:00", user: "Ger. — Paulo Saraiva", done: true },
      { step: 2, label: "Todos os documentos coletados (11/11)", date: "06/06/2026 11:45", user: "Ricardo Souza Neto", done: true },
      { step: 3, label: "Em análise pelo RH", date: "09/06/2026 09:00", user: "RH — Carla Moreira", done: false },
    ],
  },
];

type Admission = typeof ADMISSIONS[number];

const StepContent = ({ step, admission }: { step: number; admission: Admission }) => {
  const docGroups = docGroupsMap[admission.id] ?? [];
  const totalDocs = docGroups.flatMap((g) => g.docs).length;
  const doneDocs = docGroups.flatMap((g) => g.docs).filter((d) => d.status === "ok").length;
  const missingCount = totalDocs - doneDocs;

  const contents: Record<number, React.ReactNode> = {
    1: (
      <div className="flex flex-col gap-4">
        <p className="text-sm text-gray-600">
          Requisição criada e aprovada pelo gestor responsável. <strong>{admission.name}</strong> foi selecionado(a) para o cargo.
        </p>
        <div className="grid grid-cols-2 gap-3">
          {[
            ["Solicitante", "RH — Carla Moreira"],
            ["Gestor aprovador", "Paulo Saraiva"],
            ["Data da requisição", admission.startDate],
            ["Motivo", "Nova contratação"],
          ].map(([k, v]) => (
            <div key={k} className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-400">{k}</p>
              <p className="text-sm text-gray-800">{v}</p>
            </div>
          ))}
        </div>
      </div>
    ),
    2: (
      <div className="flex flex-col gap-5">
        {/* Summary bar */}
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-600">
            Coleta de documentos de <strong>{admission.name}</strong>
          </p>
          <div className="flex items-center gap-3">
            <span className={`text-sm font-medium tabular-nums ${missingCount === 0 ? "text-green-600" : "text-red-600"}`}>
              {doneDocs}/{totalDocs} recebidos
            </span>
            {missingCount > 0 && (
              <button className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors">
                Enviar lembrete
              </button>
            )}
          </div>
        </div>

        {/* Doc groups */}
        <div className="flex flex-col gap-3">
          {docGroups.map((group) => (
            <DocGroupPanel key={group.id} group={group} />
          ))}
        </div>

        {missingCount === 0 && (
          <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-lg p-4">
            <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-green-800">Todos os documentos recebidos</p>
              <p className="text-xs text-green-600 mt-0.5">Pronto para avançar para a etapa de Aprovação RH</p>
            </div>
            <button className="ml-auto px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors">
              Avançar para aprovação →
            </button>
          </div>
        )}
      </div>
    ),
    3: (
      <div className="flex flex-col gap-4">
        <p className="text-sm text-gray-600">Documentação completa. Aguardando análise e aprovação do RH antes da assinatura do contrato.</p>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-start gap-3">
          <Clock className="w-4 h-4 text-yellow-600 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm text-yellow-800 font-medium">Em análise — Carla Moreira (RH)</p>
            <p className="text-xs text-yellow-700 mt-0.5">Prazo: 11/06/2026 · Documentos conferidos: 11/11</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {[
            ["CPF válido", "ok"],
            ["CTPS sem pendências", "ok"],
            ["ASO dentro da validade", "ok"],
            ["NR obrigatória concluída", "ok"],
          ].map(([label, status]) => (
            <div key={label} className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-green-50 border border-green-100">
              <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
              <span className="text-sm text-green-700">{label}</span>
            </div>
          ))}
        </div>
        <div className="flex gap-3 pt-1">
          <button className="px-5 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors">
            ✓ Aprovar documentação
          </button>
          <button className="px-5 py-2 border border-red-300 text-red-600 hover:bg-red-50 text-sm font-medium rounded-lg transition-colors">
            ✕ Devolver com ressalvas
          </button>
        </div>
      </div>
    ),
    4: (
      <div className="flex flex-col gap-4">
        <p className="text-sm text-gray-600">Documentação aprovada. Contrato gerado e aguardando assinatura das partes.</p>
        <div className="grid grid-cols-2 gap-3">
          {[
            ["Tipo de contrato", "CLT"],
            ["Cargo", admission.cargo],
            ["Obra", admission.obra],
            ["Data de início", "15/06/2026"],
          ].map(([k, v]) => (
            <div key={k} className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-400">{k}</p>
              <p className="text-sm text-gray-800">{v}</p>
            </div>
          ))}
        </div>
        <div className="flex gap-3">
          <button className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
            <PenLine className="w-4 h-4" /> Enviar contrato para assinatura
          </button>
          <button className="inline-flex items-center gap-2 px-4 py-2 border border-gray-200 hover:bg-gray-50 text-gray-700 text-sm font-medium rounded-lg transition-colors">
            <FileText className="w-4 h-4" /> Baixar contrato (.pdf)
          </button>
        </div>
      </div>
    ),
    5: (
      <div className="flex flex-col gap-4">
        <div className="bg-green-50 border border-green-200 rounded-lg p-5 flex items-center gap-4">
          <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
            <UserCheck className="w-5 h-5 text-green-600" />
          </div>
          <div>
            <p className="text-sm font-medium text-green-800">Admissão concluída com sucesso</p>
            <p className="text-xs text-green-600 mt-0.5">{admission.name} agora aparece como <strong>Ativo</strong> na lista de Colaboradores.</p>
          </div>
        </div>
      </div>
    ),
  };
  return <>{contents[step] || null}</>;
};

export function Screen3AdmissionFlow() {
  const [admissions, setAdmissions] = useState(ADMISSIONS);
  const [selectedAdmission, setSelectedAdmission] = useState(ADMISSIONS[0]);
  const [showModal, setShowModal] = useState(false);

  const handleNovaRequisicao = (data: RequisicaoData) => {
    const nova = {
      id: `a${Date.now()}`,
      name: data.nome,
      cargo: data.cargo,
      obra: data.obra,
      currentStep: 1,
      startDate: new Date().toLocaleDateString("pt-BR"),
      history: [
        {
          step: 1,
          label: "Requisição criada",
          date: `${new Date().toLocaleDateString("pt-BR")} ${new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`,
          user: `RH — ${data.solicitante}`,
          done: true,
        },
        {
          step: 1,
          label: `Aguardando aprovação do gestor: ${data.gestor}`,
          date: "Pendente",
          user: data.gestor,
          done: false,
        },
      ],
    };
    setAdmissions((prev) => [...prev, nova]);
    setSelectedAdmission(nova as any);
  };

  return (
    <div className="flex flex-col gap-6">
      {showModal && (
        <ModalNovoColaborador
          onClose={() => setShowModal(false)}
          onSubmit={(data) => {
            handleNovaRequisicao(data);
            setShowModal(false);
          }}
        />
      )}

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-gray-900">Fluxo de Admissão</h1>
          <p className="text-sm text-gray-500 mt-0.5">Entrada única para contratar novos colaboradores — da requisição até a ativação</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          + Nova Admissão
        </button>
      </div>

      {/* Admission cards selector */}
      <div className="flex gap-3 flex-wrap">
        {admissions.map((a) => {
          const active = selectedAdmission.id === a.id;
          return (
            <button
              key={a.id}
              onClick={() => setSelectedAdmission(a as any)}
              className={`flex-1 min-w-[180px] text-left px-4 py-3 rounded-xl border transition-colors ${active ? "border-blue-300 bg-blue-50" : "border-gray-200 bg-white hover:border-gray-300"}`}
            >
              <p className={`text-sm font-medium ${active ? "text-blue-800" : "text-gray-800"}`}>{a.name}</p>
              <p className="text-xs text-gray-500 mt-0.5">{a.cargo} · {a.obra}</p>
              <div className="flex items-center gap-2 mt-2">
                <div className="flex gap-0.5">
                  {STEPS.map((s) => (
                    <div key={s.id} className={`w-4 h-1 rounded-full ${s.id < a.currentStep ? "bg-blue-500" : s.id === a.currentStep ? "bg-blue-300" : "bg-gray-200"}`} />
                  ))}
                </div>
                <span className={`text-xs ${active ? "text-blue-600" : "text-gray-500"}`}>
                  {STEPS.find((s) => s.id === a.currentStep)?.label}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Stepper + content */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        {/* Step bar */}
        <div className="flex items-start justify-between mb-8 relative">
          <div className="absolute h-px bg-gray-200 z-0" style={{ top: "20px", left: "10%", right: "10%" }} />
          {STEPS.map((step) => {
            const done = step.id < selectedAdmission.currentStep;
            const active = step.id === selectedAdmission.currentStep;
            const Icon = step.icon;
            return (
              <div key={step.id} className="flex flex-col items-center gap-2 z-10 flex-1">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-colors ${
                  done ? "bg-blue-600 border-blue-600" :
                  active ? "bg-white border-blue-600" :
                  "bg-white border-gray-200"
                }`}>
                  {done
                    ? <CheckCircle className="w-5 h-5 text-white" />
                    : <Icon className={`w-4 h-4 ${active ? "text-blue-600" : "text-gray-300"}`} />}
                </div>
                <p className={`text-xs font-medium text-center leading-tight ${active ? "text-blue-700" : done ? "text-gray-700" : "text-gray-400"}`}>
                  {step.label}
                </p>
              </div>
            );
          })}
        </div>

        {/* Step content */}
        <div className="border-t border-gray-100 pt-6">
          <div className="flex items-center gap-2 mb-5">
            <span className="text-xs font-semibold text-blue-600 uppercase tracking-wide">
              Etapa {selectedAdmission.currentStep}
            </span>
            <ChevronRight className="w-3 h-3 text-gray-300" />
            <span className="text-sm font-medium text-gray-800">
              {STEPS.find((s) => s.id === selectedAdmission.currentStep)?.label}
            </span>
          </div>
          <StepContent step={selectedAdmission.currentStep} admission={selectedAdmission as any} />
        </div>
      </div>

      {/* Timeline */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-gray-900 mb-4">Histórico</h3>
        <div className="flex flex-col">
          {selectedAdmission.history.map((h, i) => (
            <div key={i} className="flex gap-4 pb-4 last:pb-0">
              <div className="flex flex-col items-center">
                <div className={`w-3 h-3 rounded-full flex-shrink-0 mt-0.5 ${h.done ? "bg-blue-500" : "bg-gray-200"}`} />
                {i < selectedAdmission.history.length - 1 && (
                  <div className="w-px flex-1 bg-gray-100 mt-1" />
                )}
              </div>
              <div className="flex-1 pb-1">
                <p className={`text-sm ${h.done ? "text-gray-800" : "text-gray-400"}`}>{h.label}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs text-gray-400">{h.date}</span>
                  <span className="text-gray-200">·</span>
                  <span className="text-xs text-gray-400">{h.user}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
