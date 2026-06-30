import { useState } from "react";
import { Search, ChevronDown, Eye, Edit, Trash2, GitMerge } from "lucide-react";
import { EMPLOYEES, OBRAS, type Employee, type EmployeeStatus } from "./data";

type Props = {
  onSelectEmployee: (emp: Employee) => void;
  onGoToAdmission: () => void;
};

const StatusBadge = ({ status }: { status: EmployeeStatus }) => {
  const styles: Record<EmployeeStatus, string> = {
    "Em Admissão": "bg-blue-50 text-blue-700 border border-blue-200",
    "Ativo": "bg-green-50 text-green-700 border border-green-200",
    "Desligado": "bg-gray-100 text-gray-500 border border-gray-200",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${styles[status]}`}>
      {status}
    </span>
  );
};

const DocProgress = ({ received, total }: { received: number; total: number }) => {
  const missing = total - received;
  const color = missing === 0 ? "text-green-600" : missing >= 3 ? "text-red-600" : "text-yellow-600";
  const bg = missing === 0 ? "bg-green-500" : missing >= 3 ? "bg-red-500" : "bg-yellow-500";
  const pct = Math.round((received / total) * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full bg-gray-200 overflow-hidden">
        <div className={`h-full rounded-full ${bg}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-medium tabular-nums ${color}`}>{received}/{total}</span>
    </div>
  );
};

export function Screen1EmployeeList({ onSelectEmployee, onGoToAdmission }: Props) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"Todos" | EmployeeStatus>("Todos");
  const [obraFilter, setObraFilter] = useState("Todas");

  const filtered = EMPLOYEES.filter((e) => {
    const matchSearch =
      e.name.toLowerCase().includes(search.toLowerCase()) ||
      e.cpf.includes(search) ||
      e.cargo.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === "Todos" || e.status === statusFilter;
    const matchObra = obraFilter === "Todas" || e.obras.includes(obraFilter);
    return matchSearch && matchStatus && matchObra;
  });

  const statusTabMap: Record<string, "Todos" | EmployeeStatus> = {
    "Todos": "Todos",
    "Em Admissão": "Em Admissão",
    "Ativos": "Ativo",
    "Desligados": "Desligado",
  };

  const countByStatus = (s: EmployeeStatus) => EMPLOYEES.filter((e) => e.status === s).length;

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-gray-900">Colaboradores</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Registro de todos os colaboradores da empresa. Para contratar alguém novo, inicie pelo{" "}
            <button onClick={onGoToAdmission} className="text-blue-600 hover:underline font-medium">
              Fluxo de Admissão
            </button>.
          </p>
        </div>
        <button
          onClick={onGoToAdmission}
          className="inline-flex items-center gap-2 border border-blue-200 bg-blue-50 hover:bg-blue-100 text-blue-700 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <GitMerge className="w-4 h-4" />
          Iniciar admissão
        </button>
      </div>

      {/* Summary chips */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-green-50 border border-green-200 rounded-lg">
          <span className="w-2 h-2 rounded-full bg-green-500" />
          <span className="text-xs font-medium text-green-700">{countByStatus("Ativo")} Ativos</span>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-lg">
          <span className="w-2 h-2 rounded-full bg-blue-500" />
          <span className="text-xs font-medium text-blue-700">{countByStatus("Em Admissão")} Em Admissão</span>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 border border-gray-200 rounded-lg">
          <span className="w-2 h-2 rounded-full bg-gray-400" />
          <span className="text-xs font-medium text-gray-500">{countByStatus("Desligado")} Desligados</span>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Buscar por nome, CPF ou cargo..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div className="flex items-center bg-gray-100 rounded-lg p-0.5 gap-0.5">
          {Object.entries(statusTabMap).map(([label, value]) => (
            <button
              key={label}
              onClick={() => setStatusFilter(value)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                statusFilter === value
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="relative">
          <select
            value={obraFilter}
            onChange={(e) => setObraFilter(e.target.value)}
            className="appearance-none pl-3 pr-8 py-2 text-sm border border-gray-200 rounded-lg bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="Todas">Todas as obras</option>
            {OBRAS.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
          <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 pointer-events-none" />
        </div>

        <span className="text-xs text-gray-500 ml-auto">{filtered.length} colaborador{filtered.length !== 1 ? "es" : ""}</span>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              {["Nome", "CPF", "Cargo", "Obra(s)", "Status", "Documentos", "Prazo próximo", "Ações"].map((h) => (
                <th key={h} className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filtered.map((emp) => (
              <tr key={emp.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 text-xs font-semibold flex-shrink-0">
                      {emp.name.split(" ").map((n) => n[0]).slice(0, 2).join("")}
                    </div>
                    <button
                      onClick={() => onSelectEmployee(emp)}
                      className="font-medium text-gray-900 hover:text-blue-600 transition-colors text-left"
                    >
                      {emp.name}
                    </button>
                  </div>
                </td>
                <td className="px-4 py-3 text-gray-500 tabular-nums">{emp.cpf}</td>
                <td className="px-4 py-3 text-gray-700">{emp.cargo}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {emp.obras.map((o) => (
                      <span key={o} className="px-1.5 py-0.5 rounded text-xs bg-gray-100 text-gray-600">{o}</span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3"><StatusBadge status={emp.status} /></td>
                <td className="px-4 py-3">
                  {emp.status === "Em Admissão" ? (
                    <button
                      onClick={onGoToAdmission}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      Ver admissão →
                    </button>
                  ) : (
                    <DocProgress received={emp.docsReceived} total={emp.docsTotal} />
                  )}
                </td>
                <td className="px-4 py-3">
                  {emp.nextDeadline ? (
                    <span className={`text-xs tabular-nums ${
                      emp.status === "Desligado" ? "text-gray-400" :
                      emp.nextDeadline < "20/06/2026" ? "text-red-600 font-medium" : "text-gray-600"
                    }`}>
                      {emp.nextDeadline}
                    </span>
                  ) : (
                    <span className="text-gray-300 text-xs">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => onSelectEmployee(emp)}
                      className="p-1.5 rounded-md hover:bg-blue-50 text-gray-400 hover:text-blue-600 transition-colors"
                      title="Ver perfil"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    <button className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors" title="Editar">
                      <Edit className="w-4 h-4" />
                    </button>
                    <button className="p-1.5 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors" title="Excluir">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="py-12 text-center text-gray-400 text-sm">Nenhum colaborador encontrado.</div>
        )}
      </div>
    </div>
  );
}
