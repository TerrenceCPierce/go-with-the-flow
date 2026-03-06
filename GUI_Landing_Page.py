import tkinter as tk
from tkmacosx import Button
from GUI import launch_thrust_stand
from GUI import launch_pipe_flow
from GUI import launch_wind_tunnel

# --- Landing Page ---
if __name__ == "__main__":
    landing = tk.Tk()
    landing.title("Welcome")
    landing.geometry("700x500")
    landing.configure(bg="#e6f0ff")

    # Gradient simulation with color bands
    for i, color in enumerate(["#cce0ff", "#d6e6ff", "#e0ecff", "#e6f0ff"]):
        frame = tk.Frame(landing, bg=color, height=100)
        frame.pack(fill="x")

    lbl_title = tk.Label(
        landing,
        text="Laboratory Control Suite",
        font=("Helvetica", 28, "bold"),
        bg="#e6f0ff",
        fg="#00264d"
    )
    lbl_title.place(relx=0.5, rely=0.22, anchor="center")

    lbl_sub = tk.Label(
        landing,
        text="Select an experiment to begin",
        font=("Helvetica", 14),
        bg="#e6f0ff",
        fg="#003366"
    )
    lbl_sub.place(relx=0.5, rely=0.32, anchor="center")

    # ---- Button Callbacks ----
    def open_thrust_stand():
        landing.destroy()
        launch_thrust_stand()

    def open_pipe_flow():
        landing.destroy()
        launch_pipe_flow()

    def open_wind_tunnel():
        landing.destroy()
        launch_wind_tunnel()

    # ---- Buttons ----
    btn_ts = Button(
        landing,
        text="Launch Thrust Stand",
        bg="#1E90FF",
        fg="white",
        font=("Helvetica", 16, "bold"),
        command=open_thrust_stand,
        borderless=1,
    )
    btn_ts.place(relx=0.5, rely=0.50, anchor="center", width=260, height=55)

    btn_pf = Button(
        landing,
        text="Launch Pipe Flow",
        bg="#28A745",     # Green theme
        fg="white",
        font=("Helvetica", 16, "bold"),
        command=open_pipe_flow,
        borderless=1,
    )
    btn_pf.place(relx=0.5, rely=0.63, anchor="center", width=260, height=55)

    btn_wt = Button(
        landing,
        text="Launch Wind Tunnel",
        bg="#FF8C00",     # Orange theme
        fg="white",
        font=("Helvetica", 16, "bold"),
        command=open_wind_tunnel,
        borderless=1,
    )
    btn_wt.place(relx=0.5, rely=0.76, anchor="center", width=260, height=55)

    landing.mainloop()
