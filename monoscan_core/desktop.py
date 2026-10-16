"""MonoScan11 N7 offline desktop UI — standard-library Tkinter.

No fake point clouds or progress percentages. Entire UI consumes only real
local project records, native N3–N6 outputs and strict source diagnostics.
Tk Widgets are touched only on the main thread; CPU jobs run in workers.
"""
from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import traceback

from .preview import PreviewError, geometry_for_run, project_preview
from .workflow import (
    PipelineCancelled, PipelineError, diagnostics, discover_runs,
    launch_single_stage, run_pipeline,
)
from .workspace import ProjectCatalog, WorkspaceError, default_workspace


BG = "#0b1420"
PANEL = "#142333"
INK = "#e6f1f9"
MUTED = "#8faabb"
ACCENT = "#40b8d6"


class MonoScanDesktop(tk.Tk):
    """Source-driven view: projects → stages → runs → real point cloud/mesh."""

    def __init__(self, root=None):
        super().__init__()
        self.title("MonoScan11 · Windows 3B İstasyonu — N7")
        self.geometry("1440x870")
        self.minsize(1080, 690)
        self.configure(bg=BG)
        self.catalog = ProjectCatalog(root or default_workspace())
        self.events = queue.Queue()
        self.busy = False
        self.cancel_event = threading.Event()
        self.project_ids = []
        self.runs = []
        self.preview_model = None
        self.yaw = 0.65
        self.pitch = -0.4
        self.zoom = 0.95
        self.mouse = None
        self.selection = None
        self.mode = tk.StringVar(value="arkit-guided")
        self.focal = tk.StringVar(value="")
        self.want_ba = tk.BooleanVar(value=True)
        self.want_dense = tk.BooleanVar(value=False)
        self.synthetic = tk.BooleanVar(value=False)
        self.depth_near = tk.StringVar(value="1.0")
        self.depth_far = tk.StringVar(value="5.0")
        self.prior = tk.StringVar(value="2.0")
        self.preview_choice = tk.StringVar(value="Seyrek / BA")
        self.stage_state = tk.StringVar(value="Henüz işlem başlatılmadı")
        self._configure_theme()
        self._layout()
        self._refresh_projects()
        self.after(100, self._poll_events)

    def _configure_theme(self):
        theme = ttk.Style(self)
        try:
            theme.theme_use("clam")
        except tk.TclError:
            pass
        theme.configure(".", background=PANEL, foreground=INK, fieldbackground=PANEL,
                        font=("Segoe UI", 10))
        theme.configure("TFrame", background=PANEL)
        theme.configure("TLabel", background=PANEL, foreground=INK)
        theme.configure("TCheckbutton", background=PANEL, foreground=INK)
        theme.configure("TButton", padding=7, background="#223b50", foreground=INK)
        theme.map("TButton", background=[("active", "#2f6379")])
        theme.configure("TEntry", fieldbackground="#eef5f8", foreground="#101c2c")
        theme.configure("TCombobox", fieldbackground="#eef5f8", foreground="#101c2c")
        theme.configure("TNotebook", background=PANEL)
        theme.configure("TNotebook.Tab", background="#223749", foreground=INK,
                        padding=(14, 8))
        theme.map("TNotebook.Tab", background=[("selected", "#315d72")])
        theme.configure("Horizontal.TProgressbar", troughcolor=PANEL, background=ACCENT)

    def _layout(self):
        header = tk.Frame(self, bg=BG, height=92)
        header.pack(fill="x")
        tk.Label(header, text="MONOSCAN11", bg=BG, fg=INK,
                 font=("Segoe UI Semibold", 23)).pack(anchor="w", padx=24, pady=(12, 0))
        tk.Label(header,
                 text="N7 · Çevrimdışı 3B İş İstasyonu  |  Sentetik entegrasyon  |  Gerçek cihaz kabulü: N9",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=24)
        content = tk.PanedWindow(self, orient="horizontal", bg=BG, sashwidth=6, borderwidth=0)
        content.pack(fill="both", expand=True, padx=12, pady=(4, 10))
        left = tk.Frame(content, bg=PANEL, width=260)
        center = tk.Frame(content, bg=PANEL, width=790)
        right = tk.Frame(content, bg=PANEL, width=330)
        content.add(left, minsize=225, stretch="never")
        content.add(center, minsize=415, stretch="always")
        content.add(right, minsize=290, stretch="never")
        self._project_panel(left)
        self._viewer_panel(center)
        self._processing_panel(right)

    def _heading(self, parent, text):
        tk.Label(parent, text=text, bg=PANEL, fg=ACCENT,
                 font=("Segoe UI Semibold", 13)).pack(anchor="w", padx=12, pady=(13, 7))

    def _project_panel(self, parent):
        self._heading(parent, "Projeler")
        ttk.Button(parent, text="iPhone ZIP içe aktar", command=self._import_zip).pack(
            fill="x", padx=12, pady=(0, 6))
        ttk.Button(parent, text="Oturum klasörü bağla", command=self._link_folder).pack(
            fill="x", padx=12, pady=(0, 8))
        self.projects_list = tk.Listbox(parent, bg="#172c3d", fg=INK,
                                       selectbackground="#356982",
                                       activestyle="none", borderwidth=0,
                                       highlightthickness=0, font=("Segoe UI", 10))
        self.projects_list.pack(fill="both", expand=True, padx=12, pady=6)
        self.projects_list.bind("<<ListboxSelect>>", self._project_changed)
        ttk.Button(parent, text="Katalogdan çıkar (dosya silmez)",
                   command=self._remove_project).pack(fill="x", padx=12, pady=(4, 12))
        note = ("Kaydedilmiş ZIP veya yerel oturum seçin.\n"
                "Resimler yerel kalır; buluta gönderilmez.\n"
                "Dışarıdan getirilen veriye otomatik\n"
                "ölçüm doğruluğu atanmıyor.")
        tk.Label(parent, text=note, bg=PANEL, fg=MUTED,
                 justify="left", wraplength=235).pack(anchor="w", padx=12, pady=(0, 12))

    def _viewer_panel(self, parent):
        toolbar = tk.Frame(parent, bg=PANEL)
        toolbar.pack(fill="x", padx=10, pady=(10, 3))
        tk.Label(toolbar, text="3B Önizleme", bg=PANEL, fg=INK,
                 font=("Segoe UI Semibold", 14)).pack(side="left")
        ttk.Button(toolbar, text="Yenile", command=self._refresh_runs).pack(side="right")
        self.view_types = ttk.Combobox(toolbar, textvariable=self.preview_choice,
                                       state="readonly", width=14,
                                       values=("Seyrek / BA", "Yoğun noktalar", "Mesh yüzeyi"))
        self.view_types.pack(side="right", padx=(5, 10))
        self.view_types.bind("<<ComboboxSelected>>", lambda event: self._set_preview())
        self.runs_combo = ttk.Combobox(parent, state="readonly", width=48)
        self.runs_combo.pack(fill="x", padx=10, pady=(3, 5))
        self.runs_combo.bind("<<ComboboxSelected>>", self._selected_run)
        self.canvas = tk.Canvas(parent, bg="#07131d", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=5)
        self.canvas.bind("<Configure>", lambda e: self._render_preview())
        self.canvas.bind("<ButtonPress-1>", self._begin_rotate)
        self.canvas.bind("<B1-Motion>", self._rotate)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda e: self._adjust_zoom(1.10))
        self.canvas.bind("<Button-5>", lambda e: self._adjust_zoom(1/1.10))
        tk.Label(parent, text="Sürükle: döndür  ·  Tekerlek: yakınlaş  ·  Sahte geometri yok",
                 bg=PANEL, fg=MUTED).pack(anchor="w", padx=12, pady=(2, 5))
        tabs = ttk.Notebook(parent)
        tabs.pack(fill="both", padx=10, pady=(2, 10), expand=False)
        data_page = ttk.Frame(tabs)
        log_page = ttk.Frame(tabs)
        tabs.add(data_page, text="Kanıt ve belirsizlik")
        tabs.add(log_page, text="İşlem günlüğü")
        self.inspector = tk.Text(data_page, bg="#102232", fg=INK, insertbackground=INK,
                                 font=("Consolas", 9), height=11, wrap="word",
                                 borderwidth=0, padx=10, pady=8)
        self.inspector.pack(fill="both", expand=True)
        self.log = tk.Text(log_page, bg="#102232", fg=INK, font=("Consolas", 9),
                           height=11, wrap="word", borderwidth=0, padx=10, pady=8)
        self.log.pack(fill="both", expand=True)
        self._inspector_text("Henüz kayıtlı bir model yok.\n"
                             "Çıktı üretildiğinde kaynak ve belirsizlik bilgileri burada gösterilir.")

    def _processing_panel(self, parent):
        self._heading(parent, "İşlem Hattı  N3 → N6")
        body = tk.Frame(parent, bg=PANEL)
        body.pack(fill="x", padx=12)
        ttk.Label(body, text="Rekonstrüksiyon modu").pack(anchor="w", pady=(6, 2))
        modes = ttk.Combobox(body, textvariable=self.mode, state="readonly",
                             values=("photo-only", "arkit-guided"))
        modes.pack(fill="x", pady=(0, 5))
        ttk.Label(body, text="Odak (px; yalnız photo-only, K yoksa)").pack(anchor="w")
        ttk.Entry(body, textvariable=self.focal).pack(fill="x", pady=(2, 7))
        ttk.Checkbutton(body, text="N5 · Seyrek Bundle Adjustment",
                        variable=self.want_ba, command=self._toggle_dense).pack(anchor="w", pady=3)
        ttk.Checkbutton(body, text="N6 · Yoğun MVS + açık mesh",
                        variable=self.want_dense, command=self._toggle_dense).pack(anchor="w", pady=3)
        ttk.Label(body, text="N6 derinlik aralığı / poz birimi").pack(anchor="w", pady=(13, 4))
        span = ttk.Frame(body)
        span.pack(fill="x")
        ttk.Entry(span, textvariable=self.depth_near, width=9).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Entry(span, textvariable=self.depth_far, width=9).pack(side="left", expand=True, fill="x", padx=(4, 0))
        ttk.Label(body, text="ARKit heuristik prior ağırlığı (kovaryans değil)").pack(anchor="w", pady=(12, 3))
        ttk.Entry(body, textvariable=self.prior).pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(body, text="Seçilen oturum sentetik test verisidir",
                        variable=self.synthetic).pack(anchor="w", pady=(7, 12))
        self.run_button = ttk.Button(body, text="Doğrula + Rekonstrüksiyon",
                                     command=self._start_pipeline)
        self.run_button.pack(fill="x", pady=3)
        self.refine_button = ttk.Button(body, text="Seçili modelde N5",
                                        command=lambda: self._run_existing("refine"))
        self.refine_button.pack(fill="x", pady=3)
        self.dense_button = ttk.Button(body, text="Seçili modelde N6",
                                       command=lambda: self._run_existing("dense"))
        self.dense_button.pack(fill="x", pady=3)
        self.stop_button = ttk.Button(body, text="İşlemi iptal et", command=self._cancel)
        self.stop_button.pack(fill="x", pady=(3, 10))
        self.busy_bar = ttk.Progressbar(body, mode="indeterminate")
        self.busy_bar.pack(fill="x", pady=(0, 10))
        ttk.Label(body, textvariable=self.stage_state, wraplength=280,
                  foreground="#abdae2").pack(anchor="w", pady=(0, 12))
        separator = ttk.Separator(parent, orient="horizontal")
        separator.pack(fill="x", padx=10, pady=8)
        self._heading(parent, "Aşama durumları")
        self.stage_list = tk.Listbox(parent, bg="#172c3d", fg=INK,
                                     borderwidth=0, highlightthickness=0,
                                     font=("Consolas", 10), height=8)
        self.stage_list.pack(fill="x", padx=12)
        self._reset_stages()
        ttk.Label(parent, text="Ölçüm hassasiyeti: bilinmiyor.\n"
                  "N3–N6 sentetik kanıt ≠ gerçek cihaz kabulü.\n"
                  "N9: gerçek fotoğraf ve bağımsız ölçüm.",
                  foreground=MUTED, justify="left", wraplength=275).pack(
                      anchor="w", padx=12, pady=(18, 10))

    def _reset_stages(self):
        self.stage_list.delete(0, "end")
        for tag in ("Doğrulama", "N3 / N4 · Seyrek", "N5 · BA", "N6 · MVS"):
            self.stage_list.insert("end", "— " + tag)

    def _mark_stage(self, stage, mark):
        indices = {"validate": 0, "reconstruct": 1, "refine": 2, "dense": 3}
        if stage not in indices:
            return
        n = indices[stage]
        names = ("Doğrulama", "N3 / N4 · Seyrek", "N5 · BA", "N6 · MVS")
        self.stage_list.delete(n)
        self.stage_list.insert(n, mark + "  " + names[n])

    def _current(self):
        selected = self.projects_list.curselection()
        if not selected or selected[0] >= len(self.project_ids):
            return None
        return self.project_ids[selected[0]]

    def _session(self):
        pid = self._current()
        if pid is None:
            raise WorkspaceError("Önce bir proje seçin")
        return self.catalog.session_path(pid)

    def _refresh_projects(self, selected_id=None):
        all_projects = self.catalog.projects()
        self.project_ids = [p["id"] for p in all_projects]
        self.projects_list.delete(0, "end")
        for p in all_projects:
            kind = "ZIP" if p["origin"] == "zip" else "Klasör"
            self.projects_list.insert("end", f"{p['name']}  [{kind}]")
        if selected_id in self.project_ids:
            n = self.project_ids.index(selected_id)
            self.projects_list.selection_set(n)
            self.projects_list.activate(n)
            self._refresh_runs()
        elif self.project_ids:
            self.projects_list.selection_set(0)
            self._refresh_runs()
        else:
            self.runs = []
            self.runs_combo["values"] = ()
            self.preview_model = None
            self._render_preview()

    def _project_changed(self, _event=None):
        self.preview_model = None
        self._refresh_runs()

    def _refresh_runs(self):
        try:
            session = self._session()
            self.runs = discover_runs(session)
        except (WorkspaceError, PipelineError, OSError):
            self.runs = []
        self.runs_combo["values"] = [r["label"] for r in self.runs]
        if self.runs:
            self.runs_combo.current(0)
            self._selected_run()
        else:
            self.runs_combo.set("")
            self.preview_model = None
            self._inspector_text("Bu projede N3–N6 modelleri henüz yok.\n"
                                 "Kaynak dosya olmadan sahte 3B önizleme üretilmez.")
            self._render_preview()

    def _selected_item(self):
        n = self.runs_combo.current()
        return self.runs[n] if 0 <= n < len(self.runs) else None

    def _selected_run(self, _event=None):
        item = self._selected_item()
        if item is None:
            return
        self.preview_choice.set("Yoğun noktalar" if item["kind"] == "dense"
                                else "Seyrek / BA")
        self._set_preview()

    def _set_preview(self):
        item = self._selected_item()
        if item is None:
            return
        try:
            label = self.preview_choice.get()
            kind = {"Seyrek / BA": "sparse" if item["kind"] == "sparse" else "refined",
                    "Yoğun noktalar": "dense", "Mesh yüzeyi": "mesh"}[label]
            self.preview_model = geometry_for_run(item, kind)
        except (PreviewError, ValueError, OSError) as exc:
            self.preview_model = None
            self._write_log("Önizleme: " + str(exc))
        try:
            rows, warnings = diagnostics(item["summary"])
            text = "\n".join(f"{label}: {value}" for label, value in rows)
            text += "\n\nUyarılar:\n" + ("\n".join("• " + w for w in warnings)
                                          if warnings else "Kaynakta ek uyarı yok")
            text += "\n\nKaynak: " + item["path"]
            self._inspector_text(text)
        except PipelineError as exc:
            self._inspector_text("Güvenilmeyen rapor: " + str(exc))
        self._render_preview()

    def _render_preview(self):
        if not hasattr(self, "canvas"):
            return
        self.canvas.delete("all")
        model = self.preview_model
        w = max(self.canvas.winfo_width(), 300)
        h = max(self.canvas.winfo_height(), 220)
        if model is None:
            self.canvas.create_text(w/2, h/2, text="Henüz geçerli 3B geometri yok",
                                    fill=MUTED, font=("Segoe UI", 13))
            return
        try:
            points = project_preview(model.points, w, h, yaw=self.yaw,
                                     pitch=self.pitch, zoom=self.zoom)
            if model.kind == "mesh":
                faces = sorted(model.faces,
                               key=lambda tri: sum(points[i][2] for i in tri) / 3)
                for tri in faces:
                    xy = [v for i in tri for v in points[i][:2]]
                    self.canvas.create_polygon(*xy, fill="#24617c",
                                               outline="#3c91ae", width=0.5)
            else:
                for i in sorted(range(len(points)), key=lambda j: points[j][2]):
                    x, y, _ = points[i]
                    self.canvas.create_oval(x-1.2, y-1.2, x+1.2, y+1.2,
                                            fill=model.colors[i], outline="")
            self.canvas.create_text(12, 15, anchor="w", fill=MUTED,
                                    text=f"{len(model.points)} gerçek kayıt noktası · "
                                         f"{len(model.faces)} çizilen üçgen")
        except PreviewError as exc:
            self.canvas.create_text(w/2, h/2, text=str(exc), fill="#ff9c9c")

    def _begin_rotate(self, event):
        self.mouse = (event.x, event.y)

    def _rotate(self, event):
        if self.mouse:
            dx, dy = event.x-self.mouse[0], event.y-self.mouse[1]
            self.yaw += dx * 0.01
            self.pitch = max(-1.45, min(1.45, self.pitch + dy * 0.01))
            self.mouse = (event.x, event.y)
            self._render_preview()

    def _adjust_zoom(self, factor):
        self.zoom = max(0.2, min(3.0, self.zoom * factor))
        self._render_preview()

    def _wheel(self, event):
        self._adjust_zoom(1.12 if event.delta > 0 else 1/1.12)

    def _inspector_text(self, content):
        if not hasattr(self, "inspector"):
            return
        self.inspector.configure(state="normal")
        self.inspector.delete("1.0", "end")
        self.inspector.insert("end", content)
        self.inspector.configure(state="disabled")

    def _write_log(self, line):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{stamp}] {line}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _import_zip(self):
        if self.busy:
            return
        filename = filedialog.askopenfilename(title="iPhone ZIP oturumu",
                                              filetypes=[("ZIP paketleri", "*.zip")])
        if filename:
            self._start_task("ZIP içe aktarılıyor", lambda: (
                "imported", self.catalog.import_zip(filename)))

    def _link_folder(self):
        if self.busy:
            return
        path = filedialog.askdirectory(title="Oturum klasörü seçin")
        if path:
            self._start_task("Yerel oturum doğrulanıyor", lambda: (
                "imported", self.catalog.link_folder(path)))

    def _remove_project(self):
        if self.busy or not self._current():
            return
        if messagebox.askyesno("Katalog kaydı", "Yalnız kayıt çıkarılacak. Fotoğraf, ZIP ve modeller silinmeyecek."):
            self.catalog.remove(self._current())
            self._refresh_projects()

    def _toggle_dense(self):
        if self.want_dense.get():
            self.want_ba.set(True)

    def _check_synthetic(self):
        if not self.synthetic.get():
            raise PipelineError("N7 test sürümü yalnız sentetik oturumlarda çalışır. "
                                "Gerçek fotoğraflar N9'a ertelenmiştir.")

    def _start_pipeline(self):
        if self.busy:
            return
        try:
            self._check_synthetic()
            session = self._session()
            focal = float(self.focal.get().strip()) if self.focal.get().strip() else None
            near, far = float(self.depth_near.get()), float(self.depth_far.get())
            prior = float(self.prior.get())
            self._reset_stages()
            self._start_task("N3–N6 sentetik işlem hattı", lambda: (
                "pipeline", run_pipeline(
                    session, mode=self.mode.get(), focal_px=focal,
                    do_refine=self.want_ba.get(), do_dense=self.want_dense.get(),
                    depth_min=near, depth_max=far, prior_weight=prior,
                    cancel=self.cancel_event, emit=lambda ev: self.events.put(("stage", ev)))))
        except (WorkspaceError, PipelineError, ValueError, OSError) as exc:
            messagebox.showerror("İşlem başlatılamadı", str(exc))

    def _run_existing(self, stage):
        if self.busy:
            return
        try:
            self._check_synthetic()
            item = self._selected_item()
            if item is None or item["kind"] == "dense":
                raise PipelineError("N5/N6 için bir seyrek veya BA run seçin")
            session = self._session()
            near, far = float(self.depth_near.get()), float(self.depth_far.get())
            prior = float(self.prior.get())
            self._start_task("N5 optimizasyon" if stage == "refine" else "N6 yoğun model",
                             lambda: ("pipeline", launch_single_stage(
                                 stage, item["path"], session,
                                 cancel=self.cancel_event, prior_weight=prior,
                                 min_depth=near, max_depth=far,
                                 emit=lambda ev: self.events.put(("stage", ev)))))
        except (WorkspaceError, PipelineError, ValueError, OSError) as exc:
            messagebox.showerror("İşlem başlatılamadı", str(exc))

    def _start_task(self, title, worker):
        if self.busy:
            return
        self.busy = True
        self.cancel_event.clear()
        self.stage_state.set(title + " — işlem sürüyor")
        self.busy_bar.start(12)
        for button in (self.run_button, self.refine_button, self.dense_button):
            button.configure(state="disabled")
        self._write_log(title)
        def function():
            try:
                self.events.put(("completed_task", worker()))
            except Exception as exc:
                self.events.put(("task_error", str(exc)))
        threading.Thread(target=function, daemon=True).start()

    def _cancel(self):
        if self.busy:
            self.cancel_event.set()
            self._write_log("İptal isteği gönderildi. Çalışan alt işlem durdurulacak.")

    def _poll_events(self):
        while True:
            try:
                event_type, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if event_type == "stage":
                stage, action = payload.get("stage"), payload.get("event")
                if action == "start":
                    self._mark_stage(stage, "ÇALIŞIYOR")
                elif action == "complete":
                    self._mark_stage(stage, "KISMİ" if payload.get("status") == "PARTIAL"
                                     else "BİTTİ")
                elif action in ("failed", "cancelled"):
                    self._mark_stage(stage, "HATA")
                label = f"{stage}: {action}"
                if payload.get("status") == "PARTIAL":
                    label += " | KISMİ GEOMETRİ / eksik kayıt veya BA yakınsaması"
                elif action == "finished" and payload.get("partial_stages"):
                    label += " | KISMİ: " + ", ".join(payload["partial_stages"])
                if payload.get("message"):
                    label += " | " + payload["message"]
                self.stage_state.set(label)
                self._write_log(label)
            elif event_type == "completed_task":
                kind, result = payload
                self._finish_task()
                if kind == "imported":
                    self._refresh_projects(result["id"])
                    self._write_log("Oturum kataloğa eklendi: " + result["name"])
                else:
                    path = result.get("run") if isinstance(result, dict) else None
                    status = result.get("state", result.get("result", {}).get("state", "unknown"))
                    self._write_log("Aşamalar sona erdi [" + str(status) +
                                    "]. Çıktı: " + str(path))
                    self._refresh_runs()
            elif event_type == "task_error":
                self._finish_task()
                self.stage_state.set("İşlem tamamlanamadı")
                self._write_log("HATA: " + payload)
        self.after(100, self._poll_events)

    def _finish_task(self):
        self.busy = False
        self.busy_bar.stop()
        for button in (self.run_button, self.refine_button, self.dense_button):
            button.configure(state="normal")


def main():
    window = MonoScanDesktop()
    window.mainloop()


if __name__ == "__main__":
    main()
