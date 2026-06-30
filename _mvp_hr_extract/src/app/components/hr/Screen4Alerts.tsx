import { AlertTriangle, Clock, XCircle, BookOpen, UserPlus, ChevronRight, Bell } from "lucide-react";

const ALERTS = [
  {
    id: "al1",
    employee: "Marcos Antônio Ferreira",
    type: "Documento vencendo",
    detail: "NR-35 – Trabalho em Altura",
    deadline: "20/06/2026",
    daysLeft: 10,
    urgency: "red" as const,
    action: "Renovar",
  },
  {
    id: "al2",
    employee: "Carlos Eduardo Mendes",
    type: "Documento vencendo",
    detail: "ASO – Atestado de Saúde",
    deadline: "25/06/2026",
    daysLeft: 15,
    urgency: "yellow" as const,
    action: "Agendar",
  },
  {
    id: "al3",
    employee: "Fernanda Lima Souza",
    type: "Admissão em andamento",
    detail: "Documentos pendentes: Título, PIS, CTPS",
    deadline: "15/06/2026",
    daysLeft: 5,
    urgency: "red" as const,
    action: "Ver admissão",
  },
  {
    id: "al4",
    employee: "Ana Paula Rodrigues",
    type: "Documento vencido",
    detail: "ASO – Atestado de Saúde (venceu 30/11/2025)",
    deadline: "30/11/2025",
    daysLeft: -192,
    urgency: "red" as const,
    action: "Regularizar",
  },
  {
    id: "al5",
    employee: "Ana Paula Rodrigues",
    type: "Documento vencido",
    detail: "NR-35 – Trabalho em Altura (venceu 15/05/2026)",
    deadline: "15/05/2026",
    daysLeft: -26,
    urgency: "red" as const,
    action: "Regularizar",
  },
  {
    id: "al6",
    employee: "José Roberto Alves",
    type: "Treinamento pendente",
    detail: "Reciclagem NR-18 – Construção Civil",
    deadline: "30/07/2026",
    daysLeft: 50,
    urgency: "green" as const,
    action: "Agendar",
  },
  {
    id: "al7",
    employee: "Marcos Antônio Ferreira",
    type: "Documento vencendo",
    detail: "ASO – Atestado de Saúde",
    deadline: "03/07/2026",
    daysLeft: 23,
    urgency: "yellow" as const,
    action: "Agendar",
  },
  {
    id: "al8",
    employee: "Ricardo Souza Neto",
    type: "Admissão em andamento",
    detail: "Aguardando aprovação do RH",
    deadline: "11/06/2026",
    daysLeft: 1,
    urgency: "yellow" as const,
    action: "Aprovar",
  },
];

const SUMMARY_CARDS = [
  {
    label: "Documentos vencendo (7 dias)",
    count: 1,
    icon: Clock,
    color: "text-yellow-600",
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    iconBg: "bg-yellow-100",
  },
  {
    label: "Documentos vencidos",
    count: 2,
    icon: XCircle,
    color: "text-red-600",
    bg: "bg-red-50",
    border: "border-red-200",
    iconBg: "bg-red-100",
  },
  {
    label: "Treinamentos pendentes",
    count: 1,
    icon: BookOpen,
    color: "text-blue-600",
    bg: "bg-blue-50",
    border: "border-blue-200",
    iconBg: "bg-blue-100",
  },
  {
    label: "Admissões em andamento",
    count: 2,
    icon: UserPlus,
    color: "text-green-600",
    bg: "bg-green-50",
    border: "border-green-200",
    iconBg: "bg-green-100",
  },
];

const urgencyStyle = {
  red: {
    dot: "bg-red-500",
    badge: "bg-red-50 text-red-700 border-red-200",
    bar: "bg-red-500",
    label: "Urgente",
  },
  yellow: {
    dot: "bg-yellow-500",
    badge: "bg-yellow-50 text-yellow-700 border-yellow-200",
    bar: "bg-yellow-500",
    label: "Atenção",
  },
  green: {
    dot: "bg-green-500",
    badge: "bg-green-50 text-green-700 border-green-200",
    bar: "bg-green-500",
    label: "Informativo",
  },
};

export function Screen4Alerts() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-gray-900">Prazos e Alertas</h1>
          <p className="text-sm text-gray-500 mt-0.5">Monitoramento de documentos, treinamentos e admissões em tempo real</p>
        </div>
        <button className="inline-flex items-center gap-2 border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 text-sm font-medium px-4 py-2 rounded-lg transition-colors">
          <Bell className="w-4 h-4" /> Configurar alertas
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {SUMMARY_CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <div key={card.label} className={`bg-white rounded-xl border ${card.border} p-5 flex items-center gap-4`}>
              <div className={`w-10 h-10 rounded-lg ${card.iconBg} flex items-center justify-center flex-shrink-0`}>
                <Icon className={`w-5 h-5 ${card.color}`} />
              </div>
              <div>
                <p className={`text-2xl font-bold ${card.color}`}>{card.count}</p>
                <p className="text-xs text-gray-500 leading-tight mt-0.5">{card.label}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Alerts list */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-gray-900">Todos os alertas</h3>
          <span className="text-xs text-gray-500">{ALERTS.length} itens</span>
        </div>
        <div className="divide-y divide-gray-50">
          {ALERTS.map((alert) => {
            const s = urgencyStyle[alert.urgency];
            return (
              <div key={alert.id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50 transition-colors">
                <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${s.dot}`} />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-gray-900">{alert.employee}</span>
                    <span className="text-xs text-gray-400">·</span>
                    <span className="text-xs text-gray-500">{alert.type}</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5 truncate">{alert.detail}</p>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className="text-xs tabular-nums text-gray-600">{alert.deadline}</p>
                    <p className={`text-xs font-medium ${alert.daysLeft < 0 ? "text-red-600" : alert.daysLeft <= 7 ? "text-red-600" : alert.daysLeft <= 30 ? "text-yellow-600" : "text-green-600"}`}>
                      {alert.daysLeft < 0 ? `${Math.abs(alert.daysLeft)} dias atraso` : alert.daysLeft === 0 ? "Hoje" : `${alert.daysLeft} dias`}
                    </p>
                  </div>

                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${s.badge}`}>
                    {s.label}
                  </span>

                  <button className="inline-flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border border-gray-200 text-gray-700 hover:border-blue-300 hover:text-blue-600 transition-colors whitespace-nowrap">
                    {alert.action} <ChevronRight className="w-3 h-3" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
