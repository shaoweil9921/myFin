# IBD 50 Extraction

Pure Python/PyMuPDF extraction of IBD 50 stock lists from eIBD PDF magazines. No OpenAI API needed.

## Requirements

```
pip install pymupdf
```

## Usage

```bash
python extract_ibd50.py <input.pdf> <output_basename>
```

**Example:**
```bash
python extract_ibd50.py "C:\DolphinShare\IBD\2026\Raw\eIBD_082426.pdf" "C:\DolphinShare\IBD\2026\Processed\eIBD_082426"
```

**Output:** `<output_basename>.csv` with columns: `Rank, Symbol, Company, Price, ShortNote, Description`

## Algorithm (v26)

Each B-page has two regions:
- **LEFT table (x < 300):** Complete row data — rank marker + company + price + metrics + description
- **RIGHT tiles (x >= 300):** Symbol headers + short notes in a 3-column grid

1. Extract rank marker y-positions from word-level data
2. Parse LEFT table blocks by y-proximity to rank markers
3. Match symbols via index-based lookup: row index i → column = i % 3, tile position = i // 3
4. Fall back to tile-proximity matching if LEFT parsing yields < expected count

## Notes

- B1 = ranks 1-15, B3 = ranks 16-30, B4 = ranks 31-50
- Some ranks 16-50 may fall through to fallback matching and have incorrect symbols
- Short notes are optional — descriptions are always extracted
