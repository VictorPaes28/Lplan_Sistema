export type Category = {
  id: string;
  name: string;
  icon: string;
  budget: number;
  color: string;
};

export type Expense = {
  id: string;
  categoryId: string;
  description: string;
  amount: number;
  date: string;
};

export const CATEGORIES: Category[] = [
  { id: "housing", name: "Housing", icon: "🏠", budget: 2000, color: "#38bdf8" },
  { id: "food", name: "Food & Dining", icon: "🍽️", budget: 600, color: "#00d68f" },
  { id: "transport", name: "Transport", icon: "🚗", budget: 300, color: "#f59e0b" },
  { id: "utilities", name: "Utilities", icon: "⚡", budget: 200, color: "#a78bfa" },
  { id: "health", name: "Health", icon: "💊", budget: 150, color: "#fb7185" },
  { id: "entertainment", name: "Entertainment", icon: "🎬", budget: 200, color: "#34d399" },
  { id: "shopping", name: "Shopping", icon: "🛍️", budget: 400, color: "#f97316" },
  { id: "savings", name: "Savings", icon: "💰", budget: 500, color: "#e879f9" },
];

export const INITIAL_EXPENSES: Expense[] = [
  { id: "e1", categoryId: "housing", description: "Monthly rent", amount: 1850, date: "2026-06-01" },
  { id: "e2", categoryId: "food", description: "Whole Foods", amount: 142.50, date: "2026-06-02" },
  { id: "e3", categoryId: "food", description: "Chipotle", amount: 18.75, date: "2026-06-03" },
  { id: "e4", categoryId: "transport", description: "Metro card top-up", amount: 33.00, date: "2026-06-03" },
  { id: "e5", categoryId: "utilities", description: "Electricity bill", amount: 87.40, date: "2026-06-04" },
  { id: "e6", categoryId: "utilities", description: "Internet", amount: 79.99, date: "2026-06-04" },
  { id: "e7", categoryId: "health", description: "Pharmacy", amount: 62.15, date: "2026-06-05" },
  { id: "e8", categoryId: "entertainment", description: "Netflix + Spotify", amount: 28.98, date: "2026-06-05" },
  { id: "e9", categoryId: "shopping", description: "Amazon order", amount: 134.99, date: "2026-06-06" },
  { id: "e10", categoryId: "food", description: "Trader Joe's", amount: 98.20, date: "2026-06-07" },
  { id: "e11", categoryId: "transport", description: "Uber rides", amount: 47.60, date: "2026-06-07" },
  { id: "e12", categoryId: "savings", description: "Monthly transfer", amount: 500, date: "2026-06-01" },
  { id: "e13", categoryId: "entertainment", description: "Cinema tickets", amount: 38.00, date: "2026-06-08" },
  { id: "e14", categoryId: "food", description: "Dinner with friends", amount: 89.50, date: "2026-06-08" },
  { id: "e15", categoryId: "shopping", description: "H&M", amount: 211.40, date: "2026-06-09" },
  { id: "e16", categoryId: "health", description: "Gym membership", amount: 55.00, date: "2026-06-09" },
  { id: "e17", categoryId: "transport", description: "Gas", amount: 68.30, date: "2026-06-10" },
  { id: "e18", categoryId: "food", description: "Starbucks", amount: 24.60, date: "2026-06-10" },
];

export const MONTHLY_HISTORY = [
  { month: "Jan", spent: 3820, budget: 4350 },
  { month: "Feb", spent: 4100, budget: 4350 },
  { month: "Mar", spent: 3650, budget: 4350 },
  { month: "Apr", spent: 4280, budget: 4350 },
  { month: "May", spent: 3990, budget: 4350 },
  { month: "Jun", spent: 3489, budget: 4350 },
];
