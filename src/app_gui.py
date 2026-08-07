import flet as ft
import asyncio
import os
import json
from agenda_manager import criar_agenda_semanal, AGENDA_PATH, obter_proxima_semana
from batch_researcher import run_batch
from script_preparer import run_preparer
from vault_renderer import run_renderer

class AutoVideoApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "AutoVideo Turbo Dashboard"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.window_width = 1000
        self.page.window_height = 800
        
        self.log_area = ft.ListView(expand=True, spacing=10, padding=20, auto_scroll=True)
        self.status_text = ft.Text("Pronto para produzir", size=20, color="blue")
        
        self.init_ui()

    def log(self, message, color="white"):
        self.log_area.controls.append(ft.Text(message, color=color))
        self.page.update()

    def init_ui(self):
        # Header
        header = ft.Row([
            ft.Text("🚀 AutoVideo Factory", size=32, weight="bold", color="blue"),
            ft.IconButton(ft.icons.REFRESH, on_click=self.refresh_agenda)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        # Buttons
        self.btn_research = ft.ElevatedButton("Pesquisar Batch", icon=ft.icons.SEARCH, on_click=self.start_research)
        self.btn_scripts = ft.ElevatedButton("Preparar Roteiros", icon=ft.icons.DESCRIPTION, on_click=self.start_scripts)
        self.btn_render = ft.ElevatedButton("Renderizar Vídeos", icon=ft.icons.VIDEO_SETTINGS, on_click=self.start_render)
        
        btn_row = ft.Row([self.btn_research, self.btn_scripts, self.btn_render], spacing=20)

        # Agenda View
        self.agenda_list = ft.Column(expand=True, scroll=ft.ScrollMode.ALWAYS)
        
        # Main Layout
        self.page.add(
            header,
            ft.Divider(),
            ft.Text("Agenda da Próxima Semana", size=20, weight="bold"),
            ft.Container(content=self.agenda_list, height=300, border=ft.border.all(1, "grey"), padding=10),
            ft.Divider(),
            btn_row,
            ft.Text("Console de Saída", size=16, weight="bold"),
            ft.Container(content=self.log_area, expand=True, bgcolor="#1a1a1a", border_radius=10)
        )
        
        self.refresh_agenda(None)

    def refresh_agenda(self, e):
        self.agenda_list.controls.clear()
        id_semana, _ = obter_proxima_semana()
        filepath = os.path.join(AGENDA_PATH, f"{id_semana}.json")
        
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                for slot in data["slots"]:
                    color = "green" if slot["status"] == "pesquisado" else "yellow"
                    self.agenda_list.controls.append(
                        ft.ListTile(
                            leading=ft.Icon(ft.icons.CALENDAR_TODAY),
                            title=ft.Text(slot["tema"]),
                            subtitle=ft.Text(f"{slot['data']} | {slot['periodo']}"),
                            trailing=ft.Text(slot["status"], color=color)
                        )
                    )
        else:
            self.agenda_list.controls.append(ft.Text("Nenhuma agenda gerada. Clique em Gerar Agenda."))
            self.page.add(ft.ElevatedButton("Gerar Agenda Semanal", on_click=self.generate_agenda))
        
        self.page.update()

    async def generate_agenda(self, e):
        self.log("Gerando temas para a semana...")
        await criar_agenda_semanal()
        self.refresh_agenda(None)

    async def start_research(self, e):
        self.log("Iniciando Pesquisa em Lote...", "blue")
        await run_batch(3)
        self.log("✅ Pesquisa finalizada!", "green")
        self.refresh_agenda(None)

    async def start_scripts(self, e):
        self.log("Iniciando Preparação de Roteiros...", "blue")
        await run_preparer()
        self.log("✅ Roteiros finalizados!", "green")

    async def start_render(self, e):
        self.log("Iniciando Renderização Turbo...", "blue")
        await run_renderer()
        self.log("✅ Renderização finalizada! Verifique a pasta outputs.", "green")

def main(page: ft.Page):
    AutoVideoApp(page)

if __name__ == "__main__":
    ft.app(target=main)
