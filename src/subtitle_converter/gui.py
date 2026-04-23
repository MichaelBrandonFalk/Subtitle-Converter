from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .core import convert_file


class SubtitleConverterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Subtitle Converter")
        self.root.geometry("860x620")
        self.root.minsize(760, 560)

        self.files: list[Path] = []
        self.to_srt = tk.BooleanVar(value=True)
        self.to_vtt = tk.BooleanVar(value=True)
        self.to_ttml = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Add subtitle files to begin.")

        self._build_styles()
        self._build_layout()

    def _build_styles(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        self.root.configure(bg="#f3ede2")
        style.configure("App.TFrame", background="#f3ede2")
        style.configure("Card.TFrame", background="#fffaf1")
        style.configure("App.TLabel", background="#f3ede2", foreground="#1f1b18", font=("Helvetica", 11))
        style.configure("Title.TLabel", background="#f3ede2", foreground="#111111", font=("Helvetica", 26, "bold"))
        style.configure("Muted.TLabel", background="#f3ede2", foreground="#6a5c4c", font=("Helvetica", 11))
        style.configure("CardTitle.TLabel", background="#fffaf1", foreground="#1f1b18", font=("Helvetica", 12, "bold"))
        style.configure("Accent.TButton", font=("Helvetica", 11, "bold"))

    def _build_layout(self) -> None:
        shell = ttk.Frame(self.root, padding=24, style="App.TFrame")
        shell.pack(fill="both", expand=True)

        header = ttk.Frame(shell, style="App.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Subtitle Converter", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Convert SRT, VTT, and TTML without the macOS-only wrapper.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(6, 20))

        controls = ttk.Frame(shell, style="App.TFrame")
        controls.pack(fill="x")

        file_card = ttk.Frame(controls, padding=16, style="Card.TFrame")
        file_card.pack(side="left", fill="both", expand=True)

        ttk.Label(file_card, text="Files", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(file_card, text="Add one or more .srt or .vtt files.", style="Muted.TLabel").pack(anchor="w", pady=(4, 12))

        button_row = ttk.Frame(file_card, style="Card.TFrame")
        button_row.pack(fill="x", pady=(0, 12))
        ttk.Button(button_row, text="Add Files", command=self.add_files, style="Accent.TButton").pack(side="left")
        ttk.Button(button_row, text="Remove Selected", command=self.remove_selected).pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="Clear", command=self.clear_files).pack(side="left", padx=(8, 0))

        self.file_list = tk.Listbox(
            file_card,
            height=16,
            bg="#fffdf8",
            fg="#1f1b18",
            borderwidth=0,
            selectbackground="#d04b2f",
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground="#ddcfbb",
        )
        self.file_list.pack(fill="both", expand=True)

        option_card = ttk.Frame(controls, padding=16, style="Card.TFrame")
        option_card.pack(side="left", fill="y", padx=(16, 0))
        ttk.Label(option_card, text="Outputs", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(option_card, text="Choose what to generate.", style="Muted.TLabel").pack(anchor="w", pady=(4, 12))
        ttk.Checkbutton(option_card, text="SRT", variable=self.to_srt).pack(anchor="w", pady=4)
        ttk.Checkbutton(option_card, text="WebVTT", variable=self.to_vtt).pack(anchor="w", pady=4)
        ttk.Checkbutton(option_card, text="TTML", variable=self.to_ttml).pack(anchor="w", pady=4)
        ttk.Button(option_card, text="Convert", command=self.convert, style="Accent.TButton").pack(fill="x", pady=(18, 0))

        status_card = ttk.Frame(shell, padding=16, style="Card.TFrame")
        status_card.pack(fill="both", expand=True, pady=(16, 0))
        ttk.Label(status_card, text="Status", style="CardTitle.TLabel").pack(anchor="w")

        self.log = tk.Text(
            status_card,
            height=12,
            wrap="word",
            bg="#fffdf8",
            fg="#201714",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#ddcfbb",
        )
        self.log.pack(fill="both", expand=True, pady=(12, 10))
        self.log.insert("1.0", "Ready.\n")
        self.log.configure(state="disabled")

        ttk.Label(shell, textvariable=self.status, style="Muted.TLabel").pack(anchor="w", pady=(12, 0))

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select subtitle files",
            filetypes=[("Subtitle files", "*.srt *.vtt"), ("All files", "*.*")],
        )
        for raw in paths:
            path = Path(raw)
            if path not in self.files:
                self.files.append(path)
                self.file_list.insert("end", str(path))
        self.status.set(f"{len(self.files)} file(s) queued.")

    def remove_selected(self) -> None:
        selections = list(self.file_list.curselection())
        for idx in reversed(selections):
            self.file_list.delete(idx)
            self.files.pop(idx)
        self.status.set(f"{len(self.files)} file(s) queued.")

    def clear_files(self) -> None:
        self.files.clear()
        self.file_list.delete(0, "end")
        self.status.set("File queue cleared.")

    def convert(self) -> None:
        if not self.files:
            messagebox.showwarning("No files", "Add at least one .srt or .vtt file.")
            return
        if not any((self.to_srt.get(), self.to_vtt.get(), self.to_ttml.get())):
            messagebox.showwarning("No outputs selected", "Select at least one output format.")
            return

        success = 0
        failures = 0
        self.append_log("Starting conversion batch...")

        for path in self.files:
            try:
                outputs = convert_file(path, self.to_srt.get(), self.to_vtt.get(), self.to_ttml.get())
                names = ", ".join(output.name for output in outputs)
                self.append_log(f"Converted {path.name} -> {names}")
                success += 1
            except Exception as exc:
                self.append_log(f"Failed {path.name}: {exc}")
                failures += 1

        self.status.set(f"Finished. Success: {success}. Failed: {failures}.")
        if failures:
            messagebox.showwarning("Conversion finished", f"Converted {success} file(s). {failures} failed.")
        else:
            messagebox.showinfo("Conversion finished", f"Converted {success} file(s).")


def launch_gui() -> None:
    root = tk.Tk()
    SubtitleConverterApp(root)
    root.mainloop()

