# 📋 Guia Completo - Copiar Templates do Mapa_Controle

## 🎯 RESUMO RÁPIDO

Você precisa copiar os templates do **Mapa_Controle** para o **Diario_obra** (sistema central).

> **📌 Nota:** Todos os caminhos são relativos ao workspace: `C:\Users\victo\OneDrive\Área de Trabalho\Lplan_Sistema\`

---

## 📁 COPIA 1: Templates do Suprimentos

### **DE (Origem):**
```
Lplan_Sistema\Mapa_Controle\templates\suprimentos\
```

### **PARA (Destino):**
```
Lplan_Sistema\Diario_obra\suprimentos\templates\suprimentos\
```

### **Arquivos a copiar:**
1. `mapa_engenharia.html`
2. `dashboard_2.html`
3. `importar_sienge.html`

**Como fazer:**
1. Abra o Windows Explorer
2. Vá até: `C:\Users\victo\OneDrive\Área de Trabalho\Lplan_Sistema\Mapa_Controle\templates\suprimentos\`
3. Selecione os 3 arquivos acima (Ctrl+Click)
4. Copie (Ctrl+C)
5. Vá até: `C:\Users\victo\OneDrive\Área de Trabalho\Lplan_Sistema\Diario_obra\suprimentos\templates\suprimentos\`
6. Cole (Ctrl+V)

---

## 📁 COPIA 2: Template Base do Mapa_Controle

### **DE (Origem):**
```
Lplan_Sistema\Mapa_Controle\templates\base.html
```

### **PARA (Destino):**
```
Lplan_Sistema\Diario_obra\templates\base.html
```

**Como fazer:**
1. Abra o Windows Explorer
2. Vá até: `C:\Users\victo\OneDrive\Área de Trabalho\Lplan_Sistema\Mapa_Controle\templates\`
3. Selecione `base.html`
4. Copie (Ctrl+C)
5. Vá até: `C:\Users\victo\OneDrive\Área de Trabalho\Lplan_Sistema\Diario_obra\templates\`
6. Cole (Ctrl+V)
   - ⚠️ **ATENÇÃO:** Se já existir um `base.html` no destino, você pode renomear o antigo ou substituir (depende do que você quer)

---

## 📁 COPIA 3: Templates do Accounts (se necessário)

### **DE (Origem):**
```
Lplan_Sistema\Mapa_Controle\templates\accounts\
```

### **PARA (Destino):**
```
Lplan_Sistema\Diario_obra\accounts\templates\accounts\
```

### **Arquivos a copiar:**
1. `admin_central.html`
2. `criar_obra.html`
3. `criar_usuario.html`
4. `editar_usuario.html`
5. `gerenciar_obras.html`
6. `gerenciar_usuarios.html`
7. `home.html`
8. `login.html` (⚠️ pode já existir - verifique antes)
9. `profile.html`

**Como fazer:**
1. Abra o Windows Explorer
2. Vá até: `C:\Users\victo\OneDrive\Área de Trabalho\Lplan_Sistema\Mapa_Controle\templates\accounts\`
3. Selecione TODOS os arquivos (Ctrl+A)
4. Copie (Ctrl+C)
5. Vá até: `C:\Users\victo\OneDrive\Área de Trabalho\Lplan_Sistema\Diario_obra\accounts\templates\accounts\`
6. Cole (Ctrl+V)
   - ⚠️ Se algum arquivo já existir (como `login.html`), o Windows vai perguntar se você quer substituir. Escolha conforme sua necessidade.

---

## ✅ CHECKLIST FINAL

Após copiar, verifique se existem:

- [ ] `Diario_obra\suprimentos\templates\suprimentos\mapa_engenharia.html`
- [ ] `Diario_obra\suprimentos\templates\suprimentos\dashboard_2.html`
- [ ] `Diario_obra\suprimentos\templates\suprimentos\importar_sienge.html`
- [ ] `Diario_obra\templates\base.html`
- [ ] `Diario_obra\accounts\templates\accounts\admin_central.html`
- [ ] `Diario_obra\accounts\templates\accounts\criar_obra.html`
- [ ] `Diario_obra\accounts\templates\accounts\criar_usuario.html`
- [ ] `Diario_obra\accounts\templates\accounts\editar_usuario.html`
- [ ] `Diario_obra\accounts\templates\accounts\gerenciar_obras.html`
- [ ] `Diario_obra\accounts\templates\accounts\gerenciar_usuarios.html`
- [ ] `Diario_obra\accounts\templates\accounts\home.html`
- [ ] `Diario_obra\accounts\templates\accounts\profile.html`

---

## 🚀 PRÓXIMOS PASSOS

Depois de copiar todos os templates:

1. **Entre na pasta do projeto:**
   ```powershell
   cd "C:\Users\victo\OneDrive\Área de Trabalho\Lplan_Sistema\Diario_obra"
   ```

2. **Teste o sistema:**
   ```powershell
   python manage.py runserver
   ```

3. **Acesse no navegador:**
   - `http://localhost:8000/mapa/` (Mapa de Controle)
   - `http://localhost:8000/engenharia/` (Suprimentos)
   - `http://localhost:8000/gestao/` (Gestão de Aprovações)
   - `http://localhost:8000/diario/` (Diário de Obra)

Se houver erros de template, me avise!

---

## ✅ VERIFICAÇÃO RÁPIDA

Para verificar se copiou tudo corretamente, execute no PowerShell:

```powershell
cd "C:\Users\victo\OneDrive\Área de Trabalho\Lplan_Sistema\Diario_obra"

# Verificar templates do suprimentos
Get-ChildItem "suprimentos\templates\suprimentos\*.html" | Select-Object Name

# Verificar template base
Test-Path "templates\base.html"

# Verificar templates do accounts
Get-ChildItem "accounts\templates\accounts\*.html" | Select-Object Name
```
