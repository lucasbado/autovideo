import flet as ft
import asyncio
import os
import json
from datetime import datetime
from agenda_manager import criar_agenda_semanal, executar_agenda, AGENDA_PATH, obter_proxima_semana, obter_semana_atual
from batch_researcher import run_batch
from script_preparer import run_preparer, preparar_roteiro
from vault_renderer import run_renderer, renderizar_video
from vault_manager import get_files_by_status, read_markdown_file, PRODUCTION_PATH
from uploader import list_connected_accounts, gerenciar_login, remover_conta, verificar_sessao
from styles import TURBO_BLUE, TURBO_DARK, TURBO_GRAY, TURBO_GREEN, BORDER_RADIUS, ESTILOS

# --- TURBO NEON THEME ---
NEON_BLUE = "#00D2FF"
NEON_PURPLE = "#BC13FE"
NEON_GREEN = "#39FF14"

class AutoVideoApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "AutoVideo TURBO - Command Center"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.window_width = 1300
        self.page.window_height = 950
        self.page.bgcolor = "#050505"
        self.page.padding = 0
        
        # State
        self.is_running = False
        self.active_week_id, _ = obter_semana_atual()
        self.selected_week_id = self.active_week_id
        
        # UI Components
        self.log_area = ft.ListView(expand=True, spacing=5, padding=10, auto_scroll=True)
        self.content_area = ft.Container(expand=True, padding=30, bgcolor="transparent")
        
        self.rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=110,
            min_extended_width=220,
            leading=ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.ROCKET_LAUNCH, color=NEON_BLUE, size=45),
                    ft.Text("TURBO", size=12, weight="bold", color=NEON_BLUE, style=ft.TextStyle(letter_spacing=2))
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding(top=30, bottom=30)
            ),
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.AUTO_GRAPH, label="Dashboard"),
                ft.NavigationRailDestination(icon=ft.Icons.LAYERS, label="Content Vault"),
                ft.NavigationRailDestination(icon=ft.Icons.HUB, label="Accounts"),
                ft.NavigationRailDestination(icon=ft.Icons.CODE, label="System Logs"),
            ],
            on_change=self.handle_nav_change,
            bgcolor="#0A0A0A",
            indicator_color=ft.Colors.with_opacity(0.1, NEON_BLUE),
            selected_label_text_style=ft.TextStyle(color=NEON_BLUE, weight="bold"),
        )

        self.init_layout()
        self.refresh_current_view()

    def init_layout(self):
        self.page.add(
            ft.Row(
                [
                    self.rail,
                    ft.VerticalDivider(width=1, color="#1A1A1A"),
                    self.content_area,
                ],
                expand=True,
                spacing=0
            )
        )

    def log(self, message, color="white"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.controls.append(
            ft.Text(f"[{timestamp}] {message}", color=color, size=13, font_family="Consolas")
        )
        self.page.update()

    async def run_task(self, coro, task_name):
        if self.is_running:
            self.log(f"⚠️ Outra tarefa em andamento...", "yellow")
            return
            
        self.is_running = True
        self.log(f"🚀 Iniciando: {task_name}", NEON_BLUE)
        try:
            await coro
            self.log(f"✅ Finalizado: {task_name}", NEON_GREEN)
        except Exception as e:
            self.log(f"❌ Erro em {task_name}: {e}", "red")
        finally:
            self.is_running = False
            self.refresh_current_view()
            self.page.update()

    def handle_nav_change(self, e):
        self.refresh_current_view()
        self.page.update()

    def refresh_current_view(self):
        idx = self.rail.selected_index
        if idx == 0: self.show_dashboard()
        elif idx == 1: self.show_vault()
        elif idx == 2: self.show_accounts()
        elif idx == 3: self.show_logs()

    # --- VIEWS ---

    def show_dashboard(self):
        queue_count = len(get_files_by_status("research_completed")) + len(get_files_by_status("script_ready"))
        ready_count = len(get_files_by_status("rendered"))
        active_accs = len(list_connected_accounts())

        # Week Switcher
        def change_week(e):
            self.selected_week_id = e.control.value
            self.refresh_current_view()

        week_options = []
        if os.path.exists(AGENDA_PATH):
            files = [f.replace(".json", "") for f in os.listdir(AGENDA_PATH) if f.endswith(".json")]
            # Sort by week ID
            files.sort(reverse=True)
            week_options = [ft.dropdown.Option(f) for f in files[:4]] # Show last 4 weeks

        week_selector = ft.Dropdown(
            label="PRODUCTION WEEK",
            options=week_options,
            value=self.selected_week_id,
            on_select=change_week,
            width=200,
            border_color=NEON_BLUE
        )

        # Discovery Queue Preview
        discovery_items = ft.Row(scroll=ft.ScrollMode.ALWAYS, spacing=10)
        discovery_file = "data/discovery_queue.json"
        if os.path.exists(discovery_file):
            with open(discovery_file, "r", encoding="utf-8") as f:
                try:
                    queue = json.load(f)
                    for q in queue[:10]:
                        discovery_items.controls.append(
                            ft.Chip(
                                label=ft.Text(q, size=11),
                                bgcolor="#1A1A1A",
                                leading=ft.Icon(ft.Icons.AUTO_AWESOME, size=14, color=NEON_PURPLE),
                                border_side=ft.BorderSide(1, NEON_PURPLE)
                            )
                        )
                except: pass

        self.content_area.content = ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("SYSTEM STATUS", size=12, color=NEON_BLUE, weight="bold", style=ft.TextStyle(letter_spacing=2)),
                    ft.Text("Command Center", size=35, weight="bold"),
                ]),
                ft.Row([
                    week_selector,
                    ft.IconButton(ft.Icons.REFRESH, on_click=lambda _: self.refresh_current_view(), icon_color="grey")
                ], spacing=10)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            ft.Divider(height=30, color="transparent"),
            
            ft.Row([
                self.create_metric_card("RESEARCH QUEUE", str(queue_count), ft.Icons.QUERY_STATS, NEON_BLUE),
                self.create_metric_card("READY FOR POST", str(ready_count), ft.Icons.PLAY_CIRCLE_FILL, NEON_GREEN),
                self.create_metric_card("ACTIVE CHANNELS", str(active_accs), ft.Icons.STREAM, NEON_PURPLE),
            ], spacing=25),
            
            ft.Divider(height=40, color="transparent"),

            ft.Row([
                ft.Column([
                    ft.Text("PRODUCTION CONTROLS", size=14, weight="bold", color="grey"),
                    ft.Row([
                        ft.Button("RESEARCH BATCH", icon=ft.Icons.SEARCH, bgcolor=NEON_BLUE, color="black", 
                                          on_click=lambda _: self.page.run_task(self.run_task, run_batch(3), "Research")),
                        ft.Button("PREPARE SCRIPTS", icon=ft.Icons.DESCRIPTION, bgcolor=NEON_PURPLE, color="black",
                                          on_click=lambda _: self.page.run_task(self.run_task, run_preparer(), "Script Prep")),
                        ft.Button("RENDER TURBO", icon=ft.Icons.BOLT, bgcolor=NEON_GREEN, color="black",
                                          on_click=lambda _: self.page.run_task(self.run_task, run_renderer(), "Render")),
                    ], spacing=15),
                    
                    ft.Divider(height=20, color="transparent"),
                    
                    ft.Text("AGENDA AUTOMATION", size=14, weight="bold", color="grey"),
                    ft.Row([
                        ft.Button("GENERATE WEEKLY", icon=ft.Icons.EVENT_REPEAT, 
                                           on_click=lambda _: self.page.run_task(self.run_task, criar_agenda_semanal(), "Full Production Cycle")),
                        ft.Button("EXECUTE SCHEDULE", icon=ft.Icons.PLAY_ARROW,
                                           on_click=lambda _: self.page.run_task(self.run_task, executar_agenda(self.selected_week_id), "End-to-End Production")),
                    ], spacing=15),
                ], expand=True),
                
                ft.Column([
                    ft.Text("AI DISCOVERY QUEUE", size=14, weight="bold", color="grey"),
                    ft.Container(discovery_items, padding=10, bgcolor="#0D0D0D", border_radius=10, width=400)
                ])
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START),

            ft.Divider(height=40, color="#1A1A1A"),
            
            ft.Text("WEEKLY PRODUCTION BOARD", size=16, weight="bold", color=NEON_BLUE),
            ft.Container(
                content=self.get_agenda_list(),
                padding=10,
                bgcolor="#0D0D0D",
                border_radius=15,
                border=ft.Border.all(1, "#1A1A1A"),
                height=400
            )
        ], scroll=ft.ScrollMode.ALWAYS, expand=True)

    def show_vault(self):
        files = []
        if os.path.exists(PRODUCTION_PATH):
            files = [f for f in os.listdir(PRODUCTION_PATH) if f.endswith(".md")]
            
        list_items = ft.ListView(expand=True, spacing=10)
        for f in files:
            filepath = os.path.join(PRODUCTION_PATH, f)
            meta, _ = read_markdown_file(filepath)
            status = meta.get("status", "unknown")
            
            color = NEON_GREEN if status == "rendered" else NEON_BLUE if status == "script_ready" else "yellow"
            
            list_items.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.ARTICLE, color=color, size=30),
                        ft.Column([
                            ft.Text(meta.get("tema", f), size=16, weight="bold"),
                            ft.Row([
                                ft.Text(f"STATUS: {status.upper()}", size=10, color=color, weight="bold"),
                                ft.Text("|", size=10, color="grey"),
                                ft.Text(f"NICHE: {meta.get('nicho')}", size=10, color="grey"),
                            ], spacing=10)
                        ], expand=True),
                        ft.IconButton(ft.Icons.REMOVE_RED_EYE, icon_color=NEON_BLUE, 
                                      on_click=lambda _, p=filepath: self.show_markdown_dialog(p))
                    ]),
                    padding=15,
                    bgcolor="#111111",
                    border_radius=10,
                    border=ft.Border.all(1, "#1A1A1A")
                )
            )

        self.content_area.content = ft.Column([
            ft.Text("CONTENT VAULT", size=30, weight="bold", color=NEON_BLUE),
            ft.Text("Archive of research, scripts and produced assets", size=14, color="grey"),
            ft.Divider(height=20, color="#1A1A1A"),
            list_items
        ])

    def show_accounts(self):
        self.refresh_accounts()

    def refresh_accounts(self):
        accounts = list_connected_accounts()
        account_items = ft.Column(spacing=15, scroll=ft.ScrollMode.ALWAYS, expand=True)
        
        async def refresh_acc(perfil):
            await gerenciar_login(perfil)
            self.refresh_accounts()

        for acc in accounts:
            status = verificar_sessao(acc)
            is_active = status == "Conectado"
            status_color = NEON_GREEN if is_active else "red"
            
            account_items.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=40, color=NEON_BLUE if is_active else "grey"),
                            padding=5,
                        ),
                        ft.Column([
                            ft.Text(acc.upper(), size=18, weight="bold", style=ft.TextStyle(letter_spacing=1)),
                            ft.Row([
                                ft.Container(width=8, height=8, bgcolor=status_color, border_radius=4),
                                ft.Text(status, color=status_color, size=12),
                            ], spacing=10),
                        ], spacing=2, expand=True),
                        ft.Row([
                            ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh Session", 
                                          on_click=lambda e, a=acc: self.page.run_task(self.run_task(refresh_acc(a), f"Login {a}"))),
                            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red", tooltip="Remove Account",
                                          on_click=lambda e, a=acc: self.confirm_delete_account(a)),
                        ])
                    ]),
                    padding=20,
                    bgcolor="#111111",
                    border_radius=15,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.1, status_color))
                )
            )

        if not accounts:
            account_items.controls.append(ft.Text("No accounts connected. Use the button above to link a TikTok profile.", color="grey", italic=True))

        self.content_area.content = ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("ACCOUNT MANAGER", size=30, weight="bold", color=NEON_BLUE),
                    ft.Text("Direct TikTok session management", size=14, color="grey"),
                ]),
                ft.Button("CONNECT ACCOUNT", icon=ft.Icons.ADD, bgcolor=NEON_BLUE, color="black", on_click=self.add_account_dialog)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=30, color="#1A1A1A"),
            account_items
        ])
        self.page.update()

    def show_logs(self):
        self.content_area.content = ft.Column([
            ft.Row([
                ft.Text("SYSTEM TERMINAL", size=30, weight="bold", color=NEON_BLUE),
                ft.IconButton(ft.Icons.DELETE_SWEEP, on_click=lambda _: self.log_area.controls.clear() or self.page.update())
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(
                content=self.log_area,
                expand=True,
                bgcolor="#000000",
                border_radius=15,
                padding=10,
                border=ft.Border.all(1, "#1A1A1A"),
            )
        ])

    def create_metric_card(self, title, value, icon, color):
        return ft.Container(
            content=ft.Column([
                ft.Row([ft.Icon(icon, color=color, size=18), ft.Text(title, size=11, weight="bold", color="grey", style=ft.TextStyle(letter_spacing=1))]),
                ft.Text(value, size=35, weight="bold", color="white"),
            ], spacing=5),
            padding=25,
            bgcolor="#111111",
            border=ft.Border.all(1, "#222222"),
            border_radius=15,
            width=280,
            shadow=ft.BoxShadow(blur_radius=15, color=ft.Colors.with_opacity(0.05, color))
        )

    def get_agenda_list(self):
        agenda_items = ft.ListView(spacing=10, expand=True)
        filepath = os.path.join(AGENDA_PATH, f"{self.selected_week_id}.json")
        
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                slots = data.get("slots", [])
                for i, slot in enumerate(slots):
                    # Cores e Ícones de Status
                    status = slot.get("status", "planejado")
                    if status == "rendered":
                        color = NEON_GREEN
                        icon = ft.Icons.CHECK_CIRCLE
                    elif status == "script_ready":
                        color = NEON_PURPLE
                        icon = ft.Icons.DESCRIPTION
                    elif status == "pesquisado":
                        color = NEON_BLUE
                        icon = ft.Icons.SEARCH
                    elif status == "error":
                        color = "red"
                        icon = ft.Icons.ERROR_OUTLINE
                    else:
                        color = "yellow"
                        icon = ft.Icons.SCHEDULE

                    perfil = slot.get("perfil") or "NOT SET"
                    
                    agenda_items.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Container(width=5, height=40, bgcolor=color, border_radius=2),
                                ft.Column([
                                    ft.Text(slot["tema"], size=14, weight="bold", no_wrap=True),
                                    ft.Row([
                                        ft.Text(f"{slot['data']} | {slot['periodo']}", size=11, color="grey"),
                                        ft.Text("|", size=11, color="grey"),
                                        ft.Text(f"POST: {slot.get('horario', '--:--')}", size=11, color="grey"),
                                        ft.Text("|", size=11, color="grey"),
                                        ft.Text(f"CHANNEL: {perfil}", size=11, color=NEON_BLUE if slot.get("perfil") else "grey"),
                                    ], spacing=10)
                                ], expand=True, spacing=2),
                                ft.Icon(icon, color=color, size=20),
                                ft.Text(status.upper(), size=10, color=color, weight="bold"),
                                ft.Row([
                                    ft.IconButton(ft.Icons.RESTART_ALT, icon_size=18, icon_color="red", tooltip="Resetar Slot",
                                                  visible=(status == "error"), on_click=lambda _, idx=i: self.reset_slot(idx)),
                                    ft.IconButton(ft.Icons.EDIT_CALENDAR, icon_size=20, icon_color="grey", tooltip="Editar Tema/Post",
                                                  on_click=lambda _, idx=i: self.open_schedule_dialog(idx)),
                                ], spacing=0),
                            ], spacing=15),
                            padding=15,
                            bgcolor="#0A0A0A",
                            border_radius=10,
                        )
                    )
        else:
            agenda_items.controls.append(ft.Text("Production board is empty. Generate a weekly agenda to start.", color="grey", italic=True))
            
        return agenda_items

    def reset_slot(self, slot_index):
        filepath = os.path.join(AGENDA_PATH, f"{self.selected_week_id}.json")
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["slots"][slot_index]["status"] = "planejado"
            data["slots"][slot_index]["arquivo_vault"] = ""

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        self.log(f"🔄 Slot resetado: {data['slots'][slot_index]['tema']}", "yellow")
        self.refresh_current_view()

    def open_schedule_dialog(self, slot_index):
        from ideator_new import NICHOS, gerar_tema_factual
        filepath = os.path.join(AGENDA_PATH, f"{self.selected_week_id}.json")
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            slot = data["slots"][slot_index]

        accounts = list_connected_accounts()
        
        async def regenerate_topic(e):
            self.log(f"🧠 Pedindo nova ideia RECENTE (2024-2026) para {nicho_dropdown.value}...", NEON_BLUE)
            from ideator_new import gerar_tema_factual
            novo = await gerar_tema_factual(nicho_especifico=nicho_dropdown.value)
            if novo:
                title_field.value = novo["title"]
                keywords_field.value = ", ".join(novo["keywords"])
                # Auto-atribui o perfil se for o padrão do nicho
                from styles import obter_estilo
                estilo = obter_estilo(nicho_dropdown.value)
                if estilo.get("perfil_padrao") in accounts:
                    acc_dropdown.value = estilo.get("perfil_padrao")
                
                # Feedback visual imediato
                title_field.update()
                keywords_field.update()
                acc_dropdown.update()
                
                self.log(f"✨ Novo tema sugerido: {novo['title']}", NEON_GREEN)

        def save_schedule(e):
            # Recarrega para garantir que não estamos sobrescrevendo mudanças paralelas
            with open(filepath, "r", encoding="utf-8") as f:
                latest_data = json.load(f)
            
            latest_slot = latest_data["slots"][slot_index]
            
            # Detecta se o tema mudou para resetar o progresso
            if latest_slot["tema"] != title_field.value:
                latest_slot["status"] = "planejado"
                latest_slot["arquivo_vault"] = ""
            
            latest_slot["tema"] = title_field.value
            latest_slot["keywords"] = [k.strip() for k in keywords_field.value.split(",") if k.strip()]
            latest_slot["perfil"] = acc_dropdown.value
            latest_slot["horario"] = time_field.value
            latest_slot["nicho"] = nicho_dropdown.value
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(latest_data, f, indent=4, ensure_ascii=False)
            
            self.log(f"✅ Agenda salva: {latest_slot['tema']}", NEON_GREEN)
            self.close_dialog(None)
            # Força reconstrução do dashboard
            self.refresh_current_view()

        title_field = ft.TextField(label="TEMA DO VÍDEO", value=slot["tema"], border_color=NEON_BLUE, multiline=True)
        keywords_field = ft.TextField(label="KEYWORDS", value=", ".join(slot["keywords"]), border_color=NEON_BLUE)
        
        nicho_dropdown = ft.Dropdown(
            label="NICHO",
            options=[ft.dropdown.Option(n) for n in NICHOS],
            value=slot.get("nicho", "Games"),
            border_color=NEON_BLUE
        )

        acc_dropdown = ft.Dropdown(
            label="SELECT CHANNEL",
            options=[ft.dropdown.Option(a) for a in accounts],
            value=slot.get("perfil") if slot.get("perfil") in accounts else None,
            border_color=NEON_BLUE
        )
        time_field = ft.TextField(label="POST TIME (HH:MM)", value=slot.get("horario", "12:00"), border_color=NEON_BLUE)

        dlg = ft.AlertDialog(
            title=ft.Text("REVISÃO DE TEMA E AGENDAMENTO", size=16, weight="bold"),
            content=ft.Column([
                nicho_dropdown,
                title_field,
                keywords_field,
                ft.Row([
                    ft.Button("REGENERAR TEMA", icon=ft.Icons.AUTORENEW, 
                              on_click=lambda e: self.page.run_task(regenerate_topic, e)),
                ], alignment=ft.MainAxisAlignment.END),
                ft.Divider(height=10, color="#222222"),
                ft.Row([acc_dropdown, time_field], spacing=10),
            ], height=480, width=500, tight=True, spacing=10, scroll=ft.ScrollMode.ALWAYS),
            actions=[
                ft.TextButton("CANCEL", on_click=self.close_dialog),
                ft.Button("SAVE CHANGES", bgcolor=NEON_BLUE, color="black", on_click=save_schedule),
            ],
            bgcolor="#111111",
            shape=ft.RoundedRectangleBorder(radius=15)
        )
        self.page.overlay.append(dlg)
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def show_markdown_dialog(self, filepath):
        meta, body = read_markdown_file(filepath)
        status = meta.get("status")
        nicho = meta.get("nicho", "default")
        
        from styles import obter_estilo
        estilo = obter_estilo(nicho)
        target_handle = estilo.get("handle", "@FatosCuriosos")
        
        legenda = f"Confira essa curiosidade sobre {meta.get('tema')}! #fatos #curiosidades {target_handle}"
        if "visual_search_terms" in meta:
            tags = " ".join([f"#{t.replace(' ', '')}" for t in meta.get("keywords", [])[:3]])
            legenda = f"{meta.get('tema')} 🎬 {tags} {target_handle}"

        actions = [ft.TextButton("CLOSE", on_click=self.close_dialog)]
        
        if status == "research_completed":
            actions.insert(0, ft.Button("PREPARE SCRIPT", icon=ft.Icons.DESCRIPTION, bgcolor=NEON_PURPLE, color="black",
                                                on_click=lambda _: self.page.run_task(self.run_task, preparar_roteiro(filepath), "Script Prep")))
        elif status == "script_ready":
            actions.insert(0, ft.Button("RENDER VIDEO", icon=ft.Icons.BOLT, bgcolor=NEON_GREEN, color="black",
                                                on_click=lambda _: self.page.run_task(self.run_task, renderizar_video(filepath), "Render")))

        content = ft.Column([
            ft.Text(meta.get('tema', 'Project Details').upper(), size=20, weight="bold", color=NEON_BLUE),
            ft.Row([
                ft.Icon(ft.Icons.SHARE, size=16, color="grey"),
                ft.Text(f"TARGET CHANNEL: {target_handle}", size=13, color=NEON_GREEN, weight="bold"),
            ]),
            ft.Container(
                content=ft.Column([
                    ft.Text("PROPOSED TIKTOK CAPTION:", size=11, weight="bold", color="grey"),
                    ft.Text(legenda, size=12, italic=True),
                ], spacing=5),
                padding=15,
                bgcolor="#050505",
                border_radius=10,
                border=ft.Border.all(1, "#1A1A1A")
            ),
            ft.Divider(height=20, color="#222222"),
            ft.Markdown(
                body,
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            )
        ], scroll=ft.ScrollMode.ALWAYS, spacing=15, expand=True)

        dlg = ft.AlertDialog(
            content=ft.Container(content, width=900, height=750, padding=10),
            actions=actions,
            bgcolor="#111111",
            shape=ft.RoundedRectangleBorder(radius=15)
        )
        
        self.page.overlay.append(dlg)
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def confirm_delete_account(self, perfil):
        def delete_confirmed(e):
            if remover_conta(perfil):
                self.log(f"🗑️ Account removed: {perfil}", "yellow")
                self.close_dialog(None)
                self.refresh_accounts()
            else:
                self.log(f"❌ Failed to remove {perfil}", "red")
                self.close_dialog(None)

        dlg = ft.AlertDialog(
            title=ft.Text("DELETE ACCOUNT"),
            content=ft.Text(f"Permanently remove '{perfil}' session data?"),
            actions=[
                ft.TextButton("CANCEL", on_click=self.close_dialog),
                ft.Button("DELETE", bgcolor="red", color="white", on_click=delete_confirmed),
            ],
            bgcolor="#111111"
        )
        self.page.overlay.append(dlg)
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def close_dialog(self, e):
        if self.page.dialog:
            self.page.dialog.open = False
        self.page.update()

    def add_account_dialog(self, e):
        async def start_login(e):
            name = name_field.value
            if name:
                self.page.dialog.open = False
                self.page.update()
                await self.run_task(gerenciar_login(name), f"Login {name}")
                self.refresh_accounts()

        name_field = ft.TextField(label="PROFILE NAME", autofocus=True, border_color=NEON_BLUE)
        dlg = ft.AlertDialog(
            title=ft.Text("LINK NEW TIKTOK"),
            content=ft.Column([
                ft.Text("Enter a unique name for this profile.", size=12, color="grey"),
                name_field
            ], height=120, tight=True),
            actions=[
                ft.TextButton("CANCEL", on_click=self.close_dialog),
                ft.Button("OPEN TIKTOK", bgcolor=NEON_BLUE, color="black", on_click=lambda e: self.page.run_task(start_login, e)),
            ],
            bgcolor="#111111"
        )
        self.page.overlay.append(dlg)
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

def main(page: ft.Page):
    app = AutoVideoApp(page)
    
    old_print = print
    def custom_print(*args, **kwargs):
        msg = " ".join(map(str, args))
        old_print(*args, **kwargs)
        color = "white"
        if "✅" in msg: color = NEON_GREEN
        if "❌" in msg or "💥" in msg: color = "red"
        if "⚠️" in msg: color = "yellow"
        if "🚀" in msg or "🧠" in msg: color = NEON_BLUE
        if "✨" in msg: color = NEON_PURPLE
        app.log(msg, color)

    import builtins
    builtins.print = custom_print

if __name__ == "__main__":
    ft.run(main)
