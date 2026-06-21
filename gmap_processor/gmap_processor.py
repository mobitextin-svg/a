"""
Google Maps Extractor -> Formatted Output (GUI)
================================================

Reads Google Maps Extractor export files (tab/comma separated .csv/.tsv or .xlsx)
and produces a cleaned, re-ordered output file with the following columns:

    Category | query | Mobile | name | website | phone_international |
    main_category | Education Type | address | Pincode | District | State |
    query | CPF

Two reference workbooks are used purely for look-ups (they are NEVER written
to or deleted):

    * "Keyword Type.xlsx"  -> maps the search `query` to a "Category"
    * "Category.xlsx"      -> maps `main_category` to an "Education Type"

CPF = "Currently Process File name" (the source file each row came from).

The tool is pure standard-library for the GUI (tkinter) and uses pandas +
openpyxl for the data work.

    pip install pandas openpyxl
"""

import os
import re
import sys
import threading
import traceback
import queue

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import pandas as pd
except ImportError:  # pragma: no cover - friendly message at startup
    pd = None


# --------------------------------------------------------------------------- #
#  Defaults (the reference files supplied by the user)                         #
# --------------------------------------------------------------------------- #
DEFAULT_KEYWORD_TYPE = r"G:\Down Gmap\Google Maps Extractor\I\Keyword  Type.xlsx"
DEFAULT_CATEGORY = r"G:\Down Gmap\Google Maps Extractor\I\Category.xlsx"

# Output column order requested by the user.  ("query" intentionally appears
# twice in the spec, so the second one is emitted as "query.1" by pandas but
# renamed back to "query" on write.)
OUTPUT_COLUMNS = [
    "Category",
    "query",
    "Mobile",
    "name",
    "website",
    "phone_international",
    "main_category",
    "Education Type",
    "address",
    "Pincode",
    "District",
    "State",
    "query2",   # second "query" column (renamed on save)
    "CPF",
]

# Indian States / Union Territories used to detect the State from an address.
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "West Bengal",
    # Union Territories
    "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir",
    "Ladakh", "Lakshadweep", "Puducherry",
]


# --------------------------------------------------------------------------- #
#  Data helpers                                                               #
# --------------------------------------------------------------------------- #
def read_table(path):
    """Read a csv/tsv/xlsx file into a DataFrame, auto-detecting the delimiter."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path, dtype=str)
    # Let pandas sniff the separator (handles both tab and comma exports).
    return pd.read_csv(
        path,
        sep=None,
        engine="python",
        dtype=str,
        on_bad_lines="skip",
        encoding="utf-8-sig",
    )


def load_lookup(path, log):
    """
    Build a {key -> value} dict from a 2+ column reference workbook.

    First column is the key, the last column is the value.  Matching is done
    case-insensitively and with surrounding whitespace stripped.
    """
    lookup = {}
    if not path or not os.path.isfile(path):
        log(f"  ! reference not found, skipping: {path}")
        return lookup
    try:
        df = read_table(path)
    except Exception as exc:
        log(f"  ! could not read reference '{os.path.basename(path)}': {exc}")
        return lookup

    df = df.dropna(how="all")
    if df.shape[1] < 2:
        log(f"  ! reference '{os.path.basename(path)}' needs >=2 columns")
        return lookup

    key_col, val_col = df.columns[0], df.columns[-1]
    for _, row in df.iterrows():
        key = str(row[key_col]).strip().lower()
        val = "" if pd.isna(row[val_col]) else str(row[val_col]).strip()
        if key and key != "nan":
            lookup[key] = val
    log(f"  loaded {len(lookup)} entries from '{os.path.basename(path)}'")
    return lookup


def lookup_value(lookup, key):
    """Look up `key` in the dict: exact match first, then a 'contains' fallback."""
    if not key:
        return ""
    k = str(key).strip().lower()
    if k in lookup:
        return lookup[k]
    # Fallback: any reference key contained in the value (or vice-versa).
    for ref_key, ref_val in lookup.items():
        if ref_key and (ref_key in k or k in ref_key):
            return ref_val
    return ""


def extract_mobile(*phones):
    """Return a clean national mobile number (last 10 digits) from any phone field."""
    for phone in phones:
        if not phone or str(phone).lower() == "nan":
            continue
        digits = re.sub(r"\D", "", str(phone))
        if len(digits) >= 10:
            return digits[-10:]
    return ""


def extract_pincode(*texts):
    """Find a 6-digit Indian PIN code in any of the provided text fields."""
    for text in texts:
        if not text or str(text).lower() == "nan":
            continue
        m = re.search(r"\b(\d{6})\b", str(text))
        if m:
            return m.group(1)
    return ""


def extract_state(*texts):
    """Match a known Indian state/UT inside the given text fields."""
    for text in texts:
        if not text or str(text).lower() == "nan":
            continue
        low = str(text).lower()
        for state in INDIAN_STATES:
            if state.lower() in low:
                return state
    return ""


def extract_district(address, state, pincode):
    """
    Best-effort district extraction.

    Indian addresses are usually:  "..., District, State PIN, Country".
    We split on commas and pick the part that sits just before the State/PIN.
    """
    if not address or str(address).lower() == "nan":
        return ""
    parts = [p.strip() for p in str(address).split(",") if p.strip()]
    if not parts:
        return ""

    # Find the segment that contains the state or the pincode.
    anchor = None
    for i, part in enumerate(parts):
        low = part.lower()
        if (state and state.lower() in low) or (pincode and pincode in part):
            anchor = i
            break
    if anchor is None:
        anchor = len(parts) - 1  # assume last useful chunk

    # District is generally the chunk immediately before the state/pin anchor.
    idx = anchor - 1
    while idx >= 0:
        cand = parts[idx].strip()
        # Skip pure pincodes or country names.
        if cand and not re.fullmatch(r"\d{6}", cand) and cand.lower() != "india":
            return cand
        idx -= 1
    return ""


def get(row, *names):
    """Return the first non-empty value among the given column names of a row."""
    for name in names:
        if name in row.index:
            val = row[name]
            if pd.notna(val) and str(val).strip() and str(val).lower() != "nan":
                return str(val).strip()
    return ""


def process_file(path, kw_lookup, cat_lookup, log):
    """Transform one source file into a list of output-row dicts."""
    df = read_table(path)
    df.columns = [str(c).strip() for c in df.columns]
    cpf = os.path.basename(path)

    rows = []
    for _, row in df.iterrows():
        query = get(row, "query")
        main_category = get(row, "main_category")
        address = get(row, "address")
        detailed = get(row, "detailed_address")

        pincode = extract_pincode(address, detailed)
        state = extract_state(address, detailed)
        district = extract_district(address, state, pincode)

        rows.append({
            "Category": lookup_value(kw_lookup, query),
            "query": query,
            "Mobile": extract_mobile(
                get(row, "phone_international"), get(row, "phone")
            ),
            "name": get(row, "name"),
            "website": get(row, "website"),
            "phone_international": get(row, "phone_international"),
            "main_category": main_category,
            "Education Type": lookup_value(cat_lookup, main_category),
            "address": address,
            "Pincode": pincode,
            "District": district,
            "State": state,
            "query2": query,
            "CPF": cpf,
        })
    log(f"  {cpf}: {len(rows)} rows")
    return rows


# --------------------------------------------------------------------------- #
#  GUI                                                                        #
# --------------------------------------------------------------------------- #
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Google Maps Extractor — Output Formatter")
        self.geometry("780x620")
        self.minsize(700, 560)

        self.input_files = []
        self.log_q = queue.Queue()

        self._build_ui()
        self.after(100, self._drain_log)

    # -- UI construction --------------------------------------------------- #
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        # Input selection
        in_box = ttk.LabelFrame(frm, text="1. Input files (Google Maps Extractor exports)")
        in_box.pack(fill="x", **pad)
        btns = ttk.Frame(in_box)
        btns.pack(fill="x", padx=6, pady=6)
        ttk.Button(btns, text="Add Files…", command=self.add_files).pack(side="left")
        ttk.Button(btns, text="Add Folder…", command=self.add_folder).pack(side="left", padx=6)
        ttk.Button(btns, text="Clear", command=self.clear_files).pack(side="left")
        self.files_list = tk.Listbox(in_box, height=6)
        self.files_list.pack(fill="x", padx=6, pady=(0, 6))

        # Reference files
        ref_box = ttk.LabelFrame(frm, text="2. Reference files (read-only — never modified)")
        ref_box.pack(fill="x", **pad)

        self.kw_var = tk.StringVar(value=DEFAULT_KEYWORD_TYPE)
        self.cat_var = tk.StringVar(value=DEFAULT_CATEGORY)
        self._ref_row(ref_box, "Keyword Type → Category:", self.kw_var)
        self._ref_row(ref_box, "Category → Education Type:", self.cat_var)

        # Output
        out_box = ttk.LabelFrame(frm, text="3. Output")
        out_box.pack(fill="x", **pad)
        self.out_var = tk.StringVar(value=os.path.join(os.getcwd(), "output.xlsx"))
        orow = ttk.Frame(out_box)
        orow.pack(fill="x", padx=6, pady=6)
        ttk.Label(orow, text="Save to:", width=22).pack(side="left")
        ttk.Entry(orow, textvariable=self.out_var).pack(side="left", fill="x", expand=True)
        ttk.Button(orow, text="Browse…", command=self.choose_output).pack(side="left", padx=6)

        self.combine_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            out_box,
            text="Combine all input files into one output file (uncheck = one output per input)",
            variable=self.combine_var,
        ).pack(anchor="w", padx=6, pady=(0, 6))

        # Run
        run_row = ttk.Frame(frm)
        run_row.pack(fill="x", **pad)
        self.run_btn = ttk.Button(run_row, text="▶  Process", command=self.run)
        self.run_btn.pack(side="left")
        self.progress = ttk.Progressbar(run_row, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=10)

        # Log
        log_box = ttk.LabelFrame(frm, text="Log")
        log_box.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(log_box, height=10, wrap="word", state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        sb = ttk.Scrollbar(log_box, command=self.log_text.yview)
        sb.pack(side="right", fill="y", pady=6)
        self.log_text.configure(yscrollcommand=sb.set)

    def _ref_row(self, parent, label, var):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=6, pady=4)
        ttk.Label(row, text=label, width=24).pack(side="left")
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
        ttk.Button(
            row, text="Browse…",
            command=lambda: self._browse_ref(var),
        ).pack(side="left", padx=6)

    # -- actions ----------------------------------------------------------- #
    def _browse_ref(self, var):
        p = filedialog.askopenfilename(
            title="Select reference workbook",
            filetypes=[("Excel/CSV", "*.xlsx *.xls *.csv *.tsv"), ("All", "*.*")],
        )
        if p:
            var.set(p)

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select Google Maps Extractor files",
            filetypes=[("Data files", "*.csv *.tsv *.xlsx *.xls *.txt"), ("All", "*.*")],
        )
        for p in paths:
            if p not in self.input_files:
                self.input_files.append(p)
        self._refresh_files()

    def add_folder(self):
        folder = filedialog.askdirectory(title="Select a folder of export files")
        if not folder:
            return
        for fn in sorted(os.listdir(folder)):
            if fn.lower().endswith((".csv", ".tsv", ".xlsx", ".xls", ".txt")):
                p = os.path.join(folder, fn)
                if p not in self.input_files:
                    self.input_files.append(p)
        self._refresh_files()

    def clear_files(self):
        self.input_files = []
        self._refresh_files()

    def _refresh_files(self):
        self.files_list.delete(0, tk.END)
        for p in self.input_files:
            self.files_list.insert(tk.END, p)

    def choose_output(self):
        if self.combine_var.get():
            p = filedialog.asksaveasfilename(
                title="Save combined output",
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")],
            )
        else:
            p = filedialog.askdirectory(title="Select output folder")
        if p:
            self.out_var.set(p)

    def log(self, msg):
        self.log_q.put(msg)

    def _drain_log(self):
        while not self.log_q.empty():
            msg = self.log_q.get()
            self.log_text.configure(state="normal")
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state="disabled")
        self.after(100, self._drain_log)

    def run(self):
        if pd is None:
            messagebox.showerror(
                "Missing dependency",
                "pandas is required.\n\nInstall it with:\n    pip install pandas openpyxl",
            )
            return
        if not self.input_files:
            messagebox.showwarning("No input", "Add at least one input file.")
            return
        self.run_btn.configure(state="disabled")
        self.progress.configure(value=0, maximum=len(self.input_files))
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()

    # -- worker thread ----------------------------------------------------- #
    def _worker(self):
        try:
            self.log("Loading reference files…")
            kw_lookup = load_lookup(self.kw_var.get(), self.log)
            cat_lookup = load_lookup(self.cat_var.get(), self.log)

            combine = self.combine_var.get()
            out_path = self.out_var.get()
            all_rows = []

            for i, path in enumerate(self.input_files, 1):
                self.log(f"Processing [{i}/{len(self.input_files)}] {os.path.basename(path)}")
                try:
                    rows = process_file(path, kw_lookup, cat_lookup, self.log)
                except Exception as exc:
                    self.log(f"  ! error: {exc}")
                    rows = []
                if combine:
                    all_rows.extend(rows)
                else:
                    self._save(rows, self._per_file_out(out_path, path))
                self.progress.configure(value=i)

            if combine:
                self._save(all_rows, out_path)

            self.log("✔ Done.")
            self.after(0, lambda: messagebox.showinfo("Done", "Processing complete."))
        except Exception:
            err = traceback.format_exc()
            self.log("! FATAL:\n" + err)
            self.after(0, lambda: messagebox.showerror("Error", err))
        finally:
            self.after(0, lambda: self.run_btn.configure(state="normal"))

    def _per_file_out(self, out_dir, src):
        base = os.path.splitext(os.path.basename(src))[0]
        folder = out_dir if os.path.isdir(out_dir) else os.path.dirname(out_dir) or "."
        return os.path.join(folder, base + "_formatted.xlsx")

    def _save(self, rows, out_path):
        df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
        # Rename the second query column back to "query" for the final file.
        df = df.rename(columns={"query2": "query"})
        if out_path.lower().endswith(".csv"):
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
        else:
            if not out_path.lower().endswith((".xlsx", ".xls")):
                out_path += ".xlsx"
            df.to_excel(out_path, index=False)
        self.log(f"  saved {len(df)} rows -> {out_path}")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
