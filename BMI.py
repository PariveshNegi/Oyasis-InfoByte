import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sqlite3
from datetime import datetime
import math
import os
import csv

# matplotlib embedding
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except Exception:
    PANDAS_AVAILABLE = False

DB_FILE = 'bmi_data.db'

# ------ Database utilities ------
class DB:
    def __init__(self, dbfile=DB_FILE):
        self.dbfile = dbfile
        self.conn = sqlite3.connect(self.dbfile)
        self.ensure_tables()

    def ensure_tables(self):
        c = self.conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                dob TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                weight REAL NOT NULL,
                height REAL NOT NULL,
                unit TEXT NOT NULL,
                bmi REAL NOT NULL,
                category TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        self.conn.commit()

    def add_user(self, name, dob=None):
        c = self.conn.cursor()
        try:
            c.execute('INSERT INTO users (name, dob) VALUES (?, ?)', (name, dob))
            self.conn.commit()
            return c.lastrowid
        except sqlite3.IntegrityError:
            return None

    def list_users(self):
        c = self.conn.cursor()
        c.execute('SELECT id, name, dob FROM users ORDER BY name COLLATE NOCASE')
        return c.fetchall()

    def get_user(self, user_id):
        c = self.conn.cursor()
        c.execute('SELECT id, name, dob FROM users WHERE id=?', (user_id,))
        return c.fetchone()

    def save_reading(self, user_id, weight, height, unit, bmi, category, notes=None):
        c = self.conn.cursor()
        ts = datetime.utcnow().isoformat()
        c.execute('''INSERT INTO readings (user_id, timestamp, weight, height, unit, bmi, category, notes)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (user_id, ts, weight, height, unit, bmi, category, notes))
        self.conn.commit()
        return c.lastrowid

    def get_readings(self, user_id):
        c = self.conn.cursor()
        c.execute('SELECT id, timestamp, weight, height, unit, bmi, category, notes FROM readings WHERE user_id=? ORDER BY timestamp', (user_id,))
        return c.fetchall()

    def close(self):
        self.conn.close()

# ------ BMI utilities ------

def calculate_bmi(weight, height, unit='metric'):
    """
    weight: kilograms or pounds
    height: centimeters or inches
    unit: 'metric' (kg, cm) or 'imperial' (lb, in)
    """
    if unit == 'metric':
        if height <= 0:
            raise ValueError('Height must be positive')
        h_m = height / 100.0
        bmi = weight / (h_m * h_m)
    else:
        # imperial: BMI = 703 * lb / in^2
        bmi = 703.0 * weight / (height * height)
    return round(bmi, 2)


def bmi_category(bmi):
    # WHO standard categories (simplified)
    if bmi < 18.5:
        return 'Underweight'
    elif bmi < 25.0:
        return 'Normal'
    elif bmi < 30.0:
        return 'Overweight'
    else:
        return 'Obese'

# ------ GUI application ------
class BMIApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Advanced BMI Tracker')
        self.geometry('1000x650')
        self.resizable(True, True)

        # Database
        try:
            self.db = DB()
        except Exception as e:
            messagebox.showerror('DB Error', f'Failed to open database: {e}')
            self.quit()
            return

        self.selected_user_id = None

        self.create_widgets()
        self.refresh_user_list()

    def create_widgets(self):
        # Top frame: User controls and input
        top = ttk.Frame(self, padding=8)
        top.pack(side='top', fill='x')

        # Left section: Add/select user
        user_frame = ttk.LabelFrame(top, text='Users', padding=8)
        user_frame.pack(side='left', fill='y', padx=(0,8))

        self.user_listbox = tk.Listbox(user_frame, width=24, height=6)
        self.user_listbox.pack(side='top', fill='y')
        self.user_listbox.bind('<<ListboxSelect>>', self.on_user_select)

        btns = ttk.Frame(user_frame)
        btns.pack(side='top', pady=6)
        ttk.Button(btns, text='Add', command=self.add_user_dialog).pack(side='left', padx=4)
        ttk.Button(btns, text='Rename', command=self.rename_user_dialog).pack(side='left', padx=4)
        ttk.Button(btns, text='Delete', command=self.delete_user).pack(side='left', padx=4)

        # Middle section: BMI input
        input_frame = ttk.LabelFrame(top, text='New Reading', padding=8)
        input_frame.pack(side='left', fill='both', expand=True)

        # Weight
        wrow = ttk.Frame(input_frame)
        wrow.pack(fill='x', pady=2)
        ttk.Label(wrow, text='Weight:').pack(side='left', padx=6)
        self.weight_var = tk.StringVar()
        ttk.Entry(wrow, textvariable=self.weight_var, width=10).pack(side='left')
        self.weight_unit = tk.StringVar(value='kg')
        ttk.Label(wrow, textvariable=self.weight_unit).pack(side='left', padx=6)

        # Height
        hrow = ttk.Frame(input_frame)
        hrow.pack(fill='x', pady=2)
        ttk.Label(hrow, text='Height:').pack(side='left', padx=6)
        self.height_var = tk.StringVar()
        ttk.Entry(hrow, textvariable=self.height_var, width=10).pack(side='left')
        self.height_unit = tk.StringVar(value='cm')
        ttk.Label(hrow, textvariable=self.height_unit).pack(side='left', padx=6)

        # Units switch
        unit_row = ttk.Frame(input_frame)
        unit_row.pack(fill='x', pady=6)
        ttk.Label(unit_row, text='Units:').pack(side='left', padx=6)
        self.unit_mode = tk.StringVar(value='metric')
        ttk.Radiobutton(unit_row, text='Metric (kg, cm)', variable=self.unit_mode, value='metric', command=self.on_unit_change).pack(side='left')
        ttk.Radiobutton(unit_row, text='Imperial (lb, in)', variable=self.unit_mode, value='imperial', command=self.on_unit_change).pack(side='left')

        # Notes
        notes_row = ttk.Frame(input_frame)
        notes_row.pack(fill='x', pady=2)
        ttk.Label(notes_row, text='Notes (optional):').pack(side='left', padx=6)
        self.notes_var = tk.StringVar()
        ttk.Entry(notes_row, textvariable=self.notes_var, width=40).pack(side='left')

        # Action buttons
        action_row = ttk.Frame(input_frame)
        action_row.pack(fill='x', pady=6)
        ttk.Button(action_row, text='Calculate BMI', command=self.calculate_action).pack(side='left', padx=6)
        ttk.Button(action_row, text='Save Reading', command=self.save_action).pack(side='left', padx=6)
        ttk.Button(action_row, text='Export History', command=self.export_history).pack(side='left', padx=6)

        # Result display
        result_frame = ttk.Frame(input_frame)
        result_frame.pack(fill='x', pady=6)
        self.result_text = tk.Text(result_frame, height=4, width=40, state='disabled')
        self.result_text.pack(side='left', padx=4)

        # Right section: History and charts
        right_frame = ttk.Frame(self, padding=8)
        right_frame.pack(side='top', fill='both', expand=True)

        # History Table
        history_frame = ttk.LabelFrame(right_frame, text='History', padding=8)
        history_frame.pack(side='left', fill='both', expand=True)

        self.history_tree = ttk.Treeview(history_frame, columns=('ts','weight','height','unit','bmi','cat','notes'), show='headings')
        for col, w in [('ts',160), ('weight',60), ('height',60), ('unit',50), ('bmi',50), ('cat',100), ('notes',200)]:
            self.history_tree.heading(col, text=col.title())
            self.history_tree.column(col, width=w, anchor='center')
        self.history_tree.pack(fill='both', expand=True)

        hist_btns = ttk.Frame(history_frame)
        hist_btns.pack(fill='x', pady=6)
        ttk.Button(hist_btns, text='Refresh', command=self.refresh_history).pack(side='left', padx=4)
        ttk.Button(hist_btns, text='Delete Selected', command=self.delete_selected_reading).pack(side='left', padx=4)

        # Chart and Stats
        chart_frame = ttk.LabelFrame(right_frame, text='Trend & Stats', padding=8)
        chart_frame.pack(side='left', fill='both', expand=True, padx=(8,0))

        # Matplotlib Figure
        self.figure = Figure(figsize=(5,4), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

        # Stats
        stats_frame = ttk.Frame(chart_frame)
        stats_frame.pack(fill='x', pady=6)
        self.stats_label = ttk.Label(stats_frame, text='No user selected')
        self.stats_label.pack(side='left')

    # ------ user management ------
    def refresh_user_list(self):
        self.user_listbox.delete(0, tk.END)
        users = self.db.list_users()
        self.users_map = {}
        for u in users:
            uid, name, dob = u
            display = f"{name}"
            self.users_map[display] = uid
            self.user_listbox.insert(tk.END, display)

    def on_user_select(self, event=None):
        sel = self.user_listbox.curselection()
        if not sel:
            return
        display = self.user_listbox.get(sel[0])
        self.selected_user_id = self.users_map.get(display)
        self.refresh_history()
        self.refresh_chart()

    def add_user_dialog(self):
        name = simpledialog.askstring('Add User', 'Full name:')
        if not name:
            return
        dob = simpledialog.askstring('Optional: DOB', 'Date of birth (YYYY-MM-DD) — optional:')
        uid = self.db.add_user(name.strip(), dob)
        if uid is None:
            messagebox.showwarning('Add User', 'User already exists or invalid name')
        else:
            self.refresh_user_list()

    def rename_user_dialog(self):
        if not self.selected_user_id:
            messagebox.showwarning('Rename', 'Select a user first')
            return
        user = self.db.get_user(self.selected_user_id)
        if not user:
            return
        newname = simpledialog.askstring('Rename User', 'New full name:', initialvalue=user[1])
        if not newname:
            return
        c = self.db.conn.cursor()
        try:
            c.execute('UPDATE users SET name=? WHERE id=?', (newname.strip(), self.selected_user_id))
            self.db.conn.commit()
            self.refresh_user_list()
        except Exception as e:
            messagebox.showerror('Rename', f'Failed to rename: {e}')

    def delete_user(self):
        if not self.selected_user_id:
            messagebox.showwarning('Delete', 'Select a user first')
            return
        if not messagebox.askyesno('Delete User', 'Delete user and their history? This cannot be undone.'):
            return
        c = self.db.conn.cursor()
        c.execute('DELETE FROM readings WHERE user_id=?', (self.selected_user_id,))
        c.execute('DELETE FROM users WHERE id=?', (self.selected_user_id,))
        self.db.conn.commit()
        self.selected_user_id = None
        self.refresh_user_list()
        self.history_tree.delete(*self.history_tree.get_children())
        self.ax.clear()
        self.canvas.draw()
        self.stats_label.config(text='No user selected')

    # ------ actions ------
    def on_unit_change(self):
        mode = self.unit_mode.get()
        if mode == 'metric':
            self.weight_unit.set('kg')
            self.height_unit.set('cm')
        else:
            self.weight_unit.set('lb')
            self.height_unit.set('in')

    def parse_float(self, s, name):
        try:
            v = float(s)
        except Exception:
            raise ValueError(f'{name} must be a number')
        if not math.isfinite(v):
            raise ValueError(f'{name} must be a finite number')
        return v

    def validate_inputs(self):
        if not self.selected_user_id:
            raise ValueError('Select or add a user first')
        w = self.parse_float(self.weight_var.get(), 'Weight')
        h = self.parse_float(self.height_var.get(), 'Height')
        mode = self.unit_mode.get()
        # Basic reasonable ranges
        if mode == 'metric':
            if not (20 <= w <= 500):
                raise ValueError('Weight (kg) must be between 20 and 500')
            if not (50 <= h <= 272):
                raise ValueError('Height (cm) must be between 50 and 272')
        else:
            if not (44 <= w <= 1100):
                raise ValueError('Weight (lb) must be between 44 and 1100')
            if not (20 <= h <= 107):
                raise ValueError('Height (in) must be between 20 and 107')
        return w, h, mode

    def calculate_action(self):
        try:
            w, h, mode = self.validate_inputs()
        except ValueError as e:
            messagebox.showerror('Input error', str(e))
            return
        try:
            bmi = calculate_bmi(w, h, unit=mode)
        except Exception as e:
            messagebox.showerror('Calculation error', str(e))
            return
        cat = bmi_category(bmi)
        self.show_result(bmi, cat)

    def show_result(self, bmi, category):
        txt = f'BMI: {bmi}\nCategory: {category}\n'
        if category == 'Underweight':
            txt += 'Advice: Consider a nutritious calorie-rich diet and consult a doctor if necessary.'
        elif category == 'Normal':
            txt += 'Advice: Maintain your current lifestyle. Keep active and balanced diet.'
        elif category == 'Overweight':
            txt += 'Advice: Consider regular exercise, reduce calorie intake, consult healthcare professional.'
        else:
            txt += 'Advice: Strongly consider consulting a healthcare professional; focus on medically supervised plan.'
        self.result_text.config(state='normal')
        self.result_text.delete('1.0', tk.END)
        self.result_text.insert(tk.END, txt)
        self.result_text.config(state='disabled')
        # store last calculation so user can save
        self._last_calculation = (bmi, category)

    def save_action(self):
        if not hasattr(self, '_last_calculation'):
            messagebox.showwarning('Save', 'Calculate BMI before saving')
            return
        bmi, category = self._last_calculation
        try:
            w = float(self.weight_var.get())
            h = float(self.height_var.get())
        except Exception:
            messagebox.showerror('Save error', 'Invalid current inputs')
            return
        mode = self.unit_mode.get()
        notes = self.notes_var.get().strip() or None
        try:
            rid = self.db.save_reading(self.selected_user_id, w, h, mode, bmi, category, notes)
            messagebox.showinfo('Saved', f'Reading saved (id {rid})')
            self.refresh_history()
            self.refresh_chart()
        except Exception as e:
            messagebox.showerror('DB error', str(e))

    def refresh_history(self):
        for r in self.history_tree.get_children():
            self.history_tree.delete(r)
        if not self.selected_user_id:
            return
        readings = self.db.get_readings(self.selected_user_id)
        for rec in readings:
            rid, ts, weight, height, unit, bmi, cat, notes = rec
            # format timestamp for readability
            try:
                tdisplay = datetime.fromisoformat(ts).strftime('%Y-%m-%d %H:%M')
            except Exception:
                tdisplay = ts
            self.history_tree.insert('', 'end', iid=str(rid), values=(tdisplay, weight, height, unit, bmi, cat, notes or ''))

    def delete_selected_reading(self):
        sel = self.history_tree.selection()
        if not sel:
            messagebox.showwarning('Delete', 'Select a reading first')
            return
        if not messagebox.askyesno('Delete', 'Delete selected reading(s)?'):
            return
        c = self.db.conn.cursor()
        for iid in sel:
            try:
                c.execute('DELETE FROM readings WHERE id=?', (int(iid),))
            except Exception:
                pass
        self.db.conn.commit()
        self.refresh_history()
        self.refresh_chart()

    def refresh_chart(self):
        self.ax.clear()
        if not self.selected_user_id:
            self.canvas.draw()
            self.stats_label.config(text='No user selected')
            return
        readings = self.db.get_readings(self.selected_user_id)
        if not readings:
            self.canvas.draw()
            self.stats_label.config(text='No readings')
            return
        dates = []
        bmis = []
        for rec in readings:
            _id, ts, weight, height, unit, bmi, cat, notes = rec
            try:
                dt = datetime.fromisoformat(ts)
            except Exception:
                dt = datetime.utcnow()
            dates.append(dt)
            bmis.append(bmi)

        # plot
        self.ax.plot(dates, bmis, marker='o')
        self.ax.set_title('BMI over Time')
        self.ax.set_xlabel('Date')
        self.ax.set_ylabel('BMI')
        self.ax.grid(True)
        self.figure.autofmt_xdate()

        # stats
        try:
            mean_bmi = sum(bmis) / len(bmis)
            min_bmi = min(bmis)
            max_bmi = max(bmis)
            last_bmi = bmis[-1]
            stats = f'Mean: {mean_bmi:.2f}  Min: {min_bmi:.2f}  Max: {max_bmi:.2f}  Last: {last_bmi:.2f}'
        except Exception:
            stats = 'Unable to compute stats'
        self.stats_label.config(text=stats)

        self.canvas.draw()

    def export_history(self):
        if not self.selected_user_id:
            messagebox.showwarning('Export', 'Select a user first')
            return
        readings = self.db.get_readings(self.selected_user_id)
        if not readings:
            messagebox.showwarning('Export', 'No readings to export')
            return
        fname = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV files','*.csv'), ('All files','*.*')])
        if not fname:
            return
        headers = ['id','timestamp','weight','height','unit','bmi','category','notes']
        try:
            if PANDAS_AVAILABLE:
                df = pd.DataFrame(readings, columns=headers)
                df.to_csv(fname, index=False)
            else:
                with open(fname, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    for row in readings:
                        writer.writerow(row)
            messagebox.showinfo('Export', f'Exported {len(readings)} rows to {fname}')
        except Exception as e:
            messagebox.showerror('Export error', str(e))

    def on_closing(self):
        try:
            self.db.close()
        except Exception:
            pass
        self.destroy()


if __name__ == '__main__':
    app = BMIApp()
    app.protocol('WM_DELETE_WINDOW', app.on_closing)
    app.mainloop()
