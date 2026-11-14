"""Windows GUI for the independently installed audio8bit CLI."""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP = "Audio8BitGUI"
ENGINE = "0.0.3"
VOICES = {"Аккорды": "chords", "Только мелодия": "lead",
          "Чип-группа": "band", "NES / 8-bit": "nes"}
SOURCES = {"Автоматически": "auto", "Вокал": "vocals", "Инструменты": "instrumental"}
METHODS = {"Транскрипция": "transcribe", "Определение высоты": "pitch"}
FORMATS = ("wav", "mp3", "ogg", "flac")


def home() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / APP


def engine_python() -> Path:
    return home() / "engine" / "Scripts" / "python.exe"


def external_python() -> str | None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for cmd in (["py", "-3.11-64"], ["py", "-3.11"], ["python"]):
        try:
            probe = subprocess.run(cmd + ["-c",
                "import sys,struct;print(sys.executable if sys.version_info[:2]==(3,11) and struct.calcsize('P')==8 else '')"],
                text=True, capture_output=True, timeout=8, creationflags=flags)
            if probe.returncode == 0 and probe.stdout.strip():
                return probe.stdout.strip().splitlines()[-1]
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


def child_python_env(base: dict | None = None) -> dict:
    """Always use UTF-8 for child Python processes on any Windows code page.

    The GUI reads subprocess output as UTF-8. Without PYTHONIOENCODING,
    a Russian Windows locale may choose cp1251 for the child's stdout and
    crash on Japanese or other non-cp1251 characters in file names.
    """
    env = dict(os.environ if base is None else base)
    env["PYTHONIOENCODING"] = "utf-8:backslashreplace"
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def ffmpeg_path(selected: str = "") -> str | None:
    places = []
    if selected:
        p = Path(selected)
        places.append(p.parent if p.suffix.lower() == ".exe" else p)
    for executable in ("ffmpeg.exe", "ffmpeg"):
        found = shutil.which(executable)
        if found:
            places.append(Path(found).parent)
    for p in places:
        if (p / "ffmpeg.exe").is_file() and (p / "ffprobe.exe").is_file():
            return str(p)
    return None


def target_path(src: str, folder: str, fmt: str) -> Path:
    source = Path(src)
    if not source.is_file():
        raise ValueError("Выберите существующий аудиофайл")
    if fmt not in FORMATS:
        raise ValueError("Неподдерживаемый выходной формат")
    dest = (Path(folder) if folder else source.parent) / (source.stem + "_8bit." + fmt)
    if dest.resolve() == source.resolve():
        raise ValueError("Входной и выходной файлы совпадают")
    return dest


def convert_args(source: str, target: Path, opts: dict) -> list[str]:
    bits, rate, transpose, duty = (int(opts["bits"]), int(opts["rate"]),
                                   int(opts["transpose"]), float(opts["duty"]))
    if not 1 <= bits <= 8 or not 8000 <= rate <= 48000:
        raise ValueError("Битность 1–8; частота 8000–48000 Гц")
    if not -24 <= transpose <= 24 or not 0 < duty < 1:
        raise ValueError("Транспонирование −24…24; ширина импульса между 0 и 1")
    voice, method = opts["voices"], opts["method"]
    if voice in ("nes", "band") and method == "pitch":
        raise ValueError("NES и чип-группа требуют метод «Транскрипция»")
    command = [str(engine_python()), "-m", "audio8bit.cli", "-i", source, "-o", str(target),
               "-f", opts["format"], "-V", voice, "-s", opts["source"], "-m", method,
               "--bits", str(bits), "--rate", str(rate),
               "--transpose", str(transpose), "--duty", str(duty)]
    if voice in ("nes", "band"):
        for key in ("key-snap", "arrange", "echo", "dither"):
            command += ["--" + key, "on" if opts.get(key, True) else "off"]
    if not opts.get("cache", True):
        command.append("--no-cache")
    return command


class GUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Audio8Bit GUI — чиптюн из музыки")
        self.geometry("890x800")
        self.minsize(760, 700)
        self.configure(bg="#171c27")
        self.events = queue.Queue()
        self.process = None
        self.busy = False
        self.result = None
        self.basic_pitch_ok = False
        self.saved = self._load()
        self.fields = {}
        self._layout()
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _load(self):
        try:
            data = json.loads((home() / "settings.json").read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        try:
            home().mkdir(parents=True, exist_ok=True)
            (home() / "settings.json").write_text(
                json.dumps(self.options(), ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, ValueError, KeyError):
            pass

    def _layout(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        dark, panel, light, accent = "#171c27", "#212938", "#e6edf7", "#61c9a8"
        style.configure("TFrame", background=dark)
        style.configure("TLabel", background=dark, foreground=light, font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("TButton", padding=7, font=("Segoe UI", 9))
        style.configure("TCheckbutton", background=dark, foreground=light)
        style.map("TCheckbutton", background=[("active", dark)], foreground=[("active", light)])
        style.configure("TCombobox", fieldbackground=panel, foreground=light, padding=4)
        style.map("TCombobox", fieldbackground=[("readonly", panel)], foreground=[("readonly", light)])
        style.configure("TEntry", fieldbackground=panel, foreground=light)
        style.configure("TProgressbar", background=accent, troughcolor=panel)
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="audio8bit GUI", style="Header.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Превращение песен в музыку 8-битных приставок").pack(anchor="w", pady=(0, 16))
        self._path_input(frame, "Исходная аудиозапись", "input", self._choose_file)
        self._path_input(frame, "Папка для результата", "folder", self._choose_folder)
        options = ttk.Frame(frame)
        options.pack(fill="x", pady=(4, 8))
        left = ttk.Frame(options)
        right = ttk.Frame(options)
        left.pack(side="left", fill="x", expand=True, padx=(0, 14))
        right.pack(side="left", fill="x", expand=True)
        self._combo(left, "Режим звучания", "voices", VOICES, "nes")
        self._combo(left, "Источник мелодии", "source", SOURCES, "auto")
        self._combo(left, "Формат результата", "format", {f.upper(): f for f in FORMATS}, "wav")
        self._combo(right, "Определение нот", "method", METHODS, "transcribe")
        self._combo(right, "Битность", "bits", {str(i): str(i) for i in range(1,9)}, "8")
        self._combo(right, "Частота дискретизации", "rate",
                    {str(i): str(i) for i in (11025, 16000, 22050, 32000, 44100, 48000)}, "22050")
        advanced = ttk.Frame(frame)
        advanced.pack(fill="x", pady=6)
        ttk.Label(advanced, text="Транспонирование:").pack(side="left")
        self.fields["transpose"] = tk.StringVar(value=str(self.saved.get("transpose", 0)))
        tk.Spinbox(advanced, from_=-24, to=24, textvariable=self.fields["transpose"], width=6,
                   bg=panel, fg=light, insertbackground=light).pack(side="left", padx=(8, 30))
        ttk.Label(advanced, text="Ширина импульса:").pack(side="left")
        self._combo_inline(advanced, "duty",
                           {"0.125":"0.125", "0.25":"0.25", "0.5":"0.5", "0.75":"0.75"}, "0.25")
        toggles = ttk.Frame(frame)
        toggles.pack(fill="x", pady=(7, 15))
        for key, label in (("key-snap", "В тональности"), ("arrange", "Аранжировка"),
                           ("echo", "Эхо"), ("dither", "Дизеринг"), ("cache", "Кеширование")):
            var = tk.BooleanVar(value=bool(self.saved.get(key, True)))
            self.fields[key] = var
            ttk.Checkbutton(toggles, text=label, variable=var).pack(side="left", padx=(0, 13))
        tools = ttk.Frame(frame)
        tools.pack(fill="x", pady=(0, 10))
        self.status = tk.StringVar()
        ttk.Label(tools, textvariable=self.status).pack(side="left", fill="x", expand=True)
        ttk.Button(tools, text="Указать FFmpeg", command=self._choose_ffmpeg).pack(side="right")
        self.install_btn = ttk.Button(tools, text="Установить движок", command=self._install)
        self.install_btn.pack(side="right", padx=7)
        diagnostics = ttk.Frame(frame)
        diagnostics.pack(fill="x", pady=(0, 10))
        self.diagnose_btn = ttk.Button(diagnostics, text="Проверить библиотеки", command=self._diagnose)
        self.diagnose_btn.pack(side="left")
        self.repair_btn = ttk.Button(diagnostics, text="Восстановить зависимости", command=self._repair)
        self.repair_btn.pack(side="left", padx=(8, 0))
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(0, 10))
        self.run_btn = ttk.Button(actions, text="Преобразовать в 8-bit", command=self._convert)
        self.run_btn.pack(side="left")
        self.stop_btn = ttk.Button(actions, text="Остановить", command=self._stop, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        self.play_btn = ttk.Button(actions, text="Прослушать", command=self._play, state="disabled")
        self.play_btn.pack(side="left", padx=8)
        self.folder_btn = ttk.Button(actions, text="Открыть папку", command=self._open_result_folder, state="disabled")
        self.folder_btn.pack(side="left")
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=(2, 12))
        ttk.Label(frame, text="Журнал обработки").pack(anchor="w")
        log_frame = ttk.Frame(frame)
        log_frame.pack(fill="both", expand=True, pady=(5, 0))
        self.log = tk.Text(log_frame, bg="#101621", fg="#d3e1f3", insertbackground="white",
                           font=("Consolas", 9), wrap="word", height=9, padx=9, pady=9, relief="flat")
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        scrollbar.pack(side="right", fill="y")
        self.log.config(yscrollcommand=scrollbar.set)
        self._write("Готово. Для конвертации нужны Python 3.11 x64, FFmpeg и движок audio8bit.")
        self._refresh_status()

    def _path_input(self, frame, title, key, chooser):
        ttk.Label(frame, text=title).pack(anchor="w")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(3, 10))
        var = tk.StringVar(value=self.saved.get(key, ""))
        self.fields[key] = var
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Обзор…", command=chooser).pack(side="left", padx=(8, 0))

    def _combo(self, frame, title, key, mapping, default):
        ttk.Label(frame, text=title).pack(anchor="w")
        self._combo_inline(frame, key, mapping, default, fill=True)

    def _combo_inline(self, frame, key, mapping, default, fill=False):
        old = str(self.saved.get(key, default))
        label = next((a for a,b in mapping.items() if b == old), next(iter(mapping)))
        var = tk.StringVar(value=label)
        self.fields[key] = (var, mapping)
        widget = ttk.Combobox(frame, textvariable=var, values=list(mapping), state="readonly", width=12)
        if fill:
            widget.pack(fill="x", pady=(3, 10))
        else:
            widget.pack(side="left", padx=8)

    def _choose_file(self):
        filename = filedialog.askopenfilename(
            title="Выберите аудиофайл",
            filetypes=[("Музыка", "*.wav *.mp3 *.ogg *.flac *.m4a *.aac *.opus *.wma"), ("Все файлы", "*.*")])
        if filename:
            self.fields["input"].set(filename)
            if not self.fields["folder"].get():
                self.fields["folder"].set(str(Path(filename).parent))

    def _choose_folder(self):
        folder = filedialog.askdirectory(title="Папка результата")
        if folder:
            self.fields["folder"].set(folder)

    def _choose_ffmpeg(self):
        path = filedialog.askopenfilename(title="Путь к ffmpeg.exe", filetypes=[("FFmpeg", "ffmpeg.exe")])
        if path:
            self.saved["ffmpeg"] = str(Path(path).parent)
            self._refresh_status()
            self._save()

    def options(self):
        result = {}
        for key, value in self.fields.items():
            if isinstance(value, tuple):
                var, mapping = value
                result[key] = mapping[var.get()]
            else:
                result[key] = value.get()
        result["ffmpeg"] = self.saved.get("ffmpeg", "")
        return result

    def _refresh_status(self):
        engine = "Движок установлен" if engine_python().is_file() else "Движок не установлен"
        ff = "FFmpeg найден" if ffmpeg_path(self.saved.get("ffmpeg", "")) else "FFmpeg не найден"
        self.status.set(engine + "  ·  " + ff)

    def _write(self, message):
        self.log.insert("end", str(message).rstrip() + "\n")
        self.log.see("end")

    def _launch(self, args, env=None):
        if self.stopping:
            return 130
        try:
            self.events.put(("log", "Запуск: " + args[0] + " …"))
            p = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                 errors="replace", bufsize=1, env=child_python_env(env),
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.process = p
            for line in p.stdout:
                self.events.put(("log", line.rstrip()))
            return p.wait()
        except OSError as exc:
            self.events.put(("log", "Ошибка запуска: " + str(exc)))
            return 127
        finally:
            self.process = None

    def _start(self, work):
        if self.busy:
            return
        self.busy = True
        self.stopping = False
        self.run_btn.configure(state="disabled")
        self.install_btn.configure(state="disabled")
        self.diagnose_btn.configure(state="disabled")
        self.repair_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress.start(12)
        def task():
            try:
                work()
            except Exception as exc:
                self.events.put(("log", "Ошибка: " + str(exc)))
            finally:
                self.events.put(("done", ""))
        threading.Thread(target=task, daemon=True).start()

    def _install(self):
        if engine_python().is_file() and not messagebox.askyesno("Обновить?", "Установить движок повторно?"):
            return
        self._write("Установка может загрузить несколько гигабайт зависимостей и модели ИИ.")
        self._start(self._install_worker)

    def _diagnose(self):
        if not engine_python().is_file():
            messagebox.showwarning("Движок", "Сначала установите движок.")
            return
        self._start(self._diagnose_worker)

    def _diagnose_worker(self):
        # Run imports in the *installed* venv, not in the frozen GUI process.
        # Tracebacks are deliberately preserved: an ImportError inside a
        # dependency must not be reported as if basic-pitch were absent.
        script = (
            "import sys, traceback, importlib.metadata as md\n"
            "print('Python:', sys.version, flush=True)\n"
            "for name in ('audio8bit', 'basic-pitch', 'pretty-midi', 'setuptools', "
            "'tensorflow', 'numpy', 'librosa'):\n"
            " try: print(name + ':', md.version(name), flush=True)\n"
            " except md.PackageNotFoundError: print(name + ': НЕ УСТАНОВЛЕН', flush=True)\n"
            "try:\n"
            " from basic_pitch.inference import predict\n"
            " print('Basic Pitch: импорт успешен', flush=True)\n"
            "except Exception:\n"
            " traceback.print_exc()\n"
            " sys.exit(1)\n"
        )
        self.events.put(("log", "Проверка Basic Pitch в окружении программы…"))
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        code = self._launch([str(engine_python()), "-c", script], env=env)
        self.basic_pitch_ok = code == 0 and not self.stopping
        if not self.basic_pitch_ok:
            self.events.put(("log", "Импорт Basic Pitch не прошёл. Выше находится реальная ошибка Python."))
        return self.basic_pitch_ok

    def _repair(self):
        if not engine_python().is_file():
            messagebox.showwarning("Движок", "Сначала установите движок.")
            return
        self._start(self._repair_worker)

    def _repair_worker(self):
        # Some transitive packages still import pkg_resources; recent
        # setuptools removed it. Keep a compatible version in this venv.
        self.basic_pitch_ok = False
        self.events.put(("log", "Проверка и восстановление совместимых зависимостей…"))
        code = self._launch([str(engine_python()), "-m", "pip", "install",
                             "--no-input", "--disable-pip-version-check",
                             "setuptools>=70,<81", "pretty_midi>=0.2.11.post0",
                             "basic-pitch>=0.4,<0.5"])
        if code != 0 or self.stopping:
            self.events.put(("log", f"Восстановление не завершено (код {code})."))
            return False
        self._launch([str(engine_python()), "-m", "pip", "check"])
        return self._diagnose_worker()

    def _install_worker(self):
        exe = engine_python()
        if not exe.is_file():
            python = external_python()
            if not python:
                self.events.put(("log", "Не найден Python 3.11 x64. Установите его через setup-prereqs.ps1."))
                return
            exe.parent.mkdir(parents=True, exist_ok=True)
            code = self._launch([python, "-m", "venv", str(home() / "engine")])
            if code != 0 or self.stopping:
                self.events.put(("log", f"Не удалось создать окружение (код {code})."))
                return
        code = self._launch([str(exe), "-m", "pip", "install", "--no-input",
                             "--disable-pip-version-check", "audio8bit==" + ENGINE])
        if code != 0 or self.stopping:
            self.events.put(("log", f"Установка не завершена (код {code})."))
            return
        if self._repair_worker():
            self.events.put(("log", "Движок установлен, импорт Basic Pitch проверен."))

    def _convert_with_preflight(self, cmd, env, result, method):
        if method == "transcribe" and not self.basic_pitch_ok:
            if not self._diagnose_worker():
                self.events.put(("log", "Обработка остановлена до разделения аудио: "
                                         "Basic Pitch не загружается. Попробуйте «Восстановить зависимости»."))
                return
        self._convert_worker(cmd, env, result)

    def _convert(self):
        try:
            opts = self.options()
            result = target_path(opts["input"], opts["folder"], opts["format"])
            cmd = convert_args(opts["input"], result, opts)
        except (KeyError, TypeError, ValueError) as exc:
            messagebox.showerror("Параметры", str(exc))
            return
        if not engine_python().is_file():
            messagebox.showwarning("Движок", "Сначала установите движок (нужен Python 3.11 x64).")
            return
        ff_dir = ffmpeg_path(opts["ffmpeg"])
        if not ff_dir:
            messagebox.showwarning("FFmpeg", "Не найдены ffmpeg.exe и ffprobe.exe. Укажите путь или установите FFmpeg.")
            return
        if result.is_file() and not messagebox.askyesno("Перезаписать?", f"Заменить файл?\n{result}"):
            return
        try:
            result.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Папка", str(exc))
            return
        self.result = None
        self.play_btn.configure(state="disabled")
        self.folder_btn.configure(state="disabled")
        self._save()
        self._write("\nПреобразование: " + Path(opts["input"]).name)
        self._write("Выход: " + str(result))
        env = dict(os.environ)
        env["PATH"] = ff_dir + os.pathsep + env.get("PATH", "")
        env["PYTHONUNBUFFERED"] = "1"
        self._start(lambda: self._convert_with_preflight(cmd, env, result, opts["method"]))

    def _convert_worker(self, cmd, env, result):
        code = self._launch(cmd, env)
        if code == 0 and result.is_file() and not self.stopping:
            self.events.put(("converted", str(result)))
            self.events.put(("log", "Конвертация завершена."))
        else:
            self.events.put(("log", f"Конвертация завершилась с кодом {code}."))

    def _stop(self):
        self.stopping = True
        p = self.process
        self._write("Остановка по запросу пользователя…")
        if p and p.poll() is None:
            try:
                subprocess.Popen(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except OSError as exc:
                self._write(str(exc))

    def _poll(self):
        try:
            for _ in range(100):
                kind, msg = self.events.get_nowait()
                if kind == "log":
                    self._write(msg)
                elif kind == "converted":
                    self.result = Path(msg)
                    self.play_btn.configure(state="normal")
                    self.folder_btn.configure(state="normal")
                elif kind == "done":
                    self.busy = False
                    self.progress.stop()
                    self.run_btn.configure(state="normal")
                    self.install_btn.configure(state="normal")
                    self.diagnose_btn.configure(state="normal")
                    self.repair_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    self._refresh_status()
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _play(self):
        if self.result and self.result.is_file():
            os.startfile(str(self.result))

    def _open_result_folder(self):
        if self.result:
            os.startfile(str(self.result.parent))

    def _close(self):
        if self.busy:
            if not messagebox.askyesno("Закрыть", "Остановить текущую операцию и закрыть программу?"):
                return
            self._stop()
        self._save()
        self.destroy()


if __name__ == "__main__":
    GUI().mainloop()
