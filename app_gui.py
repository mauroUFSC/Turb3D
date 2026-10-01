import datetime
import os
import subprocess
import sys
import threading
import traceback
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Habilitar nitidez High-DPI no Windows (evita fontes borradas em telas 1080p, 2K e 4K)
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

from ver_3d import inspecionar_modelo_npz, gerar_visualizacao_3d, resolver_caminho_base


class AppVisualizador3D(tk.Tk):
    def __init__(self, caminho_inicial=None):
        super().__init__()

        self.base_dir = resolver_caminho_base()
        self.caminho_npz_var = tk.StringVar()
        self.caminho_saida_var = tk.StringVar()
        self.abrir_navegador_var = tk.BooleanVar(value=True)
        self.salvar_index_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Selecione um arquivo de modelo .npz para começar.")
        self.info_modelo = None
        self.ultimo_html_gerado = None
        self.gerando = False

        self._configurar_janela()
        self._configurar_estilos()
        self._criar_interface()

        # Carregar arquivo inicial se fornecido via argumento ou se existir modelo padrão
        if caminho_inicial and Path(caminho_inicial).is_file():
            self._selecionar_arquivo(Path(caminho_inicial).resolve())
        else:
            modelo_padrao = self.base_dir / "modelo_reservatorio_3d.npz"
            if modelo_padrao.is_file():
                self._selecionar_arquivo(modelo_padrao)

    def _configurar_janela(self):
        self.title("Visualizador 3D — Modelo Turbidítico & Reservatórios")
        self.geometry("780x820")
        self.minsize(700, 680)
        self.configure(bg="#f1f5f9")

        # Ícone da aplicação
        icone_bundle = Path(getattr(sys, "_MEIPASS", self.base_dir)) / "app_icon.ico"
        icone_local = self.base_dir / "app_icon.ico"
        icone_path = icone_bundle if icone_bundle.is_file() else icone_local
        if icone_path.is_file():
            try:
                self.iconbitmap(str(icone_path))
            except Exception:
                pass

    def _configurar_estilos(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("vista")
        except Exception:
            try:
                self.style.theme_use("clam")
            except Exception:
                pass

        # Configurações de fontes
        self.font_header = ("Segoe UI", 14, "bold")
        self.font_sub = ("Segoe UI", 9)
        self.font_section = ("Segoe UI", 10, "bold")
        self.font_normal = ("Segoe UI", 9)
        self.font_mono = ("Consolas", 8)
        self.font_btn_bold = ("Segoe UI", 10, "bold")

        # Cores customizadas ttk
        self.style.configure("Card.TFrame", background="#ffffff", relief="flat")
        self.style.configure("Section.TLabelframe", background="#ffffff", font=self.font_section)
        self.style.configure("Section.TLabelframe.Label", background="#ffffff", foreground="#0f172a", font=self.font_section)

        self.style.configure("Primary.TButton", font=self.font_btn_bold, padding=(12, 8))
        self.style.configure("Secondary.TButton", font=self.font_normal, padding=(8, 4))
        self.style.configure("Action.TButton", font=self.font_normal, padding=(8, 4))

    def _criar_interface(self):
        # Frame principal com barra de rolagem se a tela for pequena
        main_container = tk.Frame(self, bg="#f1f5f9")
        main_container.pack(fill="both", expand=True)

        canvas = tk.Canvas(main_container, bg="#f1f5f9", highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas, bg="#f1f5f9", padx=16, pady=12)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)

        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 1. Header Superior
        self._criar_cabecalho(self.scrollable_frame)

        # 2. Card: Seleção de Arquivo NPZ
        self._criar_secao_selecao(self.scrollable_frame)

        # 3. Card: Inspeção do Modelo Selecionado
        self._criar_secao_inspecao(self.scrollable_frame)

        # 4. Card: Configurações de Saída
        self._criar_secao_saida(self.scrollable_frame)

        # 5. Card: Ação Principal & Progresso
        self._criar_secao_acao(self.scrollable_frame)

        # 6. Card: Log de Execução
        self._criar_secao_log(self.scrollable_frame)

    def _criar_cabecalho(self, parent):
        header_card = tk.Frame(parent, bg="#1e293b", relief="flat", bd=0, padx=16, pady=14)
        header_card.pack(fill="x", pady=(0, 10))

        title_lbl = tk.Label(
            header_card,
            text="🌊 MODELO TURBIDÍTICO 3D — VISUALIZADOR",
            font=self.font_header,
            bg="#1e293b",
            fg="#f8fafc",
            anchor="w",
        )
        title_lbl.pack(fill="x")

        sub_lbl = tk.Label(
            header_card,
            text="Carregamento genérico de arquivos de dados .npz com visualização tridimensional interativa",
            font=self.font_sub,
            bg="#1e293b",
            fg="#94a3b8",
            anchor="w",
        )
        sub_lbl.pack(fill="x", pady=(3, 0))

    def _criar_secao_selecao(self, parent):
        frame = tk.LabelFrame(
            parent,
            text=" 1. Arquivo de Dados de Entrada (.npz) ",
            font=self.font_section,
            bg="#ffffff",
            fg="#1e293b",
            padx=14,
            pady=12,
            relief="solid",
            bd=1,
        )
        frame.pack(fill="x", pady=6)

        desc_lbl = tk.Label(
            frame,
            text="Selecione qualquer arquivo .npz contendo malhas 3D (ex: modelo_reservatorio_3d.npz):",
            font=self.font_normal,
            bg="#ffffff",
            fg="#475569",
            anchor="w",
        )
        desc_lbl.pack(fill="x", pady=(0, 6))

        box_input = tk.Frame(frame, bg="#ffffff")
        box_input.pack(fill="x")

        self.entry_npz = ttk.Entry(box_input, textvariable=self.caminho_npz_var, font=self.font_normal)
        self.entry_npz.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ttk.Button(
            box_input,
            text="📂 Procurar...",
            style="Secondary.TButton",
            command=self._procurar_arquivo,
        )
        btn_browse.pack(side="left", padx=(0, 6))

        btn_padrao = ttk.Button(
            box_input,
            text="🔄 Modelo Padrão",
            style="Secondary.TButton",
            command=self._carregar_modelo_padrao,
        )
        btn_padrao.pack(side="left")

    def _criar_secao_inspecao(self, parent):
        self.frame_inspecao = tk.LabelFrame(
            parent,
            text=" 2. Informações do Modelo Selecionado ",
            font=self.font_section,
            bg="#ffffff",
            fg="#1e293b",
            padx=14,
            pady=10,
            relief="solid",
            bd=1,
        )
        self.frame_inspecao.pack(fill="x", pady=6)

        # Labels de informações
        self.lbl_info_arquivo = tk.Label(
            self.frame_inspecao,
            text="📁 Arquivo: Nenhum arquivo selecionado.",
            font=self.font_normal,
            bg="#ffffff",
            fg="#64748b",
            anchor="w",
        )
        self.lbl_info_arquivo.pack(fill="x", pady=1)

        self.lbl_info_grade = tk.Label(
            self.frame_inspecao,
            text="📏 Dimensões da Grade: —",
            font=self.font_normal,
            bg="#ffffff",
            fg="#64748b",
            anchor="w",
        )
        self.lbl_info_grade.pack(fill="x", pady=1)

        self.lbl_info_espaco = tk.Label(
            self.frame_inspecao,
            text="🌐 Extensão Espacial: —",
            font=self.font_normal,
            bg="#ffffff",
            fg="#64748b",
            anchor="w",
        )
        self.lbl_info_espaco.pack(fill="x", pady=1)

        self.lbl_info_props = tk.Label(
            self.frame_inspecao,
            text="📊 Propriedades Tridimensionais: —",
            font=self.font_normal,
            bg="#ffffff",
            fg="#64748b",
            anchor="w",
            wraplength=700,
            justify="left",
        )
        self.lbl_info_props.pack(fill="x", pady=2)

    def _criar_secao_saida(self, parent):
        frame = tk.LabelFrame(
            parent,
            text=" 3. Configurações de Saída ",
            font=self.font_section,
            bg="#ffffff",
            fg="#1e293b",
            padx=14,
            pady=10,
            relief="solid",
            bd=1,
        )
        frame.pack(fill="x", pady=6)

        lbl_saida = tk.Label(
            frame,
            text="Arquivo HTML de Saída (Standalone):",
            font=self.font_normal,
            bg="#ffffff",
            fg="#475569",
            anchor="w",
        )
        lbl_saida.pack(fill="x", pady=(0, 4))

        box_saida = tk.Frame(frame, bg="#ffffff")
        box_saida.pack(fill="x", pady=(0, 8))

        self.entry_saida = ttk.Entry(box_saida, textvariable=self.caminho_saida_var, font=self.font_normal)
        self.entry_saida.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_saida = ttk.Button(
            box_saida,
            text="Alterar...",
            style="Secondary.TButton",
            command=self._escolher_destino_saida,
        )
        btn_saida.pack(side="left")

        box_checks = tk.Frame(frame, bg="#ffffff")
        box_checks.pack(fill="x")

        chk_navegador = ttk.Checkbutton(
            box_checks,
            text="🌐 Abrir automaticamente no navegador ao concluir",
            variable=self.abrir_navegador_var,
        )
        chk_navegador.pack(side="left", padx=(0, 16))

        chk_index = ttk.Checkbutton(
            box_checks,
            text="💾 Salvar cópia como index.html na mesma pasta",
            variable=self.salvar_index_var,
        )
        chk_index.pack(side="left")

    def _criar_secao_acao(self, parent):
        frame = tk.LabelFrame(
            parent,
            text=" 4. Geração & Visualização ",
            font=self.font_section,
            bg="#ffffff",
            fg="#1e293b",
            padx=14,
            pady=12,
            relief="solid",
            bd=1,
        )
        frame.pack(fill="x", pady=6)

        # Botão principal
        self.btn_gerar = tk.Button(
            frame,
            text="🚀 GERAR VISUALIZAÇÃO 3D INTERATIVA",
            font=self.font_btn_bold,
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=16,
            pady=10,
            cursor="hand2",
            command=self._iniciar_geracao,
        )
        self.btn_gerar.pack(fill="x", pady=(0, 10))

        # Barra de progresso
        self.progresso_bar = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.progresso_bar.pack(fill="x", pady=(0, 6))

        # Status label
        self.lbl_status = tk.Label(
            frame,
            textvariable=self.status_var,
            font=self.font_normal,
            bg="#ffffff",
            fg="#0369a1",
            anchor="w",
        )
        self.lbl_status.pack(fill="x", pady=(0, 6))

        # Botões de ações pós-geração
        self.box_acoes_pos = tk.Frame(frame, bg="#ffffff")
        self.box_acoes_pos.pack(fill="x")

        self.btn_abrir_navegador = ttk.Button(
            self.box_acoes_pos,
            text="🌐 Abrir no Navegador",
            style="Action.TButton",
            state="disabled",
            command=self._abrir_no_navegador,
        )
        self.btn_abrir_navegador.pack(side="left", padx=(0, 8))

        self.btn_abrir_pasta = ttk.Button(
            self.box_acoes_pos,
            text="📁 Abrir Pasta no Explorer",
            style="Action.TButton",
            state="disabled",
            command=self._abrir_pasta_explorer,
        )
        self.btn_abrir_pasta.pack(side="left")

    def _criar_secao_log(self, parent):
        frame = tk.LabelFrame(
            parent,
            text=" 5. Log de Execução ",
            font=self.font_section,
            bg="#ffffff",
            fg="#1e293b",
            padx=14,
            pady=8,
            relief="solid",
            bd=1,
        )
        frame.pack(fill="both", expand=True, pady=6)

        box_ctrl = tk.Frame(frame, bg="#ffffff")
        box_ctrl.pack(fill="x", pady=(0, 4))

        btn_limpar = ttk.Button(
            box_ctrl,
            text="Limpar Log",
            style="Secondary.TButton",
            command=self._limpar_log,
        )
        btn_limpar.pack(side="right")

        self.txt_log = tk.Text(
            frame,
            height=6,
            font=self.font_mono,
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#ffffff",
            relief="flat",
            wrap="word",
        )
        scroll_log = ttk.Scrollbar(frame, orient="vertical", command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scroll_log.set)

        self.txt_log.pack(side="left", fill="both", expand=True)
        scroll_log.pack(side="right", fill="y")

    def log(self, mensagem: str):
        """Adiciona uma mensagem com timestamp ao console de log."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        linha = f"[{timestamp}] {mensagem}\n"
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", linha)
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _limpar_log(self):
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")

    def _carregar_modelo_padrao(self):
        padrao = self.base_dir / "modelo_reservatorio_3d.npz"
        if padrao.is_file():
            self._selecionar_arquivo(padrao)
        else:
            messagebox.showwarning(
                "Aviso",
                f"O arquivo padrão não foi encontrado em:\n{padrao}\n\nPor favor, utilize o botão 'Procurar...' para selecionar seu arquivo .npz."
            )

    def _procurar_arquivo(self):
        caminho = filedialog.askopenfilename(
            title="Selecione o arquivo de modelo (.npz)",
            filetypes=[
                ("Arquivos NumPy (*.npz)", "*.npz"),
                ("Todos os arquivos (*.*)", "*.*"),
            ],
            initialdir=str(self.base_dir),
        )
        if caminho:
            self._selecionar_arquivo(Path(caminho))

    def _escolher_destino_saida(self):
        caminho = filedialog.asksaveasfilename(
            title="Salvar Visualização HTML em...",
            defaultextension=".html",
            filetypes=[
                ("Arquivo HTML (*.html)", "*.html"),
                ("Todos os arquivos (*.*)", "*.*"),
            ],
            initialfile=Path(self.caminho_saida_var.get()).name if self.caminho_saida_var.get() else "index.html",
            initialdir=str(Path(self.caminho_saida_var.get()).parent) if self.caminho_saida_var.get() else str(self.base_dir),
        )
        if caminho:
            self.caminho_saida_var.set(str(Path(caminho).resolve()))
            self.log(f"Destino de saída alterado para: {caminho}")

    def _selecionar_arquivo(self, caminho: Path):
        self.caminho_npz_var.set(str(caminho))
        self.log(f"Arquivo selecionado: {caminho.name} ({caminho})")

        # Configurar destino padrão baseado no nome e pasta do arquivo
        destino_padrao = caminho.parent / f"{caminho.stem}_3d.html"
        self.caminho_saida_var.set(str(destino_padrao))

        # Inspecionar dados em background para não travar a GUI
        threading.Thread(target=self._executar_inspecao, args=(caminho,), daemon=True).start()

    def _executar_inspecao(self, caminho: Path):
        try:
            self.status_var.set(f"Inspecionando {caminho.name}...")
            info = inspecionar_modelo_npz(caminho)
            self.after(0, self._atualizar_info_modelo, info)
        except Exception as e:
            err_msg = str(e)
            self.after(0, self._exibir_erro_inspecao, err_msg)

    def _atualizar_info_modelo(self, info: dict):
        self.info_modelo = info
        nome = info["nome_arquivo"]
        tamanho = info["tamanho_mb"]
        nx, ny, nz = info["nx"], info["ny"], info["nz"]
        total = info["total_celulas"]
        props = info["propriedades"]

        self.lbl_info_arquivo.config(
            text=f"📁 Arquivo: {nome}  |  Tamanho: {tamanho:.2f} MB",
            fg="#0f172a",
        )
        self.lbl_info_grade.config(
            text=f"📏 Dimensões da Grade: Nx = {nx:,}  |  Ny = {ny:,}  |  Nz = {nz:,}  (Total: {total:,} células)",
            fg="#0f172a",
        )
        self.lbl_info_espaco.config(
            text=(
                f"🌐 Extensão Espacial: X [{info['x_min']:.1f} a {info['x_max']:.1f} m, dx={info['dx']:.1f}m]  |  "
                f"Y [{info['y_min']:.1f} a {info['y_max']:.1f} m, dy={info['dy']:.1f}m]  |  "
                f"Z [{info['z_min']:.1f} a {info['z_max']:.1f} m, dz={info['dz']:.1f}m]"
            ),
            fg="#0f172a",
        )

        lista_props_str = ", ".join([p["label"] for p in props[:8]])
        if len(props) > 8:
            lista_props_str += f" (+{len(props) - 8} outras)"

        self.lbl_info_props.config(
            text=f"📊 Propriedades ({len(props)} encontradas): {lista_props_str}",
            fg="#0f172a",
        )

        self.status_var.set(f"Pronto para gerar! Grade {nx}x{ny}x{nz} com {len(props)} propriedades identificadas.")
        self.log(f"Inspeção concluída: {len(props)} propriedades identificadas na grade {nx}x{ny}x{nz}.")

    def _exibir_erro_inspecao(self, err_msg: str):
        self.info_modelo = None
        self.lbl_info_arquivo.config(text="📁 Arquivo: Erro ao carregar arquivo.", fg="#dc2626")
        self.lbl_info_grade.config(text="📏 Dimensões da Grade: —", fg="#64748b")
        self.lbl_info_espaco.config(text="🌐 Extensão Espacial: —", fg="#64748b")
        self.lbl_info_props.config(text=f"Erro: {err_msg}", fg="#dc2626")
        self.status_var.set("Erro na inspeção do arquivo .npz.")
        self.log(f"ERRO de inspeção: {err_msg}")
        messagebox.showerror("Erro ao Inspecionar Arquivo", f"Não foi possível ler o arquivo .npz selecionado:\n\n{err_msg}")

    def _iniciar_geracao(self):
        if self.gerando:
            return

        caminho_npz = self.caminho_npz_var.get().strip()
        if not caminho_npz or not Path(caminho_npz).is_file():
            messagebox.showwarning(
                "Arquivo Obrigatório",
                "Por favor, selecione um arquivo de dados .npz válido antes de prosseguir."
            )
            return

        caminho_saida = self.caminho_saida_var.get().strip()
        if not caminho_saida:
            caminho_saida = str(Path(caminho_npz).parent / "index.html")
            self.caminho_saida_var.set(caminho_saida)

        self.gerando = True
        self.btn_gerar.config(
            state="disabled",
            text="⏳ PROCESSANDO MODELO 3D...",
            bg="#64748b",
            cursor="watch",
        )
        self.progresso_bar["value"] = 5
        self.status_var.set("Iniciando geração da visualização 3D...")
        self.btn_abrir_navegador.config(state="disabled")
        self.btn_abrir_pasta.config(state="disabled")

        abrir_navegador = self.abrir_navegador_var.get()
        salvar_index = self.salvar_index_var.get()

        # Executa em thread separada
        thread = threading.Thread(
            target=self._processar_em_thread,
            args=(caminho_npz, caminho_saida, abrir_navegador, salvar_index),
            daemon=True,
        )
        thread.start()

    def _processar_em_thread(self, caminho_npz, caminho_saida, abrir_navegador, salvar_index):
        try:
            def cb_prog(percent, status):
                self.after(0, self._atualizar_progresso, percent, status)

            def cb_log(msg):
                self.after(0, self.log, msg)

            destino = gerar_visualizacao_3d(
                caminho_npz=caminho_npz,
                arquivo_saida=caminho_saida,
                abrir_navegador=abrir_navegador,
                salvar_copia_index=salvar_index,
                callback_progresso=cb_prog,
                callback_log=cb_log,
            )
            self.after(0, self._concluir_geracao, destino)
        except Exception as e:
            tb = traceback.format_exc()
            self.after(0, self._falhar_geracao, str(e), tb)

    def _atualizar_progresso(self, percent: int, status: str):
        self.progresso_bar["value"] = percent
        self.status_var.set(status)

    def _concluir_geracao(self, destino: Path):
        self.gerando = False
        self.ultimo_html_gerado = destino
        self.progresso_bar["value"] = 100
        self.status_var.set("Visualização 3D gerada com sucesso!")
        self.btn_gerar.config(
            state="normal",
            text="🚀 GERAR VISUALIZAÇÃO 3D INTERATIVA",
            bg="#0284c7",
            cursor="hand2",
        )
        self.btn_abrir_navegador.config(state="normal")
        self.btn_abrir_pasta.config(state="normal")

        self.log(f"Pronto! Arquivo final disponível em: {destino}")

        msg = f"Visualização 3D gerada com sucesso!\n\nArquivo: {destino.name}\nLocal: {destino.parent}"
        if not self.abrir_navegador_var.get():
            msg += "\n\nVocê pode abrir no navegador usando o botão 'Abrir no Navegador'."
        messagebox.showinfo("Sucesso", msg)

    def _falhar_geracao(self, err_msg: str, tb: str):
        self.gerando = False
        self.progresso_bar["value"] = 0
        self.status_var.set(f"Erro: {err_msg}")
        self.btn_gerar.config(
            state="normal",
            text="🚀 GERAR VISUALIZAÇÃO 3D INTERATIVA",
            bg="#0284c7",
            cursor="hand2",
        )
        self.log(f"FALHA NA GERAÇÃO:\n{tb}")
        messagebox.showerror(
            "Erro na Geração 3D",
            f"Ocorreu um erro durante o processamento do modelo:\n\n{err_msg}\n\nConsulte o Log de Execução para detalhes."
        )

    def _abrir_no_navegador(self):
        if self.ultimo_html_gerado and self.ultimo_html_gerado.is_file():
            self.log(f"Abrindo navegador para: {self.ultimo_html_gerado.name}")
            webbrowser.open(self.ultimo_html_gerado.as_uri())
        else:
            saida = Path(self.caminho_saida_var.get())
            if saida.is_file():
                self.log(f"Abrindo navegador para: {saida.name}")
                webbrowser.open(saida.as_uri())
            else:
                messagebox.showwarning("Aviso", "O arquivo HTML ainda não foi gerado.")

    def _abrir_pasta_explorer(self):
        alvo = self.ultimo_html_gerado or Path(self.caminho_saida_var.get())
        pasta = alvo.parent if alvo else self.base_dir
        if pasta.exists():
            self.log(f"Abrindo pasta no Explorer: {pasta}")
            try:
                if alvo.is_file():
                    subprocess.Popen(f'explorer /select,"{alvo}"')
                else:
                    subprocess.Popen(f'explorer "{pasta}"')
            except Exception as e:
                self.log(f"Erro ao abrir explorer: {e}")
                os.startfile(str(pasta))


def iniciar_gui(caminho_inicial=None):
    # Se passado via argumento de linha de comando ou drag-and-drop no Windows
    if caminho_inicial is None and len(sys.argv) > 1:
        cand = sys.argv[1]
        if not cand.startswith("-") and Path(cand).is_file():
            caminho_inicial = cand

    app = AppVisualizador3D(caminho_inicial=caminho_inicial)
    app.mainloop()


if __name__ == "__main__":
    iniciar_gui()
