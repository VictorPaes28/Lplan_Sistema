import { useState } from "react";
import {
  Users, GitMerge, Bell, Settings, HardHat,
  LayoutDashboard, ChevronRight,
} from "lucide-react";
import { Screen1EmployeeList } from "./components/hr/Screen1EmployeeList";
import { Screen2EmployeeProfile } from "./components/hr/Screen2EmployeeProfile";
import { Screen3AdmissionFlow } from "./components/hr/Screen3AdmissionFlow";
import { Screen4Alerts } from "./components/hr/Screen4Alerts";
import { Screen5DocConfig } from "./components/hr/Screen5DocConfig";
import { type Employee } from "./components/hr/data";

type Screen = "employees" | "profile" | "admission" | "alerts" | "docconfig";

const NAV_ITEMS = [
  { id: "employees" as Screen, label: "Colaboradores", icon: Users },
  { id: "admission" as Screen, label: "Fluxo de Admissão", icon: GitMerge },
  { id: "alerts" as Screen, label: "Prazos e Alertas", icon: Bell, badge: 3 },
  { id: "docconfig" as Screen, label: "Config. Documentos", icon: Settings },
];

export default function App() {
  const [screen, setScreen] = useState<Screen>("employees");
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);

  const handleSelectEmployee = (emp: Employee) => {
    setSelectedEmployee(emp);
    setScreen("profile");
  };

  const handleBack = () => {
    setScreen("employees");
    setSelectedEmployee(null);
  };

  const activeNav = screen === "profile" ? "employees" : screen;

  const breadcrumbs: Record<Screen, string[]> = {
    employees: ["DP / RH", "Colaboradores"],
    profile: ["DP / RH", "Colaboradores", selectedEmployee?.name ?? "Perfil"],
    admission: ["DP / RH", "Fluxo de Admissão"],
    alerts: ["DP / RH", "Prazos e Alertas"],
    docconfig: ["DP / RH", "Config. Documentos"],
  };

  return (
    <div className="min-h-screen bg-[#f9fafb] flex font-[Inter,system-ui,sans-serif]">
      {/* Sidebar */}
      <aside className="w-60 bg-white border-r border-gray-200 flex flex-col flex-shrink-0 sticky top-0 h-screen">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-gray-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center flex-shrink-0">
              <HardHat className="w-4.5 h-4.5 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900 leading-tight">Horizonte</p>
              <p className="text-xs text-gray-400 leading-tight">Construções</p>
            </div>
          </div>
        </div>

        {/* Module label */}
        <div className="px-4 pt-5 pb-2">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">DP / Recursos Humanos</p>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 flex flex-col gap-0.5">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = activeNav === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setScreen(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors text-left ${
                  active
                    ? "bg-blue-50 text-blue-700 font-medium"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                }`}
              >
                <Icon className={`w-4 h-4 flex-shrink-0 ${active ? "text-blue-600" : "text-gray-400"}`} />
                <span className="flex-1">{item.label}</span>
                {item.badge && (
                  <span className="w-5 h-5 rounded-full bg-red-500 text-white text-xs font-semibold flex items-center justify-center flex-shrink-0">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Bottom: other modules placeholder */}
        <div className="px-4 pb-4 pt-2 border-t border-gray-100 mt-2">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Outros módulos</p>
          {["Obras", "Financeiro", "Compras"].map((m) => (
            <button key={m} className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors text-left">
              <LayoutDashboard className="w-4 h-4" />
              {m}
            </button>
          ))}
        </div>

        {/* User */}
        <div className="border-t border-gray-100 px-4 py-3 flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-gray-600 text-xs font-semibold flex-shrink-0">
            CM
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-gray-800 truncate">Carla Moreira</p>
            <p className="text-xs text-gray-400 truncate">RH · Administrador</p>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="bg-white border-b border-gray-200 px-8 py-3.5 flex items-center gap-2">
          {breadcrumbs[screen].map((crumb, i, arr) => (
            <span key={i} className="flex items-center gap-2">
              <span className={`text-sm ${i === arr.length - 1 ? "text-gray-900 font-medium" : "text-gray-400"}`}>
                {crumb}
              </span>
              {i < arr.length - 1 && <ChevronRight className="w-3.5 h-3.5 text-gray-300" />}
            </span>
          ))}
        </header>

        {/* Content */}
        <main className="flex-1 p-8 overflow-auto">
          {screen === "employees" && (
            <Screen1EmployeeList
              onSelectEmployee={handleSelectEmployee}
              onGoToAdmission={() => setScreen("admission")}
            />
          )}
          {screen === "profile" && selectedEmployee && (
            <Screen2EmployeeProfile employee={selectedEmployee} onBack={handleBack} />
          )}
          {screen === "admission" && <Screen3AdmissionFlow />}
          {screen === "alerts" && <Screen4Alerts />}
          {screen === "docconfig" && <Screen5DocConfig />}
        </main>
      </div>
    </div>
  );
}
