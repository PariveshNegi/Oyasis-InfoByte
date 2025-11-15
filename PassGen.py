import tkinter as tk
from tkinter import ttk, messagebox
import secrets
import string
import math


class PasswordGeneratorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Advanced Password Generator")
        self.geometry("760x520")
        self.resizable(False, False)

        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        # Left: options
        left = ttk.Frame(frm)
        left.grid(row=0, column=0, sticky="nw", padx=(0, 12))

        ttk.Label(left, text="Password Options", font=(None, 14, 'bold')).grid(row=0, column=0, pady=(0, 8), sticky='w')

        # Length
        length_row = ttk.Frame(left)
        length_row.grid(row=1, column=0, sticky='w', pady=6)
        ttk.Label(length_row, text="Length:").pack(side=tk.LEFT)
        self.length_var = tk.IntVar(value=16)
        self.length_spin = ttk.Spinbox(length_row, from_=4, to=256, textvariable=self.length_var, width=6)
        self.length_spin.pack(side=tk.LEFT, padx=(6, 0))

        # Character sets
        ttk.Label(left, text="Include character types:").grid(row=2, column=0, sticky='w')
        self.include_upper = tk.BooleanVar(value=True)
        self.include_lower = tk.BooleanVar(value=True)
        self.include_digits = tk.BooleanVar(value=True)
        self.include_symbols = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Uppercase (A-Z)", variable=self.include_upper).grid(row=3, column=0, sticky='w')
        ttk.Checkbutton(left, text="Lowercase (a-z)", variable=self.include_lower).grid(row=4, column=0, sticky='w')
        ttk.Checkbutton(left, text="Digits (0-9)", variable=self.include_digits).grid(row=5, column=0, sticky='w')
        ttk.Checkbutton(left, text="Symbols (!@#$...)", variable=self.include_symbols).grid(row=6, column=0, sticky='w')

        # Exclude ambiguous characters
        self.exclude_ambiguous = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Exclude ambiguous (O,0,l,1,etc.)", variable=self.exclude_ambiguous).grid(row=7, column=0, sticky='w', pady=(6,0))

        # Custom exclusions
        ttk.Label(left, text="Exclude specific characters:").grid(row=8, column=0, sticky='w', pady=(8,0))
        self.exclude_entry = ttk.Entry(left, width=24)
        self.exclude_entry.grid(row=9, column=0, sticky='w')
        ttk.Label(left, text="(e.g. \"<>/\\'\" )").grid(row=10, column=0, sticky='w')

        # Number of passwords to generate
        gen_row = ttk.Frame(left)
        gen_row.grid(row=11, column=0, sticky='w', pady=(10,0))
        ttk.Label(gen_row, text="Count:").pack(side=tk.LEFT)
        self.count_var = tk.IntVar(value=1)
        self.count_spin = ttk.Spinbox(gen_row, from_=1, to=100, textvariable=self.count_var, width=6)
        self.count_spin.pack(side=tk.LEFT, padx=(6,0))

        # Buttons
        btn_row = ttk.Frame(left)
        btn_row.grid(row=12, column=0, sticky='w', pady=(12,0))
        ttk.Button(btn_row, text="Generate", command=self.generate_passwords).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Clear", command=self.clear_results).pack(side=tk.LEFT, padx=(6,0))

        # Clipboard and Save
        action_row = ttk.Frame(left)
        action_row.grid(row=13, column=0, sticky='w', pady=(12,0))
        ttk.Button(action_row, text="Copy Selected", command=self.copy_selected).pack(side=tk.LEFT)
        ttk.Button(action_row, text="Copy All", command=self.copy_all).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(action_row, text="Save", command=self.save_to_file).pack(side=tk.LEFT, padx=(6,0))

        # Right: results and strength
        right = ttk.Frame(frm)
        right.grid(row=0, column=1, sticky='nsew')
        frm.columnconfigure(1, weight=1)

        ttk.Label(right, text="Generated Passwords", font=(None, 14, 'bold')).grid(row=0, column=0, sticky='w')

        self.results_list = tk.Listbox(right, height=12, font=("Courier", 11))
        self.results_list.grid(row=1, column=0, sticky='nsew', pady=(6,0))
        right.rowconfigure(1, weight=1)

        # strength and details
        detail_frame = ttk.Frame(right)
        detail_frame.grid(row=2, column=0, sticky='ew', pady=(10,0))
        ttk.Label(detail_frame, text="Password details:").grid(row=0, column=0, sticky='w')
        self.details_text = tk.Text(detail_frame, height=6, width=48, state='disabled', wrap='word')
        self.details_text.grid(row=1, column=0, sticky='ew')

        # Bind double click to copy
        self.results_list.bind('<Double-Button-1>', self._on_double_click_copy)

        # Footer: quick tips
        footer = ttk.Label(self, text="Tips: Use length >=12 and mix character types. Excluding ambiguous chars helps readability.")
        footer.pack(side=tk.BOTTOM, fill=tk.X, pady=(6,8))

    def _charset_from_options(self):
        parts = {}
        if self.include_upper.get():
            parts['upper'] = string.ascii_uppercase
        if self.include_lower.get():
            parts['lower'] = string.ascii_lowercase
        if self.include_digits.get():
            parts['digits'] = string.digits
        if self.include_symbols.get():
            # a cautious symbolic set (you can expand)
            parts['symbols'] = "!@#$%^&*()-_=+[]{};:,.<>?/|~"

        # exclude ambiguous
        if self.exclude_ambiguous.get():
            ambiguous = "O0oIl1`\"'"
            # remove common ambiguous characters
            for k in list(parts.keys()):
                parts[k] = ''.join(ch for ch in parts[k] if ch not in 'O0oIl1')

        # remove user exclusions
        exclude_manual = ''.join(self.exclude_entry.get().split())
        if exclude_manual:
            for k in list(parts.keys()):
                parts[k] = ''.join(ch for ch in parts[k] if ch not in exclude_manual)

        # remove empty sets
        parts = {k: v for k, v in parts.items() if v}
        return parts

    def generate_passwords(self):
        try:
            length = int(self.length_var.get())
            if length <= 0:
                raise ValueError()
        except Exception:
            messagebox.showerror("Invalid length", "Please enter a valid positive integer for length.")
            return

        parts = self._charset_from_options()
        if not parts:
            messagebox.showerror("No character types", "Select at least one character type (uppercase/lowercase/digits/symbols).")
            return

        count = int(self.count_var.get())
        if count <= 0 or count > 1000:
            messagebox.showerror("Invalid count", "Please pick a count between 1 and 1000.")
            return

        # security rule: ensure at least one of each selected type
        types_selected = list(parts.keys())
        if length < len(types_selected):
            messagebox.showwarning("Length too small", f"Length is smaller than number of selected character types ({len(types_selected)}). Some types may not appear.")

        charset = ''.join(parts.values())
        # entropy estimate
        entropy = length * math.log2(len(charset)) if charset else 0

        passwords = []
        for _ in range(count):
            # build password by ensuring at least one char from each selected set
            pwd_chars = []
            # choose one from each selected type first
            for setchars in parts.values():
                if setchars:
                    pwd_chars.append(secrets.choice(setchars))
            # fill the rest
            while len(pwd_chars) < length:
                pwd_chars.append(secrets.choice(charset))
            # shuffle to avoid predictable placements
            secrets.SystemRandom().shuffle(pwd_chars)
            pwd = ''.join(pwd_chars[:length])
            passwords.append(pwd)

        # update UI
        self.results_list.delete(0, tk.END)
        for p in passwords:
            self.results_list.insert(tk.END, p)

        # details
        self._show_details(parts, length, entropy)

    def _show_details(self, parts, length, entropy):
        # calculate estimated strength
        strength_label, advice = self._entropy_to_strength(entropy)
        charset_summary = ', '.join(f"{k}({len(v)})" for k, v in parts.items())
        details = (
            f"Length: {length}\n"
            f"Character sets: {charset_summary or 'None'}\n"
            f"Entropy (bits): {entropy:.1f}\n"
            f"Strength: {strength_label}\n\n"
            f"Advice: {advice}\n"
        )
        self.details_text.config(state='normal')
        self.details_text.delete('1.0', tk.END)
        self.details_text.insert(tk.END, details)
        self.details_text.config(state='disabled')

    def _entropy_to_strength(self, entropy_bits):
        # rough thresholds
        if entropy_bits < 28:
            return "Very Weak", "Do not use this password for anything important."
        if entropy_bits < 36:
            return "Weak", "Use for unimportant temporary accounts only."
        if entropy_bits < 60:
            return "Moderate", "Good for many accounts, but consider increasing length."
        if entropy_bits < 80:
            return "Strong", "Strong password for most purposes."
        return "Very Strong", "Excellent entropy; suitable for highly sensitive accounts."

    def clear_results(self):
        self.results_list.delete(0, tk.END)
        self.details_text.config(state='normal')
        self.details_text.delete('1.0', tk.END)
        self.details_text.config(state='disabled')

    def copy_selected(self):
        sel = self.results_list.curselection()
        if not sel:
            messagebox.showinfo("Copy selected", "No password selected. Double-click a password to copy it, or select and click Copy Selected.")
            return
        pwd = self.results_list.get(sel[0])
        self._copy_to_clipboard(pwd)
        messagebox.showinfo("Copied", "Selected password copied to clipboard.")

    def copy_all(self):
        all_pwds = '\n'.join(self.results_list.get(0, tk.END))
        if not all_pwds:
            messagebox.showinfo("Copy all", "No generated passwords to copy.")
            return
        self._copy_to_clipboard(all_pwds)
        messagebox.showinfo("Copied", "All generated passwords copied to clipboard.")

    def _on_double_click_copy(self, event):
        idx = self.results_list.curselection()
        if not idx:
            return
        pwd = self.results_list.get(idx[0])
        self._copy_to_clipboard(pwd)
        # small non-blocking feedback
        self.bell()

    def _copy_to_clipboard(self, text):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            # also set selection for middle-click paste on X11
            try:
                self.update()  # now it stays on clipboard
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Clipboard error", f"Failed to copy to clipboard: {e}")

    def save_to_file(self):
        import datetime
        items = self.results_list.get(0, tk.END)
        if not items:
            messagebox.showinfo("Save", "No passwords to save.")
            return
        filename = f"passwords_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                for p in items:
                    f.write(p + '\n')
            messagebox.showinfo("Saved", f"Passwords saved to {filename}")
        except Exception as e:
            messagebox.showerror("Save error", f"Could not save file: {e}")


if __name__ == '__main__':
    app = PasswordGeneratorApp()
    app.mainloop()
