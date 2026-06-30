import { useState } from "react";
import { X, ChevronRight, User, Briefcase, Building2, FileText, CheckCircle } from "lucide-react";
import { OBRAS } from "./data";

type Props = {
  onClose: () => void;
  onSubmit: (data: RequisicaoData) => void;
};

export type RequisicaoData = {
  nome: string;
  cpf: string;
  cargo: string;
  obra: string;
  tipoContrato: string;
  salario: string;
  dataInicio: string;
  solicitante: string;
  gestor: string;
  motivo: string;
  observacoes: string;
};

const CARGOS = [
  "Pedreiro", "Servente", "Mestre de Obras", "Encarregado de Obras",
  "Engenheiro de Obras", "Auxiliar Administrativo", "Eletricista",
  "Encanador", "Armador", "Carpinteiro", "Motorista",
];

const CONTRATOS = ["CLT", "Temporário", "Estágio", "Pessoa Jurídica"];
const MOTIVOS = ["Nova contratação", "Substituição", "Expansão de equipe", "Projeto específico"];

const Field = ({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) => (
  <div className="flex flex-col gap-1">
    <label className="text-xs font-medium text-gray-600">
      {label} {required && <span className="text-red-500">*</span>}
    </label>
    {children}
  </div>
);

const inputCls = "w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent";
const selectCls = "w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none";

const STEPS = [
  { id: 1, label: "Candidato", icon: User },
  { id: 2, label: "Vaga", icon: Briefcase },
  { id: 3, label: "Contrato", icon: FileText },
  { id: 4, label: "Confirmação", icon: CheckCircle },
];

export function ModalNovoColaborador({ onClose, onSubmit }: Props) {
  const [step, setStep] = useState(1);
  const [data, setData] = useState<RequisicaoData>({
    nome: "",
    cpf: "",
    cargo: "",
    obra: "",
    tipoContrato: "CLT",
    salario: "",
    dataInicio: "",
    solicitante: "Carla Moreira",
    gestor: "",
    motivo: "Nova contratação",
    observacoes: "",
  });

  const set = (field: keyof RequisicaoData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setData((d) => ({ ...d, [field]: e.target.value }));

  const canAdvance = () => {
    if (step === 1) return data.nome.trim() !== "" && data.cpf.trim() !== "";
    if (step === 2) return data.cargo !== "" && data.obra !== "" && data.gestor !== "";
    if (step === 3) return data.dataInicio !== "" && data.salario !== "";
    return true;
  };

  const handleNext = () => { if (canAdvance() && step < 4) setStep(step + 1); };
  const handleBack = () => { if (step > 1) setStep(step - 1); };

  const handleSubmit = () => {
    onSubmit(data);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 flex flex-col max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-gray-100">
          <div>
            <h2 className="text-gray-900">Nova Requisição de Contratação</h2>
            <p className="text-xs text-gray-500 mt-0.5">Etapa 1 do fluxo de admissão — Requisição</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Stepper */}
        <div className="px-6 py-4 border-b border-gray-100 bg-gray-50">
          <div className="flex items-center justify-between">
            {STEPS.map((s, i) => {
              const done = s.id < step;
              const active = s.id === step;
              const Icon = s.icon;
              return (
                <div key={s.id} className="flex items-center flex-1">
                  <div className="flex flex-col items-center gap-1 flex-shrink-0">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center border-2 transition-all ${
                      done ? "bg-blue-600 border-blue-600" :
                      active ? "bg-white border-blue-600" :
                      "bg-white border-gray-200"
                    }`}>
                      {done
                        ? <CheckCircle className="w-4 h-4 text-white" />
                        : <Icon className={`w-3.5 h-3.5 ${active ? "text-blue-600" : "text-gray-300"}`} />}
                    </div>
                    <span className={`text-xs whitespace-nowrap font-medium ${active ? "text-blue-700" : done ? "text-gray-700" : "text-gray-400"}`}>
                      {s.label}
                    </span>
                  </div>
                  {i < STEPS.length - 1 && (
                    <div className={`flex-1 h-px mx-3 mb-4 transition-colors ${done ? "bg-blue-400" : "bg-gray-200"}`} />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {step === 1 && (
            <div className="flex flex-col gap-5">
              <div className="flex items-center gap-2 mb-1">
                <div className="w-7 h-7 rounded-lg bg-blue-100 flex items-center justify-center">
                  <User className="w-3.5 h-3.5 text-blue-600" />
                </div>
                <h3 className="text-gray-800">Dados do Candidato</h3>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <Field label="Nome completo" required>
                    <input className={inputCls} placeholder="Ex: João Silva Santos" value={data.nome} onChange={set("nome")} />
                  </Field>
                </div>
                <Field label="CPF" required>
                  <input className={inputCls} placeholder="000.000.000-00" value={data.cpf} onChange={set("cpf")} />
                </Field>
                <Field label="Solicitante (RH)">
                  <input className={inputCls} value={data.solicitante} onChange={set("solicitante")} />
                </Field>
              </div>

              <div className="bg-blue-50 border border-blue-100 rounded-lg p-4">
                <p className="text-xs text-blue-700">
                  <span className="font-semibold">Próxima etapa:</span> Após criar a requisição, o candidato receberá um link para enviar sua documentação. Os documentos exigidos são definidos na aba <em>Config. Documentos</em>.
                </p>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="flex flex-col gap-5">
              <div className="flex items-center gap-2 mb-1">
                <div className="w-7 h-7 rounded-lg bg-purple-100 flex items-center justify-center">
                  <Briefcase className="w-3.5 h-3.5 text-purple-600" />
                </div>
                <h3 className="text-gray-800">Informações da Vaga</h3>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Cargo" required>
                  <div className="relative">
                    <select className={selectCls} value={data.cargo} onChange={set("cargo")}>
                      <option value="">Selecione o cargo</option>
                      {CARGOS.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                </Field>
                <Field label="Obra" required>
                  <div className="relative">
                    <select className={selectCls} value={data.obra} onChange={set("obra")}>
                      <option value="">Selecione a obra</option>
                      {OBRAS.map((o) => <option key={o} value={o}>{o}</option>)}
                    </select>
                  </div>
                </Field>
                <Field label="Gestor responsável" required>
                  <input className={inputCls} placeholder="Nome do gestor" value={data.gestor} onChange={set("gestor")} />
                </Field>
                <Field label="Motivo da contratação">
                  <div className="relative">
                    <select className={selectCls} value={data.motivo} onChange={set("motivo")}>
                      {MOTIVOS.map((m) => <option key={m} value={m}>{m}</option>)}
                    </select>
                  </div>
                </Field>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="flex flex-col gap-5">
              <div className="flex items-center gap-2 mb-1">
                <div className="w-7 h-7 rounded-lg bg-green-100 flex items-center justify-center">
                  <FileText className="w-3.5 h-3.5 text-green-600" />
                </div>
                <h3 className="text-gray-800">Dados Contratuais</h3>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Tipo de contrato">
                  <div className="relative">
                    <select className={selectCls} value={data.tipoContrato} onChange={set("tipoContrato")}>
                      {CONTRATOS.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                </Field>
                <Field label="Data prevista de início" required>
                  <input type="date" className={inputCls} value={data.dataInicio} onChange={set("dataInicio")} />
                </Field>
                <Field label="Salário (R$)" required>
                  <input className={inputCls} placeholder="Ex: 3.500,00" value={data.salario} onChange={set("salario")} />
                </Field>
              </div>

              <Field label="Observações">
                <textarea
                  className={`${inputCls} resize-none`}
                  rows={3}
                  placeholder="Informações adicionais relevantes para a contratação..."
                  value={data.observacoes}
                  onChange={set("observacoes")}
                />
              </Field>
            </div>
          )}

          {step === 4 && (
            <div className="flex flex-col gap-5">
              <div className="flex items-center gap-2 mb-1">
                <div className="w-7 h-7 rounded-lg bg-green-100 flex items-center justify-center">
                  <CheckCircle className="w-3.5 h-3.5 text-green-600" />
                </div>
                <h3 className="text-gray-800">Confirmar Requisição</h3>
              </div>

              <p className="text-sm text-gray-500">Revise os dados antes de enviar. Após a confirmação, a requisição seguirá para aprovação do gestor.</p>

              <div className="bg-gray-50 rounded-xl border border-gray-200 overflow-hidden">
                {/* Candidato */}
                <div className="px-4 py-3 border-b border-gray-100">
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Candidato</p>
                  <div className="grid grid-cols-2 gap-x-8 gap-y-2">
                    <SummaryRow label="Nome" value={data.nome} />
                    <SummaryRow label="CPF" value={data.cpf} />
                    <SummaryRow label="Solicitante" value={data.solicitante} />
                  </div>
                </div>
                {/* Vaga */}
                <div className="px-4 py-3 border-b border-gray-100">
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Vaga</p>
                  <div className="grid grid-cols-2 gap-x-8 gap-y-2">
                    <SummaryRow label="Cargo" value={data.cargo} />
                    <SummaryRow label="Obra" value={data.obra} />
                    <SummaryRow label="Gestor" value={data.gestor} />
                    <SummaryRow label="Motivo" value={data.motivo} />
                  </div>
                </div>
                {/* Contrato */}
                <div className="px-4 py-3">
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Contrato</p>
                  <div className="grid grid-cols-2 gap-x-8 gap-y-2">
                    <SummaryRow label="Tipo" value={data.tipoContrato} />
                    <SummaryRow label="Salário" value={data.salario ? `R$ ${data.salario}` : "—"} />
                    <SummaryRow label="Início previsto" value={data.dataInicio || "—"} />
                  </div>
                  {data.observacoes && (
                    <div className="mt-2">
                      <SummaryRow label="Observações" value={data.observacoes} />
                    </div>
                  )}
                </div>
              </div>

              <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-lg p-4">
                <Building2 className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-amber-800">
                  A requisição será encaminhada ao gestor <strong>{data.gestor || "responsável"}</strong> para aprovação. Após aprovado, o candidato receberá o link para envio de documentos.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-between bg-gray-50">
          <button
            onClick={step === 1 ? onClose : handleBack}
            className="px-4 py-2 border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 text-sm font-medium rounded-lg transition-colors"
          >
            {step === 1 ? "Cancelar" : "← Voltar"}
          </button>

          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400">{step} de {STEPS.length}</span>
            {step < 4 ? (
              <button
                onClick={handleNext}
                disabled={!canAdvance()}
                className="inline-flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-200 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
              >
                Continuar <ChevronRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                className="inline-flex items-center gap-2 px-5 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors"
              >
                <CheckCircle className="w-4 h-4" /> Criar requisição
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

const SummaryRow = ({ label, value }: { label: string; value: string }) => (
  <div>
    <span className="text-xs text-gray-400">{label}: </span>
    <span className="text-xs text-gray-800 font-medium">{value || "—"}</span>
  </div>
);
