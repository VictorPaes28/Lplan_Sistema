export type EmployeeStatus = "Em Admissão" | "Ativo" | "Desligado";

export type Document = {
  id: string;
  name: string;
  status: "received" | "pending" | "missing";
  expiry?: string;
  required: boolean;
};

export type Employee = {
  id: string;
  name: string;
  cpf: string;
  rg: string;
  birthDate: string;
  address: string;
  bank: string;
  pis: string;
  education: string;
  shirtSize: string;
  bootSize: string;
  cargo: string;
  obras: string[];
  status: EmployeeStatus;
  admissionDate: string;
  company: string;
  docsReceived: number;
  docsTotal: number;
  nextDeadline?: string;
  photo?: string;
  documents: Document[];
};

export const OBRAS = ["Obra Paulista", "Obra Morumbi", "Obra Lapa", "Obra ABC", "Obra Tatuapé"];

export const EMPLOYEES: Employee[] = [
  {
    id: "1",
    name: "Carlos Eduardo Mendes",
    cpf: "423.891.047-55",
    rg: "32.456.789-0",
    birthDate: "15/03/1988",
    address: "Rua das Acácias, 234, Apto 12 – São Paulo/SP",
    bank: "Caixa Econômica – Ag. 0043 / CC 12345-6",
    pis: "127.45678.90-1",
    education: "Ensino Médio Completo",
    shirtSize: "G",
    bootSize: "42",
    cargo: "Encarregado de Obras",
    obras: ["Obra Paulista", "Obra Morumbi"],
    status: "Ativo",
    admissionDate: "12/01/2022",
    company: "Construtora Horizonte Ltda.",
    docsReceived: 11,
    docsTotal: 12,
    nextDeadline: "25/06/2026",
    documents: [
      { id: "d1", name: "RG", status: "received", required: true },
      { id: "d2", name: "CPF", status: "received", required: true },
      { id: "d3", name: "Título de Eleitor", status: "received", required: true },
      { id: "d4", name: "Certidão de Nascimento/Casamento", status: "received", required: true },
      { id: "d5", name: "Comprovante Bancário", status: "received", required: true },
      { id: "d6", name: "Comprovante de Endereço", status: "received", required: true },
      { id: "d7", name: "Certificado de Escolaridade", status: "received", required: false },
      { id: "d8", name: "PIS", status: "received", required: true },
      { id: "d9", name: "CTPS (Carteira de Trabalho)", status: "received", required: true },
      { id: "d10", name: "Documentos dos Filhos", status: "received", required: false },
      { id: "d11", name: "ASO – Atestado de Saúde", status: "pending", expiry: "25/06/2026", required: true },
      { id: "d12", name: "NR-35 – Trabalho em Altura", status: "missing", expiry: "30/07/2026", required: true },
    ],
  },
  {
    id: "2",
    name: "Fernanda Lima Souza",
    cpf: "987.654.321-00",
    rg: "41.234.567-8",
    birthDate: "22/07/1994",
    address: "Av. Paulista, 1000, Conj. 52 – São Paulo/SP",
    bank: "Bradesco – Ag. 1234 / CC 56789-0",
    pis: "234.56789.01-2",
    education: "Superior em Administração",
    shirtSize: "M",
    bootSize: "37",
    cargo: "Auxiliar Administrativa",
    obras: ["Obra Lapa"],
    status: "Em Admissão",
    admissionDate: "05/06/2026",
    company: "Construtora Horizonte Ltda.",
    docsReceived: 6,
    docsTotal: 12,
    nextDeadline: "15/06/2026",
    documents: [
      { id: "d1", name: "RG", status: "received", required: true },
      { id: "d2", name: "CPF", status: "received", required: true },
      { id: "d3", name: "Título de Eleitor", status: "missing", required: true },
      { id: "d4", name: "Certidão de Nascimento/Casamento", status: "received", required: true },
      { id: "d5", name: "Comprovante Bancário", status: "pending", required: true },
      { id: "d6", name: "Comprovante de Endereço", status: "received", required: true },
      { id: "d7", name: "Certificado de Escolaridade", status: "received", required: false },
      { id: "d8", name: "PIS", status: "missing", required: true },
      { id: "d9", name: "CTPS (Carteira de Trabalho)", status: "missing", required: true },
      { id: "d10", name: "Documentos dos Filhos", status: "missing", required: false },
      { id: "d11", name: "ASO – Atestado de Saúde", status: "missing", required: true },
      { id: "d12", name: "NR-35 – Trabalho em Altura", status: "missing", required: true },
    ],
  },
  {
    id: "3",
    name: "José Roberto Alves",
    cpf: "111.222.333-44",
    rg: "55.667.788-9",
    birthDate: "08/11/1980",
    address: "Rua Voluntários da Pátria, 78 – São Paulo/SP",
    bank: "Itaú – Ag. 5678 / CC 90123-4",
    pis: "345.67890.12-3",
    education: "Ensino Fundamental",
    shirtSize: "GG",
    bootSize: "43",
    cargo: "Pedreiro",
    obras: ["Obra ABC"],
    status: "Ativo",
    admissionDate: "03/05/2019",
    company: "Construtora Horizonte Ltda.",
    docsReceived: 12,
    docsTotal: 12,
    nextDeadline: "10/09/2026",
    documents: [
      { id: "d1", name: "RG", status: "received", required: true },
      { id: "d2", name: "CPF", status: "received", required: true },
      { id: "d3", name: "Título de Eleitor", status: "received", required: true },
      { id: "d4", name: "Certidão de Nascimento/Casamento", status: "received", required: true },
      { id: "d5", name: "Comprovante Bancário", status: "received", required: true },
      { id: "d6", name: "Comprovante de Endereço", status: "received", required: true },
      { id: "d7", name: "Certificado de Escolaridade", status: "received", required: false },
      { id: "d8", name: "PIS", status: "received", required: true },
      { id: "d9", name: "CTPS (Carteira de Trabalho)", status: "received", required: true },
      { id: "d10", name: "Documentos dos Filhos", status: "received", required: false },
      { id: "d11", name: "ASO – Atestado de Saúde", status: "received", expiry: "10/09/2026", required: true },
      { id: "d12", name: "NR-35 – Trabalho em Altura", status: "received", expiry: "15/12/2026", required: true },
    ],
  },
  {
    id: "4",
    name: "Marcos Antônio Ferreira",
    cpf: "555.666.777-88",
    rg: "12.345.678-9",
    birthDate: "30/04/1975",
    address: "Rua Guaicurus, 450 – São Paulo/SP",
    bank: "Banco do Brasil – Ag. 9012 / CC 34567-8",
    pis: "456.78901.23-4",
    education: "Técnico em Edificações",
    shirtSize: "GG",
    bootSize: "44",
    cargo: "Mestre de Obras",
    obras: ["Obra Tatuapé", "Obra ABC"],
    status: "Ativo",
    admissionDate: "17/08/2015",
    company: "Construtora Horizonte Ltda.",
    docsReceived: 10,
    docsTotal: 12,
    nextDeadline: "03/07/2026",
    documents: [
      { id: "d1", name: "RG", status: "received", required: true },
      { id: "d2", name: "CPF", status: "received", required: true },
      { id: "d3", name: "Título de Eleitor", status: "received", required: true },
      { id: "d4", name: "Certidão de Nascimento/Casamento", status: "received", required: true },
      { id: "d5", name: "Comprovante Bancário", status: "received", required: true },
      { id: "d6", name: "Comprovante de Endereço", status: "received", required: true },
      { id: "d7", name: "Certificado de Escolaridade", status: "received", required: false },
      { id: "d8", name: "PIS", status: "received", required: true },
      { id: "d9", name: "CTPS (Carteira de Trabalho)", status: "received", required: true },
      { id: "d10", name: "Documentos dos Filhos", status: "missing", required: false },
      { id: "d11", name: "ASO – Atestado de Saúde", status: "pending", expiry: "03/07/2026", required: true },
      { id: "d12", name: "NR-35 – Trabalho em Altura", status: "missing", expiry: "20/06/2026", required: true },
    ],
  },
  {
    id: "5",
    name: "Ana Paula Rodrigues",
    cpf: "999.888.777-66",
    rg: "98.765.432-1",
    birthDate: "14/12/1991",
    address: "Av. Interlagos, 333 – São Paulo/SP",
    bank: "Nubank – Ag. 0001 / CC 11111-1",
    pis: "567.89012.34-5",
    education: "Superior em Engenharia Civil",
    shirtSize: "P",
    bootSize: "36",
    cargo: "Engenheira de Obras",
    obras: ["Obra Paulista"],
    status: "Desligado",
    admissionDate: "02/03/2021",
    company: "Construtora Horizonte Ltda.",
    docsReceived: 12,
    docsTotal: 12,
    documents: [
      { id: "d1", name: "RG", status: "received", required: true },
      { id: "d2", name: "CPF", status: "received", required: true },
      { id: "d3", name: "Título de Eleitor", status: "received", required: true },
      { id: "d4", name: "Certidão de Nascimento/Casamento", status: "received", required: true },
      { id: "d5", name: "Comprovante Bancário", status: "received", required: true },
      { id: "d6", name: "Comprovante de Endereço", status: "received", required: true },
      { id: "d7", name: "Certificado de Escolaridade", status: "received", required: false },
      { id: "d8", name: "PIS", status: "received", required: true },
      { id: "d9", name: "CTPS (Carteira de Trabalho)", status: "received", required: true },
      { id: "d10", name: "Documentos dos Filhos", status: "received", required: false },
      { id: "d11", name: "ASO – Atestado de Saúde", status: "received", expiry: "30/11/2025", required: true },
      { id: "d12", name: "NR-35 – Trabalho em Altura", status: "received", expiry: "15/05/2026", required: true },
    ],
  },
];

export type DocConfig = {
  id: string;
  name: string;
  appliesTo: "Todos" | "Por Cargo" | "Por Obra";
  hasExpiry: boolean;
  expiryDays?: number;
  required: boolean;
};

export const DOC_CONFIGS: DocConfig[] = [
  { id: "dc1", name: "RG", appliesTo: "Todos", hasExpiry: false, required: true },
  { id: "dc2", name: "CPF", appliesTo: "Todos", hasExpiry: false, required: true },
  { id: "dc3", name: "Título de Eleitor", appliesTo: "Todos", hasExpiry: false, required: true },
  { id: "dc4", name: "Certidão de Nascimento/Casamento", appliesTo: "Todos", hasExpiry: false, required: true },
  { id: "dc5", name: "Comprovante Bancário", appliesTo: "Todos", hasExpiry: false, required: true },
  { id: "dc6", name: "Comprovante de Endereço", appliesTo: "Todos", hasExpiry: true, expiryDays: 90, required: true },
  { id: "dc7", name: "Certificado de Escolaridade", appliesTo: "Por Cargo", hasExpiry: false, required: false },
  { id: "dc8", name: "PIS", appliesTo: "Todos", hasExpiry: false, required: true },
  { id: "dc9", name: "CTPS (Carteira de Trabalho)", appliesTo: "Todos", hasExpiry: false, required: true },
  { id: "dc10", name: "Documentos dos Filhos", appliesTo: "Todos", hasExpiry: false, required: false },
  { id: "dc11", name: "ASO – Atestado de Saúde Ocupacional", appliesTo: "Todos", hasExpiry: true, expiryDays: 365, required: true },
  { id: "dc12", name: "NR-35 – Trabalho em Altura", appliesTo: "Por Cargo", hasExpiry: true, expiryDays: 365, required: true },
  { id: "dc13", name: "NR-10 – Segurança em Eletricidade", appliesTo: "Por Cargo", hasExpiry: true, expiryDays: 730, required: false },
  { id: "dc14", name: "FGTS – Extrato", appliesTo: "Todos", hasExpiry: true, expiryDays: 30, required: false },
];
