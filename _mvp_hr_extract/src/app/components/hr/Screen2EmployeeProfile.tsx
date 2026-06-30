import { ArrowLeft, Upload, Eye, CheckCircle, AlertTriangle, XCircle, Building2, Calendar, Briefcase } from "lucide-react";
import { type Employee, type Document } from "./data";

type Props = {
  employee: Employee;
  onBack: () => void;
};

const DocStatusIcon = ({ status }: { status: Document["status"] }) => {
  if (status === "received") return <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />;
  if (status === "pending") return <AlertTriangle className="w-4 h-4 text-yellow-500 flex-shrink-0" />;
  return <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />;
};

const DocStatusLabel = ({ status }: { status: Document["status"] }) => {
  const map = {
    received: { label: "Recebido", cls: "text-green-600 bg-green-50 border-green-200" },
    pending: { label: "Pendente", cls: "text-yellow-700 bg-yellow-50 border-yellow-200" },
    missing: { label: "Faltando", cls: "text-red-600 bg-red-50 border-red-200" },
  };
  const s = map[status];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${s.cls}`}>
      {s.label}
    </span>
  );
};

const Field = ({ label, value }: { label: string; value: string }) => (
  <div>
    <p className="text-xs text-gray-400 mb-0.5">{label}</p>
    <p className="text-sm text-gray-800">{value}</p>
  </div>
);

export function Screen2EmployeeProfile({ employee: emp, onBack }: Props) {
  const statusStyle: Record<string, string> = {
    "Em Admissão": "bg-blue-50 text-blue-700 border border-blue-200",
    "Ativo": "bg-green-50 text-green-700 border border-green-200",
    "Desligado": "bg-gray-100 text-gray-500 border border-gray-200",
  };

  const received = emp.documents.filter((d) => d.status === "received").length;
  const total = emp.documents.length;

  return (
    <div className="flex flex-col gap-6">
      {/* Back + Header */}
      <div>
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors mb-4"
        >
          <ArrowLeft className="w-4 h-4" /> Voltar para lista
        </button>

        <div className="flex items-start gap-4">
          <div className="w-16 h-16 rounded-xl bg-blue-100 flex items-center justify-center text-blue-700 text-xl font-semibold flex-shrink-0">
            {emp.name.split(" ").map((n) => n[0]).slice(0, 2).join("")}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-gray-900">{emp.name}</h1>
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium ${statusStyle[emp.status]}`}>
                {emp.status}
              </span>
            </div>
            <p className="text-sm text-gray-500 mt-0.5">{emp.cargo}</p>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              {emp.obras.map((o) => (
                <span key={o} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-700 border border-blue-100">
                  <Building2 className="w-3 h-3" />{o}
                </span>
              ))}
            </div>
          </div>
          <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
            Editar
          </button>
        </div>
      </div>

      {/* Two columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Personal Data */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-gray-900 mb-4 pb-3 border-b border-gray-100">Dados Pessoais</h3>
          <div className="grid grid-cols-2 gap-x-8 gap-y-4">
            <Field label="Nome completo" value={emp.name} />
            <Field label="CPF" value={emp.cpf} />
            <Field label="RG" value={emp.rg} />
            <Field label="Data de nascimento" value={emp.birthDate} />
            <Field label="PIS" value={emp.pis} />
            <Field label="Escolaridade" value={emp.education} />
            <div className="col-span-2"><Field label="Endereço" value={emp.address} /></div>
            <div className="col-span-2"><Field label="Conta bancária" value={emp.bank} /></div>
            <Field label="Tamanho de camisa" value={emp.shirtSize} />
            <Field label="Tamanho de bota" value={emp.bootSize} />
          </div>
        </div>

        {/* Right: Work Info */}
        <div className="flex flex-col gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-gray-900 mb-4 pb-3 border-b border-gray-100">Dados Profissionais</h3>
            <div className="flex flex-col gap-4">
              <div className="flex items-start gap-3">
                <Briefcase className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-xs text-gray-400">Cargo</p>
                  <p className="text-sm text-gray-800">{emp.cargo}</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <Calendar className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-xs text-gray-400">Admissão</p>
                  <p className="text-sm text-gray-800">{emp.admissionDate}</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <Building2 className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-xs text-gray-400">Empresa responsável</p>
                  <p className="text-sm text-gray-800">{emp.company}</p>
                </div>
              </div>
              <div>
                <p className="text-xs text-gray-400 mb-2">Obras vinculadas</p>
                <div className="flex flex-col gap-1">
                  {emp.obras.map((o) => (
                    <span key={o} className="text-sm text-gray-700 flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-500 flex-shrink-0" />{o}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Doc Summary */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-gray-900">Documentação</h4>
              <span className="text-xs text-gray-500">{received}/{total} docs</span>
            </div>
            <div className="w-full h-2 rounded-full bg-gray-100 overflow-hidden mb-2">
              <div
                className={`h-full rounded-full transition-all ${received === total ? "bg-green-500" : received < total * 0.6 ? "bg-red-500" : "bg-yellow-500"}`}
                style={{ width: `${(received / total) * 100}%` }}
              />
            </div>
            <p className="text-xs text-gray-400">{total - received} documento{total - received !== 1 ? "s" : ""} pendente{total - received !== 1 ? "s" : ""}</p>
          </div>
        </div>
      </div>

      {/* Document Checklist */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-gray-900">Checklist de Documentos</h3>
          <span className="text-xs text-gray-500">{received} de {total} recebidos</span>
        </div>
        <div className="divide-y divide-gray-50">
          {emp.documents.map((doc) => (
            <div key={doc.id} className="flex items-center gap-4 px-5 py-3 hover:bg-gray-50 transition-colors">
              <DocStatusIcon status={doc.status} />
              <div className="flex-1 min-w-0">
                <span className="text-sm text-gray-800">{doc.name}</span>
                {doc.required && (
                  <span className="ml-2 text-xs text-gray-400">obrigatório</span>
                )}
              </div>
              <DocStatusLabel status={doc.status} />
              {doc.expiry ? (
                <span className="text-xs text-gray-500 tabular-nums w-24 text-right">Venc. {doc.expiry}</span>
              ) : (
                <span className="w-24" />
              )}
              <div className="flex items-center gap-1.5">
                <button className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-md border border-gray-200 text-gray-600 hover:border-blue-300 hover:text-blue-600 transition-colors">
                  <Upload className="w-3 h-3" /> Upload
                </button>
                {doc.status === "received" && (
                  <button className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-md border border-gray-200 text-gray-600 hover:border-gray-300 hover:text-gray-800 transition-colors">
                    <Eye className="w-3 h-3" /> Ver
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
