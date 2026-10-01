# Visualização 3D - Modelo Turbidítico (Plotly)

Visualização tridimensional volumétrica e por **fatias ortogonais interativas com 3 sliders (X, Y, Z)** do modelo geológico `modelo_turbiditico_3D.npz`.  
Pronto para execução local no **Windows 10/11**, Linux, macOS e publicação no **GitHub Pages**.

🌐 **Visualização Online (GitHub Pages):** [https://mazzutti.github.io/Turb3D/](https://mazzutti.github.io/Turb3D/)

---

## 1. Publicação no GitHub Pages

O repositório já está preparado com o arquivo `index.html` e um workflow automatizado em `.github/workflows/deploy.yml`.

### Como ativar o GitHub Pages no repositório:
1. No seu repositório no GitHub, clique na aba **Settings** (Configurações).
2. No menu lateral esquerdo, clique em **Pages**.
3. Em **Build and deployment > Source**:
   - Selecione **GitHub Actions** (recomendado — publica automaticamente em qualquer push para a branch `main`).
   - *Ou alternativa direta:* Selecione **Deploy from a branch** > Branch: `main` > Pasta: `/ (root)` > clique em **Save**.
4. Em poucos segundos, a visualização estará acessível publicamente em:  
   👉 **`https://mazzutti.github.io/Turb3D/`**

---

## 2. Clonar o Repositório

Abra o **PowerShell**, **Terminal** ou **Prompt de Comando (CMD)** e execute:

```bash
# Clonar o repositório
git clone https://github.com/mazzutti/Turb3D.git

# Entrar na pasta do projeto
cd Turb3D
```

---

## 3. Instalação no Windows

### Pré-requisitos
- Python 3.10 ou superior instalado ([python.org](https://www.python.org/downloads/)).  
  *(Na instalação, marcar a opção **"Add python.exe to PATH"**).*
- Git instalado ([git-scm.com](https://git-scm.com/)).

---

### Passo a passo (PowerShell)

Dentro da pasta `Turb3D`, execute:

```powershell
# 1. Habilitar execução de scripts para a sessão atual (caso bloqueado)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# 2. Criar ambiente virtual (.venv)
python -m venv .venv

# 3. Ativar o ambiente virtual
.venv\Scripts\Activate.ps1

# 4. Atualizar pip e instalar dependências
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> **Se preferir usar o Prompt de Comando clássico (CMD):**
> ```cmd
> python -m venv .venv
> .venv\Scripts\activate.bat
> pip install -r requirements.txt
> ```

---

## 4. Como Executar

### Opção A: Executável Windows Standalone (Sem Necessidade de Python)
O projeto inclui o executável independente **`VisualizadorTurbiditico3D.exe`** (disponível na raiz e na pasta `dist/`).
- Basta dar um **duplo clique** em `VisualizadorTurbiditico3D.exe` (ou no inicializador `Iniciar_Visualizador.bat`).
- Uma interface gráfica intuitiva será aberta para você:
  1. **Selecionar genericamente qualquer arquivo `.npz`** no seu computador (via botão *Procurar...* ou arrastando o arquivo).
  2. **Inspecionar instantaneamente o modelo:** grade 3D ($N_x \times N_y \times N_z$), limites espaciais em metros e todas as propriedades encontradas.
  3. **Escolher o arquivo HTML de saída** e opção de abertura automática no navegador.
  4. Clicar em **🚀 Gerar Visualização 3D Interativa**.

### Opção B: Interface Gráfica via Python
Com o ambiente virtual ativado, você pode abrir a interface gráfica diretamente:

```powershell
python app_gui.py
# ou com o arquivo npz já pré-selecionado:
python app_gui.py modelo_reservatorio_3d.npz
```

### Opção C: Linha de Comando (CLI)
Para gerar diretamente o HTML via terminal:

```powershell
# Carrega modelo_reservatorio_3d.npz por padrão e abre no navegador
python ver_3d.py

# Informar outro arquivo NPZ genérico:
python ver_3d.py outro_modelo.npz

# Gerar sem abrir o navegador:
python ver_3d.py --no-browser
```

---

## 5. Como Recompilar o Executável Standalone

Caso faça alterações no código e deseje recompilar o executável para Windows:

```powershell
python -m PyInstaller --clean --onefile --windowed --name "VisualizadorTurbiditico3D" --icon "app_icon.ico" --add-data "app_icon.ico;." app_gui.py
```

O novo arquivo executável será gerado em `dist/VisualizadorTurbiditico3D.exe`.

---

## 6. Controles Interativos no Navegador

- **3 Sliders Independentes de Fatias (abaixo do gráfico 3D):**
  - **Slider Z (Azul - Profundidade):** Desliza entre as camadas geológicas em profundidade.
  - **Slider Y (Verde - Inline):** Desliza o plano vertical ao longo do eixo Y.
  - **Slider X (Vermelho - Crossline):** Desliza o plano vertical ao longo do eixo X.
- **Menu Dropdown (canto superior esquerdo):**  
  Alterna instantaneamente a propriedade exibida em todas as fatias:
  - `porosity` (Porosidade)
  - `permeability` (Permeabilidade em mD)
  - `facies` (Fácies sedimentares)
  - `density`, `Vp`, `Vs`, `Sw`, `Ip`, etc.
- **Legenda Interativa (canto superior):**
  - Clique em qualquer fatia (`Fatia Z`, `Fatia X`, `Fatia Y`) para ocultá-la ou exibi-la.
  - Clique em **"Volume 3D"** para ativar a nuvem volumétrica com transparência junto com as fatias.
- **Navegação 3D:**
  - **Botão esquerdo do mouse (arrastar):** Rotação 3D em torno do volume.
  - **Scroll do mouse:** Zoom in / Zoom out.
  - **Botão direito do mouse:** Pan (deslocar a câmera).
- **Eixo Z:** Profundidade orientada conforme convenção geológica (profundidade aumenta para baixo).

---

## 7. Estrutura dos Arquivos

- `VisualizadorTurbiditico3D.exe`: Executável Windows standalone pronto para uso.
- `Iniciar_Visualizador.bat`: Inicializador em lote com detecção inteligente de ambiente.
- `app_gui.py`: Interface gráfica em Tkinter/ttk com inspeção em tempo real e geração não-bloqueante.
- `ver_3d.py`: Motor de processamento, carregador genérico de `.npz`, Plotly 3D e CLI.
- `app_icon.ico`: Ícone temático tridimensional para o executável.
- `modelo_reservatorio_3d.npz`: Arquivo de dados de referência (150×150×100 células).
- `index.html`: Arquivo interativo servido no GitHub Pages.
- `requirements.txt`: Dependências do ambiente Python (`numpy`, `plotly`, `pyinstaller`, `pillow`).
