import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import subprocess
import threading
import webbrowser
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import serial
import serial.tools.list_ports
from datetime import datetime
import csv
import time
import pandas as pd
import numpy as np
from tkmacosx import Button
import customtkinter as ctk

AIR_DENSITY = 1.298351265  # kg/m^3
LAB_DETAILS_URL = "https://drive.google.com/file/d/1WX5xK7Xqua2Vz-lO5Z7_klDieToz0dC8/view?usp=sharing"

SENSOR_COLORS = ["#1E90FF", "#F28484", "#28A745", "#FF8C00"]

# USB vendor IDs of Arduino boards and the USB-serial chips used on compatible boards
ARDUINO_USB_VIDS = {
    0x2341, 0x2A03,  # Arduino
    0x1A86,          # WCH CH340 / CH9102 (common on clones)
    0x10C4,          # Silicon Labs CP210x
    0x0403,          # FTDI
}
ARDUINO_PORT_KEYWORDS = ["arduino", "usb serial", "usb-serial", "usb to uart", "ch340",
                         "ch910", "cp210", "silicon labs", "ftdi", "wch"]


def _looks_like_arduino(port):
    """True if a serial port from serial.tools.list_ports looks like an Arduino."""
    if port.vid in ARDUINO_USB_VIDS:
        return True
    text = " ".join(filter(None, [port.description, port.manufacturer])).lower()
    return any(k in text for k in ARDUINO_PORT_KEYWORDS)


# ---------------------------------------------------------------------------
#  SHARED HELPERS (saving data, talking to the Arduino off the Tk thread)
# ---------------------------------------------------------------------------

DATA_FOLDER_NAME = "Go With The Flow Data"


def _desktop_dir():
    """The Desktop the user actually sees. On Windows this is often inside OneDrive,
    while ~/Desktop is an empty folder nobody looks at."""
    if sys.platform == "win32":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(260)
            # 0x10 = CSIDL_DESKTOPDIRECTORY
            if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0:
                return buf.value
        except Exception:
            pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


def _data_dir():
    """Folder that new CSV files are saved in (created if needed)."""
    for base in (_desktop_dir(), os.path.expanduser("~"), os.getcwd()):
        path = os.path.join(base, DATA_FOLDER_NAME)
        try:
            os.makedirs(path, exist_ok=True)
            if os.access(path, os.W_OK):
                return path
        except OSError:
            continue
    return os.getcwd()


def _open_folder(path):
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def _open_arduino(port):
    """Open the port, do the GReady handshake and ask which MUX ports have sensors.

    Runs on a background thread, so it must not touch Tk widgets.
    Returns (serial connection, list of MUX ports). Raises RuntimeError with a
    message for the status label.
    """
    if port.isdigit():
        port = "COM" + port
    try:
        # write_timeout: without it a write to a stuck port blocks forever on Windows
        ser = serial.Serial(port=port, baudrate=115200, timeout=1.0, write_timeout=2.0)
    except serial.SerialException as e:
        print(f"Can't open {port}: {e}")
        raise RuntimeError(f"Can't open {port}. Close the Arduino IDE Serial Monitor "
                           f"if it is open.")
    try:
        time.sleep(2)                 # opening the port resets the Arduino; let it boot
        ser.reset_input_buffer()

        ready = False
        for _ in range(3):
            ser.write(b"GReady\n")
            deadline = time.time() + 1.5
            while time.time() < deadline:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    print(f"Arduino says: {line}")
                if "Ready" in line:
                    ready = True
                    break
            if ready:
                break
        if not ready:
            raise RuntimeError(f"{port} didn't answer. Check it's the right port and the "
                               f"Arduino sketch is uploaded.")

        ser.write(b"PORTS\n")
        mux_ports = []
        deadline = time.time() + 3
        while time.time() < deadline:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line.startswith("Ports:,"):
                parts = line.split("Ports:,", 1)[1].split(",")
                mux_ports = [int(p) for p in parts if p.strip().isdigit()]
                print(f"Detected MUX ports: {mux_ports}")
                break
        return ser, mux_ports
    except Exception as e:
        ser.close()
        if isinstance(e, RuntimeError):
            raise
        print(f"Lost contact with {port}: {e}")
        raise RuntimeError(f"Lost contact with {port}. Unplug the Arduino, plug it back in "
                           f"and click Connect.")


def _request_reading(ser, timeout=6.0):
    """Send "a" and return one pressure per sensor, in Pa. Runs on a background thread.
    The Arduino answers in about 1.1 s."""
    ser.reset_input_buffer()
    ser.write(b"a\n")
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if line:
            print(f"Received: {line}")
        if line.startswith("Data:,"):
            raw_vals = line.split("Data:,", 1)[1].split(",")
            return [float(v) * 100 for v in raw_vals if v.strip()]   # hPa -> Pa
    raise TimeoutError("Timeout: no data received. Check the sensors and USB cable.")


def _run_in_background(root, work, on_done):
    """Run work() on a worker thread so the window keeps responding, then call
    on_done(result, error) back on the Tk thread."""
    result = {}

    def target():
        try:
            result["value"] = work()
        except Exception as e:
            result["error"] = e

    worker = threading.Thread(target=target, daemon=True)
    worker.start()

    def check():
        if worker.is_alive():
            root.after(50, check)
        elif root.winfo_exists():
            on_done(result.get("value"), result.get("error"))

    root.after(50, check)


def _build_file_bar(parent, file_path_var):
    """Top-left bar showing where the current CSV is saved, with an Open Folder button."""
    bar = tk.Frame(parent, bg="white")
    bar.grid_columnconfigure(0, weight=1)
    tk.Label(bar, textvariable=file_path_var, bg="white", fg="#333333", anchor="w",
             font=("Arial", 12), width=1).grid(row=0, column=0, sticky="ew", padx=(8, 4))
    Button(bar, text="Open Data Folder", bg="#E0E0E0", font=("Arial", 12),
           command=lambda: _open_folder(_data_dir())).grid(row=0, column=1, padx=4)
    return bar


NEW_FILE_HINT = "A new data file is created when you click Collect."


def _saving_to_text(filepath):
    """Short "Saving to:" text (e.g. Desktop › Go With The Flow Data › file.csv). The full
    path is too long for the window; Open Data Folder shows where it is."""
    folder = os.path.dirname(filepath)
    return (f"Saving to: {os.path.basename(os.path.dirname(folder))} › "
            f"{os.path.basename(folder)} › {os.path.basename(filepath)}")


def _short_heading(col):
    """Table heading for a CSV column name; the CSV keeps the full name."""
    return (col.replace("MUX Port ", "Port ")
               .replace("Pressure Difference", "ΔP")
               .replace("Static Ambient Pressure", "Ambient")
               .replace("Static Inside Pressure", "Inside")
               .replace("Pitot Pressure", "Pitot")
               .replace(" - Pressure (Pa)", " (Pa)"))


def _setup_table_columns(tree, columns, width):
    """Short headings, and columns never narrower than their heading."""
    import tkinter.font as tkfont
    heading_font = tkfont.nametofont("TkHeadingFont")
    for col in columns:
        text = _short_heading(col)
        fit = heading_font.measure(text) + 20
        tree.heading(col, text=text)
        tree.column(col, anchor="center", width=max(width, fit), minwidth=fit, stretch=True)


def launch_thrust_stand(master=None):
    _launch_experiment(master, "Thrust Stand Experiment")


def launch_pipe_flow(master=None):
    _launch_pipe_flow_window(master)


def launch_wind_tunnel(master=None):
    _launch_wind_tunnel_window(master)


def launch_diagnostic(master=None):
    _launch_diagnostic_window(master)


# ---------------------------------------------------------------------------
#  DIAGNOSTIC WINDOW
# ---------------------------------------------------------------------------

def _launch_diagnostic_window(master):
    standalone_root = None

    if master is None:
        standalone_root = tk.Tk()
        standalone_root.withdraw()
        master = standalone_root
    else:
        master.withdraw()

    root = tk.Toplevel(master)
    root.title("Diagnostic Test")
    root.geometry("1000x700")
    root.configure(bg="white")

    arduino = None
    running = False
    times = []
    sensor_pressures = []
    start_time = None

    def on_close():
        nonlocal running
        running = False
        try:
            if arduino is not None and arduino.is_open:
                arduino.close()
        except Exception:
            pass
        root.destroy()
        if standalone_root is not None:
            standalone_root.destroy()
        else:
            master.deiconify()

    root.protocol("WM_DELETE_WINDOW", on_close)

    arduino_status_var = tk.StringVar(value="Not Connected")
    port_var = tk.StringVar()

    def find_arduino_port():
        ports = serial.tools.list_ports.comports()
        for port in ports:
            desc = (port.description or "").lower()
            if _looks_like_arduino(port):
                return port.device
        return None

    def connect_arduino():
        nonlocal arduino
        port = port_var.get().strip() or find_arduino_port()
        if not port:
            arduino_status_var.set("No Arduino found")
            lbl_status.config(fg="red")
            return
        try:
            port_var.set(port)
            arduino = serial.Serial(port=port, baudrate=115200, timeout=0.1)
            arduino_status_var.set(f"Connected: {port}")
            lbl_status.config(fg="green")
        except serial.SerialException as e:
            arduino_status_var.set(f"Failed: {e}")
            lbl_status.config(fg="red")
            arduino = None

    def poll_arduino():
        nonlocal running, start_time
        if not running:
            return
        if arduino is None or not arduino.is_open:
            root.after(500, poll_arduino)
            return

        try:
            line = arduino.readline().decode("utf-8", errors="ignore").strip()
            if line.startswith("Data:,"):
                parts = line.split("Data:,", 1)[1].split(",")
                values = []
                for p in parts:
                    try:
                        values.append(float(p) * 100)
                    except ValueError:
                        values.append(None)

                if not sensor_pressures:
                    for _ in values:
                        sensor_pressures.append([])

                elapsed = time.time() - start_time
                times.append(elapsed)
                for i, v in enumerate(values):
                    if i < len(sensor_pressures):
                        sensor_pressures[i].append(v)

                cutoff = elapsed - 60
                while times and times[0] < cutoff:
                    times.pop(0)
                    for sp in sensor_pressures:
                        if sp:
                            sp.pop(0)

                ax.clear()
                for i, sp in enumerate(sensor_pressures):
                    ax.plot(times[:len(sp)], sp,
                            color=SENSOR_COLORS[i % len(SENSOR_COLORS)],
                            linewidth=1.5,
                            label=f"Sensor {i + 1}")
                ax.set_xlabel("Time (s)", fontsize=16)
                ax.set_ylabel("Pressure (Pa)", fontsize=16)
                ax.set_title("Live Pressure", fontsize=20)
                ax.legend()
                fig.tight_layout()
                canvas.draw()
        except Exception:
            pass

        root.after(100, poll_arduino)

    def start_stop():
        nonlocal running, start_time, times, sensor_pressures, arduino
        if not running:
            if arduino is None:
                arduino_status_var.set("Connect to Arduino first")
                lbl_status.config(fg="red")
                return
            times.clear()
            sensor_pressures.clear()
            start_time = time.time()
            running = True
            arduino.write("DIAG\n".encode())
            arduino.flush()
            btn_startstop.config(text="Stop", bg="#F28484")
            poll_arduino()
        else:
            running = False
            arduino.write("STOP\n".encode())
            arduino.flush()
            btn_startstop.config(text="Start", bg="#B0CA99")

    root.grid_rowconfigure(0, weight=1)
    root.grid_rowconfigure(1, weight=0)
    root.grid_columnconfigure(0, weight=1)

    frame_plot = tk.Frame(root, bg="white")
    frame_plot.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    frame_plot.grid_rowconfigure(0, weight=1)
    frame_plot.grid_columnconfigure(0, weight=1)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.set_xlabel("Time (s)", fontsize=16)
    ax.set_ylabel("Pressure (Pa)", fontsize=16)
    ax.set_title("Live Pressure", fontsize=20, fontweight="bold")
    canvas = FigureCanvasTkAgg(fig, frame_plot)
    canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

    frame_ctrl = tk.Frame(root, bg="white")
    frame_ctrl.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

    tk.Label(frame_ctrl, text="Port:", bg="white", font=("Arial", 14)).pack(side="left", padx=(0, 4))
    tk.Entry(frame_ctrl, textvariable=port_var, font=("Arial", 14), width=14).pack(side="left", padx=(0, 8))

    Button(frame_ctrl, text="Connect", bg="#B0CA99", font=("Arial", 14),
           command=connect_arduino).pack(side="left", padx=(0, 8))

    lbl_status = tk.Label(frame_ctrl, textvariable=arduino_status_var,
                          fg="red", bg="white", font=("Arial", 14))
    lbl_status.pack(side="left", padx=(0, 20))

    Button(frame_ctrl, text="Exit", bg="#F28484", font=("Arial", 14),
           command=on_close).pack(side="right", padx=(8, 0))

    btn_startstop = Button(frame_ctrl, text="Start", bg="#B0CA99",
                           font=("Arial", 14), command=start_stop)
    btn_startstop.pack(side="right", padx=(0, 8))

    if standalone_root is not None:
        standalone_root.mainloop()


# ---------------------------------------------------------------------------
#  PIPE FLOW WINDOW  — 4 pressure sensors, dedicated layout
# ---------------------------------------------------------------------------

def _launch_pipe_flow_window(master):
    standalone_root = None

    if master is None:
        standalone_root = tk.Tk()
        standalone_root.withdraw()
        master = standalone_root
    else:
        master.withdraw()

    root = tk.Toplevel(master)
    root.title("Pipe Flow Experiment")
    root.geometry("1440x900")
    root.minsize(1100, 700)
    root.configure(bg="white")

    # ── state ──────────────────────────────────────────────────────────────
    pos_var           = tk.StringVar(value="0")
    level_var         = tk.IntVar(value=1)
    port_var          = tk.StringVar()
    arduino_status_var = tk.StringVar(value="Not Connected")
    file_path_var      = tk.StringVar(value=NEW_FILE_HINT)

    arduino        = None
    file_handle    = None   # opened on the first Collect after New File
    busy           = False  # True while waiting on the Arduino
    NUM_SENSORS    = 4
    detected_ports = []
    CSV_COLS       = ["data #"] + [f"Sensor {i+1} - Pressure (Pa)" for i in range(NUM_SENSORS)]

    df = pd.DataFrame(columns=CSV_COLS)

    def _get_csv_cols():
        if detected_ports:
            return ["data #"] + [f"MUX Port {p} - Pressure (Pa)" for p in detected_ports]
        return ["data #"] + [f"Port {i} - Pressure (Pa)" for i in range(NUM_SENSORS)]

    # ── helpers ────────────────────────────────────────────────────────────

    def on_close():
        nonlocal arduino, file_handle
        try:
            if arduino is not None and arduino.is_open:
                arduino.close()
        except Exception:
            pass
        try:
            if file_handle is not None and not file_handle.closed:
                file_handle.close()
        except Exception:
            pass
        root.destroy()
        if standalone_root is not None:
            standalone_root.destroy()
        else:
            master.deiconify()

    root.protocol("WM_DELETE_WINDOW", on_close)

    def open_lab_details():
        webbrowser.open_new(LAB_DETAILS_URL)

    def set_status(text, color):
        arduino_status_var.set(text)
        lbl_not_conn.config(fg=color)

    def newfile_Callback():
        """Start a new run. The CSV itself is created on the first Collect."""
        nonlocal file_handle, df, table

        CSV_COLS[:] = _get_csv_cols()

        for widget in frame_DT.winfo_children():
            widget.destroy()
        table = build_table(frame_DT)

        try:
            if file_handle is not None and not file_handle.closed:
                file_handle.close()
        except Exception:
            pass
        file_handle = None
        file_path_var.set(NEW_FILE_HINT)

        df = pd.DataFrame(columns=CSV_COLS)
        refresh_all(df)
        pos_var.set("0")

    def _open_new_csv():
        nonlocal file_handle
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath  = os.path.join(_data_dir(), f"pipe_flow_{timestamp}.csv")
        print(f"Writing pipe flow data to {filepath}…")
        file_handle = open(filepath, "w", newline="")
        csv.writer(file_handle).writerow(CSV_COLS)
        file_handle.flush()
        file_path_var.set(_saving_to_text(filepath))

    def find_arduino_port():
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if _looks_like_arduino(port):
                print(f"Found Arduino on port: {port.device}")
                return port.device
        print("No Arduino found")
        return None

    def auto_connect_arduino():
        nonlocal arduino, busy
        if busy:
            return
        # A port typed in the Port box wins; otherwise search for one
        port = port_var.get().strip() or find_arduino_port()
        if not port:
            set_status("No Arduino found. Plug it in and try again.", "red")
            return
        port_var.set(port)
        if arduino is not None:
            arduino.close()   # reconnecting: release the port first
            arduino = None
        set_status(f"Connecting to {port}…", "black")
        busy = True

        def on_connected(result, error):
            nonlocal arduino, busy
            busy = False
            if error is not None:
                set_status(str(error), "red")
                return
            arduino, mux_ports = result
            detected_ports[:] = mux_ports
            if df.empty or _get_csv_cols() != CSV_COLS:
                newfile_Callback()
            if mux_ports:
                set_status(f"Connected to {port}. Sensors on MUX ports "
                           f"{', '.join(map(str, mux_ports))}.", "green")
            else:
                set_status(f"Connected to {port}, but the Arduino found no sensors. "
                           f"Check the wiring.", "red")

        _run_in_background(root, lambda: _open_arduino(port), on_connected)

    def collect_Callback():
        nonlocal busy
        if busy:
            return
        if arduino is None:
            set_status("Not connected to Arduino. Click Connect first.", "red")
            return

        x_pos = pos_var.get()
        set_status("Collecting…", "black")
        busy = True

        def on_reading(pressures, error):
            nonlocal busy, df
            busy = False
            if error is not None:
                set_status(str(error), "red")
                return
            if not pressures:
                set_status("Arduino found no sensors. Check wiring, then Connect again.", "red")
                return

            # The row must have exactly one value per pressure column, or the
            # values end up under the wrong headers. Missing sensors stay blank.
            n_cols  = len(CSV_COLS) - 1
            warning = len(pressures) != n_cols
            if warning:
                set_status(f"Got {len(pressures)} sensor readings but the file has {n_cols} "
                           f"sensor columns. Click Connect again after changing sensors.", "red")
            values = [str(p) for p in pressures[:n_cols]]
            values += [""] * (n_cols - len(values))
            row = [x_pos] + values
            try:
                if file_handle is None or file_handle.closed:
                    _open_new_csv()
                csv.writer(file_handle).writerow(row)
                file_handle.flush()
            except OSError as e:
                print(f"Can't save data: {e}")
                set_status("Can't save data. If the CSV is open in Excel, close it "
                           "and Collect again.", "red")
                return
            print(f"Wrote to CSV: {row}")

            df = pd.read_csv(file_handle.name)
            refresh_all(df)
            try:
                pos_var.set(str(int(float(x_pos) + level_var.get())))
            except ValueError:
                pass
            if not warning:
                set_status(f"Saved point {len(df)}.", "green")

        _run_in_background(root, lambda: _request_reading(arduino), on_reading)

    # ── plotting ────────────────────────────────────────────────────────────

    def refresh_plots(dataframe):
        pressure_cols = CSV_COLS[1:]  # skip "data #"
        for i, ax in enumerate(axes):
            ax.clear()
            col = pressure_cols[i] if i < len(pressure_cols) else None
            ax.set_xlabel("data #", fontsize=10)
            ax.set_ylabel("Pressure (Pa)", fontsize=10)
            ax.set_title(col or f"Sensor {i+1}", fontsize=12, fontweight="bold",
                         color=SENSOR_COLORS[i])
            if not dataframe.empty and col and col in dataframe.columns:
                ax.plot(dataframe["data #"], dataframe[col],
                        color=SENSOR_COLORS[i], linewidth=1.8, marker="o")
            canvases[i].draw()

    # ── table ───────────────────────────────────────────────────────────────

    def build_table(parent):
        tree = ttk.Treeview(parent, columns=CSV_COLS, show="headings")
        _setup_table_columns(tree, CSV_COLS, 110)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        return tree

    def refresh_table(dataframe):
        for row in table.get_children():
            table.delete(row)
        for _, row in dataframe.iterrows():
            table.insert("", tk.END, values=list(row))

    def refresh_all(dataframe):
        refresh_plots(dataframe)
        refresh_table(dataframe)


    # ── layout ──────────────────────────────────────────────────────────────
    #
    #  col 0-1 : 2×2 graph grid   col 2-3 : table + controls
    #  row 0   : top bar
    #  row 1-2 : graphs / table
    #  row 3   : bottom controls

    root.grid_columnconfigure(0, weight=3)
    root.grid_columnconfigure(1, weight=3)
    root.grid_columnconfigure(2, weight=2, minsize=160)
    root.grid_columnconfigure(3, weight=2, minsize=160)
    for r in range(4):
        root.grid_rowconfigure(r, weight=1 if r in (1, 2) else 0)

    # Top bar
    _build_file_bar(root, file_path_var).grid(row=0, column=0, columnspan=2,
                                              sticky="ew", padx=4, pady=4)
    Button(root, text="Lab Details", bg="#B4DCEB", font=("Arial", 13),
           command=open_lab_details).grid(row=0, column=2, sticky="ew", padx=4, pady=4)
    Button(root, text="Exit", bg="#F28484", font=("Arial", 13),
           command=on_close).grid(row=0, column=3, sticky="ew", padx=4, pady=4)

    # ── 2×2 graph grid ──────────────────────────────────────────────────────
    graph_positions = [(1, 0), (1, 1), (2, 0), (2, 1)]
    figs, axes, canvases = [], [], []

    for idx, (grow, gcol) in enumerate(graph_positions):
        frame = tk.Frame(root, bg="white", relief="flat", bd=1)
        frame.grid(row=grow, column=gcol, sticky="nsew", padx=6, pady=6)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        fig, ax = plt.subplots(figsize=(4, 2.8), layout="constrained")
        ax.set_xlabel("data #", fontsize=10)
        ax.set_ylabel("Pressure (Pa)", fontsize=10)
        ax.set_title(f"Sensor {idx+1}", fontsize=12, fontweight="bold",
                     color=SENSOR_COLORS[idx])

        cv = FigureCanvasTkAgg(fig, frame)
        cv.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        figs.append(fig)
        axes.append(ax)
        canvases.append(cv)

    # ── data table ──────────────────────────────────────────────────────────
    frame_DT = tk.Frame(root, bg="white")
    frame_DT.grid(row=1, column=2, columnspan=2, rowspan=2,
                  sticky="nsew", padx=8, pady=8)
    frame_DT.grid_propagate(False)   # the table scrolls rather than widening the window
    table = build_table(frame_DT)

    # ── arduino status ──────────────────────────────────────────────────────
    frame_status = tk.Frame(root, bg="white")
    frame_status.grid(row=3, column=0, sticky="nsew", padx=15, pady=10)
    for i in range(2):
        frame_status.grid_columnconfigure(i, weight=1, minsize=120)
    for j in range(3):
        frame_status.grid_rowconfigure(j, weight=1, minsize=30)

    tk.Label(frame_status, text="Arduino Status:", bg="white",
             font=("Arial", 15)).grid(row=0, column=0, sticky="ew")
    lbl_not_conn = tk.Label(frame_status, textvariable=arduino_status_var,
                            fg="red", bg="white", font=("Arial", 15),
                            width=1, height=3)
    lbl_not_conn.grid(row=0, column=1, sticky="ew")
    lbl_not_conn.bind("<Configure>", lambda e: e.widget.config(wraplength=max(e.width - 4, 50)))

    tk.Label(frame_status, text="Port:", bg="white",
             font=("Arial", 15)).grid(row=1, column=0, sticky="ew")
    tk.Entry(frame_status, textvariable=port_var,
             font=("Arial", 13)).grid(row=1, column=1, sticky="ew")

    Button(frame_status, text="Connect", bg="#B0CA99", font=("Arial", 14),
           command=auto_connect_arduino).grid(row=2, column=0, columnspan=2,
                                              sticky="ew", pady=(8, 0))

    # ── position / level ────────────────────────────────────────────────────
    frame_tp = tk.Frame(root, bg="white")
    frame_tp.grid(row=3, column=1, sticky="nsew", padx=15, pady=10)
    frame_tp.grid_columnconfigure(0, weight=1)
    for i in range(6):
        frame_tp.grid_rowconfigure(i, weight=1)

    tk.Label(frame_tp, text="Data Collection number:", bg="white",
             font=("Arial", 15)).grid(row=0, column=0, sticky="ew")
    tk.Entry(frame_tp, textvariable=pos_var,
             font=("Arial", 13)).grid(row=1, column=0, sticky="ew")

    auto_increment_var = ctk.BooleanVar(value=True)
    ctk.CTkSwitch(frame_tp, text="Auto-increment (+1)", variable=auto_increment_var,
                  font=("Arial", 13),
                  command=lambda: level_var.set(1 if auto_increment_var.get() else 0)
                  ).grid(row=2, column=0, sticky="w", pady=(8, 0))

    # ── bottom action buttons ───────────────────────────────────────────────
    Button(root, text="Collect", bg="#B0CA99", font=("Arial", 16),
           command=collect_Callback).grid(row=3, column=2, sticky="nsew",
                                          padx=8, pady=12, ipady=16)
    Button(root, text="New File", bg="#1E90FF", font=("Arial", 16),
           command=newfile_Callback).grid(row=3, column=3, sticky="nsew",
                                          padx=8, pady=12, ipady=16)

    # ── init ────────────────────────────────────────────────────────────────
    newfile_Callback()

    if standalone_root is not None:
        standalone_root.mainloop()


#  WIND TUNNEL WINDOW  

def _launch_wind_tunnel_window(master):
    standalone_root = None

    if master is None:
        standalone_root = tk.Tk()
        standalone_root.withdraw()
        master = standalone_root
    else:
        master.withdraw()

    root = tk.Toplevel(master)
    root.title("Wind Tunnel Experiment")
    root.geometry("1440x900")
    root.minsize(1100, 700)
    root.configure(bg="white")

    # ── state ──────────────────────────────────────────────────────────────
    pos_var            = tk.StringVar(value="0")
    level_var          = tk.IntVar(value=1)
    drag_var           = tk.StringVar()
    object_var         = tk.StringVar(value="Big Teardrop")
    port_var           = tk.StringVar()
    arduino_status_var = tk.StringVar(value="Not Connected")
    file_path_var      = tk.StringVar(value=NEW_FILE_HINT)

    OBJECT_TYPES   = ["Big Teardrop", "Small Teardrop", "Half-Sphere"]
    detected_ports = []
    CSV_COLS       = ["data #", "Object Type", "Drag Force (N)",
                      "Port 0 - Static Ambient Pressure (Pa)", "Port 1 - Static Inside Pressure (Pa)"]

    arduino     = None
    file_handle = None   # opened on the first Collect after New File
    busy        = False  # True while waiting on the Arduino
    df          = pd.DataFrame(columns=CSV_COLS)

    def _get_csv_cols():
        if len(detected_ports) >= 2:
            return ["data #", "Object Type", "Drag Force (N)",
                    f"MUX Port {detected_ports[0]} - Static Ambient Pressure (Pa)",
                    f"MUX Port {detected_ports[1]} - Static Inside Pressure (Pa)"]
        return ["data #", "Object Type", "Drag Force (N)",
                "Port 0 - Static Ambient Pressure (Pa)", "Port 1 - Static Inside Pressure (Pa)"]

    # ── helpers ────────────────────────────────────────────────────────────

    def on_close():
        nonlocal arduino, file_handle
        try:
            if arduino is not None and arduino.is_open:
                arduino.close()
        except Exception:
            pass
        try:
            if file_handle is not None and not file_handle.closed:
                file_handle.close()
        except Exception:
            pass
        root.destroy()
        if standalone_root is not None:
            standalone_root.destroy()
        else:
            master.deiconify()

    root.protocol("WM_DELETE_WINDOW", on_close)

    def open_lab_details():
        webbrowser.open_new(LAB_DETAILS_URL)

    def set_status(text, color):
        arduino_status_var.set(text)
        lbl_not_conn.config(fg=color)

    def newfile_Callback():
        """Start a new run. The CSV itself is created on the first Collect."""
        nonlocal file_handle, df, table

        CSV_COLS[:] = _get_csv_cols()

        for widget in frame_DT.winfo_children():
            widget.destroy()
        table = build_table(frame_DT)

        try:
            if file_handle is not None and not file_handle.closed:
                file_handle.close()
        except Exception:
            pass
        file_handle = None
        file_path_var.set(NEW_FILE_HINT)

        df = pd.DataFrame(columns=CSV_COLS)
        refresh_all(df)
        pos_var.set("0")

    def _open_new_csv():
        nonlocal file_handle
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath  = os.path.join(_data_dir(), f"wind_tunnel_{timestamp}.csv")
        print(f"Writing wind tunnel data to {filepath}…")
        file_handle = open(filepath, "w", newline="")
        csv.writer(file_handle).writerow(CSV_COLS)
        file_handle.flush()
        file_path_var.set(_saving_to_text(filepath))

    def find_arduino_port():
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if _looks_like_arduino(port):
                print(f"Found Arduino on port: {port.device}")
                return port.device
        print("No Arduino found")
        return None

    def auto_connect_arduino():
        nonlocal arduino, busy
        if busy:
            return
        # A port typed in the Port box wins; otherwise search for one
        port = port_var.get().strip() or find_arduino_port()
        if not port:
            set_status("No Arduino found. Plug it in and try again.", "red")
            return
        port_var.set(port)
        if arduino is not None:
            arduino.close()   # reconnecting: release the port first
            arduino = None
        set_status(f"Connecting to {port}…", "black")
        busy = True

        def on_connected(result, error):
            nonlocal arduino, busy
            busy = False
            if error is not None:
                set_status(str(error), "red")
                return
            arduino, mux_ports = result
            detected_ports[:] = mux_ports
            if df.empty or _get_csv_cols() != CSV_COLS:
                newfile_Callback()
            if mux_ports:
                set_status(f"Connected to {port}. Sensors on MUX ports "
                           f"{', '.join(map(str, mux_ports))}.", "green")
            else:
                set_status(f"Connected to {port}, but the Arduino found no sensors. "
                           f"Check the wiring.", "red")

        _run_in_background(root, lambda: _open_arduino(port), on_connected)

    def collect_Callback():
        nonlocal busy
        if busy:
            return
        if arduino is None:
            set_status("Not connected to Arduino. Click Connect first.", "red")
            return

        x_pos       = pos_var.get()
        drag        = drag_var.get()
        object_type = object_var.get()
        set_status("Collecting…", "black")
        busy = True

        def on_reading(pressures, error):
            nonlocal busy, df
            busy = False
            if error is not None:
                set_status(str(error), "red")
                return
            ambient_press = pressures[0] if len(pressures) > 0 else 0.0
            inside_press  = pressures[1] if len(pressures) > 1 else 0.0
            warning = len(pressures) < 2
            if warning:
                set_status(f"Got {len(pressures)} sensor reading(s), need 2. "
                           f"Check the wiring, then Connect again.", "red")
            row = [x_pos, object_type, drag, str(ambient_press), str(inside_press)]
            try:
                if file_handle is None or file_handle.closed:
                    _open_new_csv()
                csv.writer(file_handle).writerow(row)
                file_handle.flush()
            except OSError as e:
                print(f"Can't save data: {e}")
                set_status("Can't save data. If the CSV is open in Excel, close it "
                           "and Collect again.", "red")
                return
            print(f"Wrote to CSV: {row}")

            df = pd.read_csv(file_handle.name)
            refresh_all(df)
            try:
                pos_var.set(str(int(float(x_pos) + level_var.get())))
            except ValueError:
                pass
            if not warning:
                set_status(f"Saved point {len(df)}.", "green")

        _run_in_background(root, lambda: _request_reading(arduino), on_reading)

    # ── plotting ────────────────────────────────────────────────────────────

    def refresh_plots(dataframe):
        ax_amb.clear()
        ax_amb.set_xlabel("data #", fontsize=11)
        ax_amb.set_ylabel("Pressure (Pa)", fontsize=11)
        ax_amb.set_title("Static Ambient Pressure", fontsize=13, fontweight="bold",
                         color=SENSOR_COLORS[0])
        amb_col = CSV_COLS[3]
        if not dataframe.empty and amb_col in dataframe.columns:
            ax_amb.plot(dataframe["data #"], dataframe[amb_col],
                        color=SENSOR_COLORS[0], linewidth=1.8, marker="o")
        canvas_amb.draw()

        ins_col = CSV_COLS[4]
        ax_ins.clear()
        ax_ins.set_xlabel("data #", fontsize=11)
        ax_ins.set_ylabel("Pressure (Pa)", fontsize=11)
        ax_ins.set_title("Static Inside Pressure", fontsize=13, fontweight="bold",
                         color=SENSOR_COLORS[1])
        if not dataframe.empty and ins_col in dataframe.columns:
            ax_ins.plot(dataframe["data #"], dataframe[ins_col],
                        color=SENSOR_COLORS[1], linewidth=1.8, marker="o")
        canvas_ins.draw()



    def build_table(parent):
        tree = ttk.Treeview(parent, columns=CSV_COLS, show="headings")
        _setup_table_columns(tree, CSV_COLS, 130)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        return tree

    def refresh_table(dataframe):
        for row in table.get_children():
            table.delete(row)
        for _, row in dataframe.iterrows():
            table.insert("", tk.END, values=list(row))

    def refresh_all(dataframe):
        refresh_plots(dataframe)
        refresh_table(dataframe)



    root.grid_columnconfigure(0, weight=3)
    root.grid_columnconfigure(1, weight=3)
    root.grid_columnconfigure(2, weight=2, minsize=160)
    root.grid_columnconfigure(3, weight=2, minsize=160)
    for r in range(4):
        root.grid_rowconfigure(r, weight=1 if r in (1, 2) else 0)

    # Top bar
    _build_file_bar(root, file_path_var).grid(row=0, column=0, columnspan=2,
                                              sticky="ew", padx=4, pady=4)
    Button(root, text="Lab Details", bg="#B4DCEB", font=("Arial", 13),
           command=open_lab_details).grid(row=0, column=2, sticky="ew", padx=4, pady=4)
    Button(root, text="Exit", bg="#F28484", font=("Arial", 13),
           command=on_close).grid(row=0, column=3, sticky="ew", padx=4, pady=4)

    # ── ambient pressure graph ──────────────────────────────────────────────
    frame_amb = tk.Frame(root, bg="white")
    frame_amb.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
    frame_amb.grid_rowconfigure(0, weight=1)
    frame_amb.grid_columnconfigure(0, weight=1)

    fig_amb, ax_amb = plt.subplots(figsize=(5, 2.8), layout="constrained")
    ax_amb.set_xlabel("data #", fontsize=11)
    ax_amb.set_ylabel("Pressure (Pa)", fontsize=11)
    ax_amb.set_title("Static Ambient Pressure", fontsize=13, fontweight="bold",
                     color=SENSOR_COLORS[0])
    canvas_amb = FigureCanvasTkAgg(fig_amb, frame_amb)
    canvas_amb.get_tk_widget().grid(row=0, column=0, sticky="nsew")

    # ── inside pressure graph ───────────────────────────────────────────────
    frame_ins = tk.Frame(root, bg="white")
    frame_ins.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
    frame_ins.grid_rowconfigure(0, weight=1)
    frame_ins.grid_columnconfigure(0, weight=1)

    fig_ins, ax_ins = plt.subplots(figsize=(5, 2.8), layout="constrained")
    ax_ins.set_xlabel("data #", fontsize=11)
    ax_ins.set_ylabel("Pressure (Pa)", fontsize=11)
    ax_ins.set_title("Static Inside Pressure", fontsize=13, fontweight="bold",
                     color=SENSOR_COLORS[1])
    canvas_ins = FigureCanvasTkAgg(fig_ins, frame_ins)
    canvas_ins.get_tk_widget().grid(row=0, column=0, sticky="nsew")

    # ── data table ──────────────────────────────────────────────────────────
    frame_DT = tk.Frame(root, bg="white")
    frame_DT.grid(row=1, column=2, columnspan=2, rowspan=2,
                  sticky="nsew", padx=8, pady=8)
    frame_DT.grid_propagate(False)   # the table scrolls rather than widening the window
    table = build_table(frame_DT)

    # ── arduino status ──────────────────────────────────────────────────────
    frame_status = tk.Frame(root, bg="white")
    frame_status.grid(row=3, column=0, sticky="nsew", padx=15, pady=10)
    for i in range(2):
        frame_status.grid_columnconfigure(i, weight=1, minsize=120)
    for j in range(3):
        frame_status.grid_rowconfigure(j, weight=1, minsize=30)

    tk.Label(frame_status, text="Arduino Status:", bg="white",
             font=("Arial", 15)).grid(row=0, column=0, sticky="ew")
    lbl_not_conn = tk.Label(frame_status, textvariable=arduino_status_var,
                            fg="red", bg="white", font=("Arial", 15),
                            width=1, height=3)
    lbl_not_conn.grid(row=0, column=1, sticky="ew")
    lbl_not_conn.bind("<Configure>", lambda e: e.widget.config(wraplength=max(e.width - 4, 50)))

    tk.Label(frame_status, text="Port:", bg="white",
             font=("Arial", 15)).grid(row=1, column=0, sticky="ew")
    tk.Entry(frame_status, textvariable=port_var,
             font=("Arial", 13)).grid(row=1, column=1, sticky="ew")

    Button(frame_status, text="Connect", bg="#B0CA99", font=("Arial", 14),
           command=auto_connect_arduino).grid(row=2, column=0, columnspan=2,
                                              sticky="ew", pady=(8, 0))

    # ── experiment inputs ───────────────────────────────────────────────────
    _script_dir = os.path.dirname(os.path.abspath(__file__))

    def _load_image(filename, size=50):
        path = os.path.join(_script_dir, filename)
        if not os.path.isfile(path):
            return None
        try:
            from PIL import Image, ImageTk
            img = Image.open(path).convert("RGBA")
            img.thumbnail((size, size), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except ImportError:
            photo = tk.PhotoImage(file=path)
            factor = max(1, photo.width() // size, photo.height() // size)
            return photo.subsample(factor, factor)

    _object_images = {
        "Big Teardrop":   _load_image("Large_Teardrop.webp", size=90),
        "Small Teardrop": _load_image("Small_Teardrop.webp", size=50),
        "Half-Sphere":    _load_image("Half_Sphere.png",     size=70),
    }

    frame_inputs = tk.Frame(root, bg="white")
    frame_inputs.grid(row=3, column=1, sticky="nsew", padx=15, pady=10)
    frame_inputs.grid_columnconfigure(0, weight=1)
    for i in range(8):
        frame_inputs.grid_rowconfigure(i, weight=1)

    tk.Label(frame_inputs, text="Object Type:", bg="white",
             font=("Arial", 15)).grid(row=0, column=0, sticky="w")

    lbl_obj_img = tk.Label(frame_inputs, bg="white")
    lbl_obj_img.grid(row=1, column=0, pady=(2, 4))

    combo_obj = ttk.Combobox(frame_inputs, textvariable=object_var, values=OBJECT_TYPES,
                             state="readonly", font=("Arial", 13))
    combo_obj.grid(row=2, column=0, sticky="ew")

    def _update_object_image(*_):
        img = _object_images.get(object_var.get())
        if img:
            lbl_obj_img.config(image=img, text="")
            lbl_obj_img.image = img
        else:
            lbl_obj_img.config(image="", text="(no image)")
            lbl_obj_img.image = None

    object_var.trace_add("write", _update_object_image)
    _update_object_image()

    tk.Label(frame_inputs, text="Drag Force (N):", bg="white",
             font=("Arial", 15)).grid(row=3, column=0, sticky="w", pady=(8, 0))
    tk.Entry(frame_inputs, textvariable=drag_var,
             font=("Arial", 13)).grid(row=4, column=0, sticky="ew")

    tk.Label(frame_inputs, text="Data # :", bg="white",
             font=("Arial", 15)).grid(row=5, column=0, sticky="w", pady=(8, 0))
    tk.Entry(frame_inputs, textvariable=pos_var,
             font=("Arial", 13)).grid(row=6, column=0, sticky="ew")

    auto_increment_var = ctk.BooleanVar(value=True)
    ctk.CTkSwitch(frame_inputs, text="Auto-increment (+1)", variable=auto_increment_var,
                  font=("Arial", 13),
                  command=lambda: level_var.set(1 if auto_increment_var.get() else 0)
                  ).grid(row=7, column=0, sticky="w", pady=(4, 0))

    # ── bottom action buttons ───────────────────────────────────────────────
    Button(root, text="Collect", bg="#B0CA99", font=("Arial", 18),
           command=collect_Callback).grid(row=3, column=2, sticky="nsew",
                                          padx=8, pady=12, ipady=16)
    Button(root, text="New File", bg="#1E90FF", font=("Arial", 18),
           command=newfile_Callback).grid(row=3, column=3, sticky="nsew",
                                          padx=8, pady=12, ipady=16)

    # ── init ────────────────────────────────────────────────────────────────
    newfile_Callback()

    if standalone_root is not None:
        standalone_root.mainloop()



#  THRUST STAND WINDOW

THRUST_HELP = (
    "1.  Plug in the Arduino with the USB cable and click Connect. "
    "The status turns green when it is ready.\n\n"
    "2.  Plug the two sensors into any multiplexer ports. The app works out which one "
    "is the pitot: once air is flowing, the pitot reads higher.\n\n"
    "3.  Thrust (g): type the scale reading before you Collect. It is saved with every "
    "point and stays filled in, so you only need to change it when the scale reading "
    "changes.\n\n"
    "4.  Position (mm): where the pitot tube is now. It starts at 0.\n\n"
    "5.  Click Collect and wait about a second. The point appears in the table and plots, "
    "and Position goes up by 1 mm (or 2 mm with the switch on).\n\n"
    "6.  Move the pitot tube to the new position and click Collect again.\n\n"
    "7.  New File starts a new run and sets Position back to 0. Every run is its own CSV "
    f"file in the \"{DATA_FOLDER_NAME}\" folder on your Desktop. Open Data Folder shows it."
)


def _launch_experiment(master, window_title):
    standalone_root = None

    if master is None:
        standalone_root = tk.Tk()
        standalone_root.withdraw()
        master = standalone_root
    else:
        master.withdraw()

    root = tk.Toplevel(master)
    root.title(window_title)
    root.geometry("1440x900")
    root.minsize(1200, 700)
    root.configure(bg="white")

    pos_var = tk.StringVar(value="0")
    level_var = tk.IntVar(value=1)
    thrust_var = tk.StringVar()
    port_var = tk.StringVar()
    arduino_status_var = tk.StringVar(value="Not Connected")
    file_path_var = tk.StringVar(value=NEW_FILE_HINT)

    arduino        = None
    file_handle    = None   # opened on the first Collect after New File
    busy           = False  # True while waiting on the Arduino
    detected_ports = []
    CSV_COLS       = []
    df             = pd.DataFrame()
    table          = None
    # Which sensor is the pitot is worked out per run: once air is flowing the pitot
    # always reads higher than ambient. Until then the lower MUX port is assumed.
    roles_swapped  = False
    roles_locked   = False

    def _role_indices():
        """Positions of the pitot and ambient values in each "Data:," line."""
        return (1, 0) if roles_swapped else (0, 1)

    def _get_csv_cols():
        if len(detected_ports) >= 2:
            pitot_i, amb_i = _role_indices()
            pitot_col = f"MUX Port {detected_ports[pitot_i]} - Pitot Pressure (Pa)"
            amb_col   = f"MUX Port {detected_ports[amb_i]} - Ambient (Pa)"
        else:
            pitot_col, amb_col = "Port 0 - Pitot Pressure (Pa)", "Port 1 - Ambient (Pa)"
        return ["x (mm)", pitot_col, amb_col, "Thrust(g)",
                "Pressure Difference (Pa)", "Velocity (m/s)"]

    def set_status(text, color):
        arduino_status_var.set(text)
        lbl_not_conn.config(fg=color)

    def on_close():
        nonlocal arduino, file_handle
        try:
            if arduino is not None and arduino.is_open:
                arduino.close()
        except Exception:
            pass
        try:
            if file_handle is not None and not file_handle.closed:
                file_handle.close()
        except Exception:
            pass
        root.destroy()
        if standalone_root is not None:
            standalone_root.destroy()
        else:
            master.deiconify()

    root.protocol("WM_DELETE_WINDOW", on_close)

    def open_lab_details():
        webbrowser.open_new(LAB_DETAILS_URL)

    def show_help():
        messagebox.showinfo("How to use the Thrust Stand", THRUST_HELP, parent=root)

    def newfile_Callback():
        """Start a new run. The CSV itself is created on the first Collect, so
        opening the window or clicking New File twice never leaves empty files."""
        nonlocal file_handle, df, table, roles_swapped, roles_locked
        try:
            if file_handle is not None and not file_handle.closed:
                file_handle.close()
        except Exception:
            pass
        file_handle = None
        file_path_var.set(NEW_FILE_HINT)
        roles_swapped = roles_locked = False

        CSV_COLS[:] = _get_csv_cols()
        df = pd.DataFrame(columns=CSV_COLS)
        for widget in frame_DT.winfo_children():
            widget.destroy()
        table = display_dataframe_as_table(frame_DT, df)
        refresh_plots(df)
        pos_var.set("0")

    def _open_new_csv():
        nonlocal file_handle
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = os.path.join(_data_dir(), f"thrust_stand_{timestamp}.csv")
        print(f"Writing data to {filepath}...")
        file_handle = open(filepath, "w", newline="")
        csv.writer(file_handle).writerow(CSV_COLS)
        file_handle.flush()
        file_path_var.set(_saving_to_text(filepath))

    def find_arduino_port():
        ports = serial.tools.list_ports.comports()
        for port in ports:
            desc = (port.description or "").lower()
            print(port.device, "-", desc)
            if _looks_like_arduino(port):
                print(f"Found Arduino on port: {port.device}")
                return port.device
        print("No Arduino found")
        return None

    def _swap_roles():
        """The pitot turned out to be the other sensor: relabel the columns and fix
        the points already saved in this run (their two pressures were swapped)."""
        nonlocal roles_swapped, df, file_handle, table
        old_cols = CSV_COLS[:]
        roles_swapped = not roles_swapped
        CSV_COLS[:] = _get_csv_cols()

        fixed = pd.DataFrame(columns=CSV_COLS)
        if not df.empty:
            fixed = df.copy()
            fixed.columns = CSV_COLS
            fixed[CSV_COLS[1]] = df[old_cols[2]]
            fixed[CSV_COLS[2]] = df[old_cols[1]]
            fixed[CSV_COLS[4]] = (fixed[CSV_COLS[1]] - fixed[CSV_COLS[2]]).round(4)
            fixed[CSV_COLS[5]] = np.sqrt(np.maximum(0, 2 * fixed[CSV_COLS[4]] / AIR_DENSITY)).round(4)
        df = fixed

        if file_handle is not None and not file_handle.closed:
            path = file_handle.name
            file_handle.close()
            df.to_csv(path, index=False)
            file_handle = open(path, "a", newline="")

        for widget in frame_DT.winfo_children():
            widget.destroy()
        table = display_dataframe_as_table(frame_DT, df)

    def auto_connect_arduino():
        nonlocal arduino, busy
        if busy:
            return
        # A port typed in the Port box wins; otherwise search for one
        port = port_var.get().strip() or find_arduino_port()
        if not port:
            set_status("No Arduino found. Plug it in and try again.", "red")
            return
        port_var.set(port)
        if arduino is not None:
            arduino.close()   # reconnecting: release the port first
            arduino = None
        set_status(f"Connecting to {port}…", "black")
        busy = True

        def on_connected(result, error):
            nonlocal arduino, busy
            busy = False
            if error is not None:
                set_status(str(error), "red")
                return
            arduino, mux_ports = result
            detected_ports[:] = mux_ports
            if df.empty or _get_csv_cols() != CSV_COLS:
                newfile_Callback()

            if len(mux_ports) >= 2:
                set_status(f"Connected to {port}.", "green")
            elif mux_ports:
                set_status(f"Connected, but only 1 sensor found (port {mux_ports[0]}). "
                           f"Thrust Stand needs 2. Check the wiring.", "red")
            else:
                set_status(f"Connected to {port}, but the Arduino found no sensors. "
                           f"Check the wiring.", "red")

        _run_in_background(root, lambda: _open_arduino(port), on_connected)

    def collect_Callback():
        nonlocal busy
        if busy:
            return
        if arduino is None:
            set_status("Not connected to Arduino. Click Connect first.", "red")
            return

        x_pos = pos_var.get()
        thrust = thrust_var.get()
        set_status("Collecting…", "black")
        busy = True

        def on_reading(pressures, error):
            nonlocal busy, df, roles_locked
            busy = False
            if error is not None:
                set_status(str(error), "red")
                return
            if len(pressures) < 2:
                set_status(f"Got {len(pressures)} sensor reading(s), need 2. "
                           f"Check the wiring, then Connect again.", "red")
                return

            pitot_i, amb_i = _role_indices()
            pitot_press   = pressures[pitot_i]
            ambient_press = pressures[amb_i]
            diff     = pitot_press - ambient_press

            # Sensor noise and offset stay well under 20 Pa, so the first bigger
            # difference shows which sensor is the pitot (it reads higher).
            detected_note = None
            if not roles_locked and abs(diff) > 20:
                roles_locked = True
                if diff < 0:
                    _swap_roles()
                    pitot_press, ambient_press, diff = ambient_press, pitot_press, -diff
                pitot_port = detected_ports[_role_indices()[0]] if len(detected_ports) >= 2 else None
                if pitot_port is not None:
                    detected_note = f"Pitot sensor detected on MUX port {pitot_port}."
            velocity = np.sqrt(max(0.0, 2 * diff / AIR_DENSITY))
            prev_pitot = df[CSV_COLS[1]].iloc[-1] if not df.empty else None

            try:
                if file_handle is None or file_handle.closed:
                    _open_new_csv()
                csv.writer(file_handle).writerow(
                    [x_pos, pitot_press, ambient_press, thrust, round(diff, 4), round(velocity, 4)])
                file_handle.flush()
            except OSError as e:
                print(f"Can't save data: {e}")
                set_status("Can't save data. If the CSV is open in Excel, close it "
                           "and Collect again.", "red")
                return
            print("Wrote to CSV")
            df = pd.read_csv(file_handle.name)
            refresh_all(df)

            try:
                pos_var.set(str(int(float(x_pos) + level_var.get())))
            except ValueError:
                pass

            if diff < -20:
                set_status("Pitot now reads lower than Ambient. Check the pitot tubing "
                           "is still attached.", "#C06000")
            elif prev_pitot is not None and pitot_press == prev_pitot:
                set_status("Pitot reading is exactly the same as the last point. The sensor "
                           "may be stuck: check it in the Diagnostic window.", "#C06000")
            elif detected_note:
                set_status(f"Saved point {len(df)}. {detected_note}", "green")
            else:
                set_status(f"Saved point {len(df)}.", "green")

        _run_in_background(root, lambda: _request_reading(arduino), on_reading)

    def display_dataframe_as_table(parent, df_example):
        tree = ttk.Treeview(parent, columns=list(df_example.columns), show="headings")
        _setup_table_columns(tree, list(df_example.columns), 90)
        for _, row in df_example.iterrows():
            tree.insert("", tk.END, values=list(row))
        vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        return tree

    def refresh_plots(dataframe):
        pitot_col, amb_col = CSV_COLS[1], CSV_COLS[2]

        ax1.clear()
        if not dataframe.empty:
            ax1.plot(dataframe["x (mm)"], dataframe[pitot_col], "o-", color="red", label="Pitot")
            ax1.plot(dataframe["x (mm)"], dataframe[amb_col], "o-",
                     color=SENSOR_COLORS[0], label="Ambient")
            ax1.legend(loc="best")
        ax1.set_xlabel("x (mm)", fontsize=12)
        ax1.set_ylabel("Pressure (Pa)", fontsize=12)

        ax2.clear()
        if not dataframe.empty:
            ax2.plot(dataframe["x (mm)"], dataframe["Velocity (m/s)"], "o-", color="red")
        ax2.set_xlabel("x (mm)", fontsize=12)
        ax2.set_ylabel("V (m/s)", fontsize=12)

        fig_press.canvas.draw()
        fig_velo.canvas.draw()

    def refresh_table(dataframe):
        for row in table.get_children():
            table.delete(row)
        for _, row in dataframe.iterrows():
            table.insert("", tk.END, values=list(row))
        children = table.get_children()
        if children:
            table.see(children[-1])

    def refresh_all(dataframe):
        refresh_plots(dataframe)
        refresh_table(dataframe)

    root.grid_columnconfigure(0, weight=3)
    root.grid_columnconfigure(1, weight=2)
    root.grid_columnconfigure(2, weight=1)
    root.grid_columnconfigure(3, weight=1)
    root.grid_rowconfigure(0, weight=0)
    root.grid_rowconfigure(1, weight=3)
    root.grid_rowconfigure(2, weight=3)
    root.grid_rowconfigure(3, weight=1, minsize=200)   # room for the Thrust/Position inputs

    _build_file_bar(root, file_path_var).grid(column=0, row=0, sticky="ew", padx=4, pady=4)
    Button(root, text="How to Use", bg="#FFE08A", command=show_help).grid(
        column=1, row=0, sticky="e", padx=4, pady=4)
    btn_lab_details = Button(root, text="Lab Details", bg="#B4DCEB", command=open_lab_details)
    btn_lab_details.grid(column=2, row=0, sticky="ew", padx=4, pady=4)
    btn_exit = Button(root, text="Exit", bg="#F28484", command=on_close)
    btn_exit.grid(column=3, row=0, sticky="ew", padx=4, pady=4)

    frame_PX = tk.Frame(root, bg="white")
    frame_PX.grid(column=0, row=1, columnspan=2, sticky="nsew", padx=8, pady=8)
    frame_PX.grid_columnconfigure(0, weight=1)
    frame_PX.grid_rowconfigure(1, weight=1)
    tk.Label(frame_PX, text="Absolute Pressure vs X-Position",
             font=("Arial", 20), bg="white").grid(column=0, row=0, sticky="nsew")
    fig_press = plt.Figure(figsize=(2.5, 2.5), dpi=100)
    canvas_press = FigureCanvasTkAgg(fig_press, frame_PX)
    canvas_press.get_tk_widget().grid(column=0, row=1, sticky="nsew")
    ax1 = fig_press.add_subplot(111)
    fig_press.tight_layout(pad=2.0)
    fig_press.set_constrained_layout(True)

    frame_VX = tk.Frame(root, bg="white")
    frame_VX.grid(column=0, row=2, columnspan=2, sticky="nsew", padx=8, pady=8)
    frame_VX.grid_columnconfigure(0, weight=1)
    frame_VX.grid_rowconfigure(1, weight=1)
    tk.Label(frame_VX, text="Velocity vs X-Position",
             bg="white", font=("Arial", 20)).grid(column=0, row=0, sticky="nsew")
    fig_velo = plt.Figure(figsize=(2.5, 2.5), dpi=100)
    canvas_velo = FigureCanvasTkAgg(fig_velo, frame_VX)
    canvas_velo.get_tk_widget().grid(column=0, row=1, sticky="nsew")
    ax2 = fig_velo.add_subplot(111)
    fig_velo.tight_layout(pad=2.0)
    fig_velo.set_constrained_layout(True)

    frame_DT = tk.Frame(root, bg="white")
    frame_DT.grid(column=2, row=1, columnspan=2, rowspan=2, sticky="nsew", padx=8, pady=8)
    frame_DT.grid_propagate(False)   # the table scrolls rather than widening the window

    frame_status = tk.Frame(root, bg="white")
    frame_status.grid(column=0, row=3, sticky="nsew", padx=15, pady=15)
    for i in range(2):
        frame_status.grid_columnconfigure(i, weight=1, minsize=120)
    for j in range(3):
        frame_status.grid_rowconfigure(j, weight=1, minsize=30)

    tk.Label(frame_status, text="Arduino Status:", bg="white",
             font=("Arial", 16)).grid(column=0, row=0, sticky="ew")
    lbl_not_conn = tk.Label(frame_status, textvariable=arduino_status_var,
                            fg="red", bg="white", font=("Arial", 16),
                            width=1, height=3)
    lbl_not_conn.grid(column=1, row=0, sticky="ew")
    lbl_not_conn.bind("<Configure>", lambda e: e.widget.config(wraplength=max(e.width - 4, 50)))
    tk.Label(frame_status, text="Port:", bg="white",
             font=("Arial", 16)).grid(column=0, row=1, sticky="ew")
    tk.Entry(frame_status, textvariable=port_var).grid(column=1, row=1, sticky="ew")
    Button(frame_status, text="Connect", bg="#B0CA99", command=auto_connect_arduino,
           font=("Arial", 15)).grid(column=0, row=2, columnspan=2, sticky="ew", pady=(8, 0))

    frame_tp = tk.Frame(root, bg="white")
    frame_tp.grid(column=1, row=3, sticky="nsew", padx=15, pady=15)
    frame_tp.grid_columnconfigure(0, weight=1, minsize=200)
    for i in range(5):
        frame_tp.grid_rowconfigure(i, weight=1)

    tk.Label(frame_tp, text="Thrust (g):", bg="white",
             font=("Arial", 16)).grid(column=0, row=0, sticky="w")
    tk.Entry(frame_tp, textvariable=thrust_var).grid(column=0, row=1, sticky="ew")
    tk.Label(frame_tp, text="Position (mm):", bg="white",
             font=("Arial", 16)).grid(column=0, row=2, sticky="w")
    tk.Entry(frame_tp, textvariable=pos_var).grid(column=0, row=3, sticky="ew")
    auto_increment_var = ctk.BooleanVar(value=False)
    level_var.set(1)

    def on_increment_toggle():
        if auto_increment_var.get():
            level_var.set(2)
            increment_switch.configure(text="Step +2 mm per Collect")
        else:
            level_var.set(1)
            increment_switch.configure(text="Step +1 mm per Collect")

    increment_switch = ctk.CTkSwitch(frame_tp, text="Step +1 mm per Collect",
                                     variable=auto_increment_var, font=("Arial", 14),
                                     command=on_increment_toggle)
    increment_switch.grid(column=0, row=4, sticky="w", pady=(4, 0))

    Button(root, text="Collect", bg="#B0CA99", command=collect_Callback,
           font=("Arial", 18)).grid(column=2, row=3, sticky="nsew", padx=8, pady=15, ipady=18)
    Button(root, text="New File", bg="#1E90FF", command=newfile_Callback,
           font=("Arial", 18)).grid(column=3, row=3, sticky="nsew", padx=8, pady=15, ipady=18)

    newfile_Callback()

    if standalone_root is not None:
        standalone_root.mainloop()


# ---------------------------------------------------------------------------
#  WELCOME SCREEN
# ---------------------------------------------------------------------------

def show_welcome_screen():
    root = tk.Tk()
    root.title("Welcome")
    root.geometry("1100x800")
    root.minsize(900, 650)
    root.configure(bg="#dbe6f5")

    root.grid_columnconfigure(0, weight=1)
    for r in range(7):
        root.grid_rowconfigure(r, weight=1)

    tk.Label(root, text="Laboratory Control Suite", font=("Arial", 38, "bold"),
             bg="#dbe6f5", fg="#0c366b").grid(row=1, column=0, pady=(30, 10))
    tk.Label(root, text="Select an experiment to begin", font=("Arial", 20),
             bg="#dbe6f5", fg="#0c366b").grid(row=2, column=0, pady=(0, 30))

    button_frame = tk.Frame(root, bg="#dbe6f5")
    button_frame.grid(row=3, column=0)

    Button(button_frame, text="Launch Thrust Stand", font=("Arial", 18, "bold"),
           bg="#1e90ff", fg="white", width=300, height=55,
           command=lambda: launch_thrust_stand(root)).grid(row=0, column=0, pady=10)

    Button(button_frame, text="Launch Pipe Flow", font=("Arial", 18, "bold"),
           bg="#28a745", fg="white", width=300, height=55,
           command=lambda: launch_pipe_flow(root)).grid(row=1, column=0, pady=10)

    Button(button_frame, text="Launch Wind Tunnel", font=("Arial", 18, "bold"),
           bg="#ff8c00", fg="white", width=300, height=55,
           command=lambda: launch_wind_tunnel(root)).grid(row=2, column=0, pady=10)

    Button(button_frame, text="Launch Diagnostic", font=("Arial", 18, "bold"),
           bg="#6a5acd", fg="white", width=300, height=55,
           command=lambda: launch_diagnostic(root)).grid(row=3, column=0, pady=10)

    root.mainloop()


if __name__ == "__main__":
    show_welcome_screen()