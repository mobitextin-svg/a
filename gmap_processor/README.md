# Google Maps Extractor — Output Formatter (GUI)

A small Windows desktop tool that turns raw **Google Maps Extractor** export
files into a clean, re-ordered spreadsheet.

## Output columns

| Column | Source |
|---|---|
| **Category** | looked up from `Keyword Type.xlsx` using `query` |
| query | from input |
| **Mobile** | last 10 digits of `phone_international` / `phone` |
| name | from input |
| website | from input |
| phone_international | from input |
| main_category | from input |
| **Education Type** | looked up from `Category.xlsx` using `main_category` |
| address | from input |
| **Pincode** | 6-digit PIN parsed from the address |
| **District** | parsed from the address (segment before State/PIN) |
| **State** | matched against the list of Indian states/UTs |
| query | from input (second copy, as in the spec) |
| **CPF** | *Currently Process File* — the source file name |

## Reference files (read-only)

The two reference workbooks are **only read** — they are never edited,
overwritten, or deleted:

* `G:\Down Gmap\Google Maps Extractor\I\Keyword  Type.xlsx`
  → first column = keyword/query, last column = **Category**
* `G:\Down Gmap\Google Maps Extractor\I\Category.xlsx`
  → first column = main_category, last column = **Education Type**

Both paths are pre-filled in the GUI and can be changed with *Browse…*.
Look-ups are case-insensitive with a "contains" fallback.

## Running

Double-click **START.bat** (installs dependencies on first run), or:

```
pip install -r requirements.txt
python gmap_processor.py
```

## How to use

1. **Add Files…** or **Add Folder…** of the extractor exports
   (`.csv`, `.tsv`, `.xlsx`, `.txt` — delimiter is auto-detected).
2. Confirm the two reference file paths.
3. Pick an output file (or folder, if combining is off).
4. Click **▶ Process**.

By default every input file is combined into one output workbook, with the
`CPF` column showing which source file each row came from.
