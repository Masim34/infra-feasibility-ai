import io
import json
from datetime import datetime
from typing import Any, Dict, List
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def _safe_iso(dt) -> str | None:
    if not dt:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


def _summary_from_full_report(full_report: Dict[str, Any]) -> Dict[str, Any]:
    if not full_report:
        return {}
    summary_section = full_report.get("summary") or full_report.get("executive_summary") or {}
    return {
        "recommendation": summary_section.get("recommendation") or summary_section.get("headline"),
        "key_numbers": summary_section.get("key_numbers") or {},
    }


def export_analysis_json(analysis) -> bytes:
    payload: Dict[str, Any] = {
        "analysis": {
            "id": analysis.id,
            "project_id": analysis.project_id,
            "user_id": analysis.user_id,
            "status": analysis.status,
            "error_message": analysis.error_message,
            "created_at": _safe_iso(analysis.created_at),
            "completed_at": _safe_iso(analysis.completed_at),
            "processing_time_seconds": analysis.processing_time_seconds,
        },
        "project": {
            "name": getattr(analysis.project, "name", None),
            "country": getattr(analysis.project, "country", None),
            "technology": getattr(analysis.project, "technology", None),
            "capacity_mw": getattr(analysis.project, "capacity_mw", None),
            "location_lat": getattr(analysis.project, "location_lat", None),
            "location_lon": getattr(analysis.project, "location_lon", None),
        },
        "inputs": {"parameters": analysis.parameters or {}},
        "financials": analysis.financial_results or {},
        "energy": analysis.energy_results or {},
        "risk": analysis.risk_results or {},
        "scenarios": analysis.scenarios_results or {},
        "sensitivity": analysis.sensitivity_results or {},
        "monte_carlo": analysis.monte_carlo_results or {},
        "country_risk_score": analysis.country_risk_score,
        "country_risk_grade": analysis.country_risk_grade,
        "risk_adjusted_discount_rate": analysis.risk_adjusted_discount_rate,
        "narrative_report": analysis.narrative_report,
        "full_report": analysis.full_report or {},
        "summary": _summary_from_full_report(analysis.full_report or {}),
    }
    return json.dumps(payload, indent=2, default=str).encode("utf-8")


def _pdf_write_multiline(pdf: canvas.Canvas, text: str, x: float, y_start: float, line_height: float, max_width: int) -> float:
    if not text:
        return y_start
    lines: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        while len(line) > max_width:
            split_pos = line.rfind(" ", 0, max_width)
            if split_pos <= 0:
                split_pos = max_width
            lines.append(line[:split_pos])
            line = line[split_pos:].lstrip()
        lines.append(line)
    y = y_start
    for ln in lines:
        if y < 60:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = A4[1] - 50
        pdf.drawString(x, y, ln)
        y -= line_height
    return y


def export_analysis_pdf(analysis) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50
    line_height = 16
    margin_x = 50

    pdf.setTitle(f"analysis-{analysis.id}")
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(margin_x, y, "Infrastructure Feasibility Analysis Report")
    y -= 2 * line_height

    pdf.setFont("Helvetica", 10)
    pdf.drawString(margin_x, y, f"Generated: {datetime.utcnow().isoformat()} UTC")
    y -= line_height
    pdf.drawString(margin_x, y, f"Analysis ID: {analysis.id}")
    y -= line_height
    pdf.drawString(margin_x, y, f"Status: {analysis.status}")
    y -= 2 * line_height

    project = getattr(analysis, "project", None)
    if project:
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(margin_x, y, "Project Overview")
        y -= 1.5 * line_height
        pdf.setFont("Helvetica", 10)
        pdf.drawString(margin_x, y, f"Name: {project.name}")
        y -= line_height
        pdf.drawString(margin_x, y, f"Country: {project.country}")
        y -= line_height
        pdf.drawString(margin_x, y, f"Technology: {project.technology}")
        y -= line_height
        pdf.drawString(margin_x, y, f"Capacity (MW): {project.capacity_mw}")
        y -= line_height
        pdf.drawString(margin_x, y, f"Location: {project.location_lat}, {project.location_lon}")
        y -= 2 * line_height

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margin_x, y, "Key Financial Metrics")
    y -= 1.5 * line_height
    pdf.setFont("Helvetica", 10)
    pdf.drawString(margin_x, y, f"NPV (USD): {analysis.npv_usd}")
    y -= line_height
    pdf.drawString(margin_x, y, f"IRR (%): {analysis.irr_percent}")
    y -= line_height
    pdf.drawString(margin_x, y, f"LCOE (USD/MWh): {analysis.lcoe_usd_mwh}")
    y -= line_height
    pdf.drawString(margin_x, y, f"Country Risk Score: {analysis.country_risk_score}")
    y -= line_height
    pdf.drawString(margin_x, y, f"Country Risk Grade: {analysis.country_risk_grade}")
    y -= 2 * line_height

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margin_x, y, "Narrative Summary")
    y -= 1.5 * line_height
    pdf.setFont("Helvetica", 10)
    narrative = analysis.narrative_report or "No narrative available."
    y = _pdf_write_multiline(pdf, narrative, margin_x, y, line_height, max_width=100)
    y -= 2 * line_height

    summary = _summary_from_full_report(analysis.full_report or {})
    if summary.get("recommendation"):
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(margin_x, y, "Recommendation")
        y -= 1.5 * line_height
        pdf.setFont("Helvetica", 10)
        y = _pdf_write_multiline(pdf, summary["recommendation"], margin_x, y, line_height, max_width=100)
        y -= line_height

    key_numbers = summary.get("key_numbers") or {}
    if key_numbers:
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(margin_x, y, "Key Numbers")
        y -= 1.5 * line_height
        pdf.setFont("Helvetica", 10)
        for k, v in key_numbers.items():
            pdf.drawString(margin_x + 15, y, f"- {k}: {v}")
            y -= line_height

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.read()