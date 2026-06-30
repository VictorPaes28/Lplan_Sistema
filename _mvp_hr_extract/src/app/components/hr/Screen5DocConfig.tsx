import { useState } from "react";
import { Plus, Pencil, Trash2, Check, X } from "lucide-react";
import { DOC_CONFIGS, type DocConfig } from "./data";

const Toggle = ({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) => (
  <button
    onClick={() => onChange(!value)}
    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${value ? "bg-blue-600" : "bg-gray-300"}`}
  >
    <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform shadow-sm ${value ? "translate-x-5" : "translate-x-0.5"}`} />
  </button>
);

type RowProps = {
  doc: DocConfig;
  onDelete: (id: string) => void;
};

const DocRow = ({ doc, onDelete }: RowProps) => (
  <tr className="hover:bg-gray-50 transition-colors">
    <td className="px-4 py-3">
      <span className="text-sm text-gray-800">{doc.name}</span>
    </td>
    <td className="px-4 py-3">
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${
        doc.appliesTo === "Todos" ? "bg-gray-100 text-gray-600 border-gray-200" :
        doc.appliesTo === "Por Cargo" ? "bg-purple-50 text-purple-700 border-purple-200" :
        "bg-blue-50 text-blue-700 border-blue-200"
      }`}>
        {doc.appliesTo}
      </span>
    </td>
    <td className="px-4 py-3">
      <div className="flex items-center gap-1.5">
        {doc.hasExpiry
          ? <Check className="w-4 h-4 text-green-500" />
          : <X className="w-4 h-4 text-gray-300" />}
        <span className="text-sm text-gray-600">{doc.hasExpiry ? "Sim" : "Não"}</span>
      </div>
    </td>
    <td className="px-4 py-3">
      {doc.hasExpiry && doc.expiryDays ? (
        <span className="text-sm tabular-nums text-gray-700">{doc.expiryDays} dias</span>
      ) : (
        <span className="text-gray-300 text-sm">—</span>
      )}
    </td>
    <td className="px-4 py-3">
      <div className="flex items-center gap-1.5">
        {doc.required
          ? <Check className="w-4 h-4 text-blue-500" />
          : <X className="w-4 h-4 text-gray-300" />}
        <span className="text-sm text-gray-600">{doc.required ? "Sim" : "Não"}</span>
      </div>
    </td>
    <td className="px-4 py-3">
      <div className="flex items-center gap-1">
        <button className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors">
          <Pencil className="w-4 h-4" />
        </button>
        <button
          onClick={() => onDelete(doc.id)}
          className="p-1.5 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </td>
  </tr>
);

export function Screen5DocConfig() {
  const [docs, setDocs] = useState<DocConfig[]>(DOC_CONFIGS);
  const [showAdd, setShowAdd] = useState(false);
  const [newDoc, setNewDoc] = useState<Partial<DocConfig>>({
    name: "",
    appliesTo: "Todos",
    hasExpiry: false,
    expiryDays: 365,
    required: true,
  });

  const handleDelete = (id: string) => setDocs((d) => d.filter((x) => x.id !== id));

  const handleAdd = () => {
    if (!newDoc.name?.trim()) return;
    setDocs((d) => [...d, { ...newDoc, id: `dc${Date.now()}` } as DocConfig]);
    setShowAdd(false);
    setNewDoc({ name: "", appliesTo: "Todos", hasExpiry: false, expiryDays: 365, required: true });
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-gray-900">Configuração de Documentos</h1>
          <p className="text-sm text-gray-500 mt-0.5">Defina os tipos de documentos exigidos e suas regras de validade</p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" /> Novo Tipo de Documento
        </button>
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
          <h3 className="text-blue-900 mb-4">Novo tipo de documento</h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="lg:col-span-2">
              <label className="block text-xs font-medium text-gray-600 mb-1">Nome do documento</label>
              <input
                type="text"
                placeholder="Ex: CNH – Carteira de Habilitação"
                value={newDoc.name || ""}
                onChange={(e) => setNewDoc({ ...newDoc, name: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Aplica-se a</label>
              <select
                value={newDoc.appliesTo}
                onChange={(e) => setNewDoc({ ...newDoc, appliesTo: e.target.value as DocConfig["appliesTo"] })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="Todos">Todos</option>
                <option value="Por Cargo">Por Cargo</option>
                <option value="Por Obra">Por Obra</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Validade (dias)</label>
              <input
                type="number"
                disabled={!newDoc.hasExpiry}
                value={newDoc.expiryDays || ""}
                onChange={(e) => setNewDoc({ ...newDoc, expiryDays: Number(e.target.value) })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white text-gray-900 disabled:bg-gray-100 disabled:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <div className="flex items-center gap-6 mt-4">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <Toggle value={!!newDoc.hasExpiry} onChange={(v) => setNewDoc({ ...newDoc, hasExpiry: v })} />
              <span className="text-sm text-gray-700">Possui validade</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <Toggle value={!!newDoc.required} onChange={(v) => setNewDoc({ ...newDoc, required: v })} />
              <span className="text-sm text-gray-700">Obrigatório</span>
            </label>
          </div>
          <div className="flex items-center gap-3 mt-5">
            <button
              onClick={handleAdd}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Adicionar documento
            </button>
            <button
              onClick={() => setShowAdd(false)}
              className="px-4 py-2 border border-gray-200 bg-white text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              {["Nome do documento", "Aplica-se a", "Possui validade", "Prazo de validade", "Obrigatório", "Ações"].map((h) => (
                <th key={h} className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {docs.map((doc) => (
              <DocRow key={doc.id} doc={doc} onDelete={handleDelete} />
            ))}
          </tbody>
        </table>
        {docs.length === 0 && (
          <div className="py-12 text-center text-gray-400 text-sm">Nenhum documento configurado.</div>
        )}
      </div>

      <p className="text-xs text-gray-400">
        {docs.length} tipo{docs.length !== 1 ? "s" : ""} de documento configurado{docs.length !== 1 ? "s" : ""} · {docs.filter(d => d.required).length} obrigatórios
      </p>
    </div>
  );
}
