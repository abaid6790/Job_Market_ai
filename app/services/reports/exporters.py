"""
Generic report exporters — JSON, CSV, and PDF, all built from the same
plain dict produced by generator.py. Since every report type is just a
dict of scalars/lists/nested dicts, one generic flattener/renderer covers
all of them rather than needing a bespoke exporter per report type.
"""
import csv
import io
import json

from fpdf import FPDF

_UNICODE_REPLACEMENTS = {
    "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u2022": "-", "\u2026": "...",
}


def _sanitize_pdf_text(text) -> str:
    text = str(text)
    for unicode_char, replacement in _UNICODE_REPLACEMENTS.items():
        text = text.replace(unicode_char, replacement)
    # Core PDF fonts (Helvetica) only support latin-1 — anything left
    # outside that range is replaced rather than crashing the render.
    return text.encode("latin-1", "replace").decode("latin-1")


def to_json_bytes(data):
    return json.dumps(data, indent=2, default=str).encode("utf-8")


def _flatten_for_csv(data, prefix=""):
    rows = []
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_flatten_for_csv(value, full_key))
    elif isinstance(data, list):
        if not data:
            rows.append((prefix, ""))
        elif all(isinstance(item, dict) for item in data):
            for index, item in enumerate(data):
                rows.extend(_flatten_for_csv(item, f"{prefix}[{index}]"))
        else:
            rows.append((prefix, "; ".join(str(v) for v in data)))
    else:
        rows.append((prefix, "" if data is None else str(data)))
    return rows


def to_csv_bytes(data):
    rows = _flatten_for_csv(data)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Field", "Value"])
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _render_pdf_value(pdf, key, value, indent=0):
    # Cap indentation: deeply nested data would otherwise consume all the
    # available line width and make FPDF raise "Not enough horizontal
    # space to render a single character".
    indent = min(indent, 3)
    pad = "  " * indent
    key = _sanitize_pdf_text(key)
    if isinstance(value, dict):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, f"{pad}{key}:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for sub_key, sub_value in value.items():
            _render_pdf_value(pdf, sub_key, sub_value, indent + 1)
    elif isinstance(value, list):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, f"{pad}{key}:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        if not value:
            pdf.cell(0, 6, f"{pad}  (none)", new_x="LMARGIN", new_y="NEXT")
        elif all(isinstance(item, dict) for item in value):
            for index, item in enumerate(value, start=1):
                pdf.cell(0, 6, f"{pad}  {index}.", new_x="LMARGIN", new_y="NEXT")
                for sub_key, sub_value in item.items():
                    _render_pdf_value(pdf, sub_key, sub_value, indent + 2)
        else:
            safe_values = [_sanitize_pdf_text(v) for v in value]
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 6, f"{pad}  " + ", ".join(safe_values))
    else:
        pdf.set_font("Helvetica", "", 10)
        safe_value = _sanitize_pdf_text(value) if value is not None else ""
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 6, f"{pad}{key}: {safe_value}")


def to_pdf_bytes(data):
    pdf = FPDF()
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _sanitize_pdf_text(data.get("report_type", "Report")), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    for key, value in data.items():
        if key == "report_type":
            continue
        _render_pdf_value(pdf, key, value)
        pdf.ln(1)

    output = pdf.output()
    return bytes(output)


EXPORTERS = {
    "json": (to_json_bytes, "application/json", "json"),
    "csv": (to_csv_bytes, "text/csv", "csv"),
    "pdf": (to_pdf_bytes, "application/pdf", "pdf"),
}


def export(data, fmt):
    if fmt not in EXPORTERS:
        raise ValueError(f"Unsupported export format: {fmt}")
    exporter_fn, mimetype, extension = EXPORTERS[fmt]
    return exporter_fn(data), mimetype, extension
