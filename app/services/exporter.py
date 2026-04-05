"""
app/services/exporter.py
Investor-grade export service for infra-feasibility-ai.
Generates PDF reports (using ReportLab) and Excel models (using XlsxWriter).
"""
import io
import json
from datetime import datetime
from typing import Dict, Any, List

import pandas as pd
import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.units import inch


def generate_excel_model(report_data: Dict[str, Any]) -> io.BytesIO:
    """
    Generate a multi-sheet Excel financial model and technical report.
    """
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    
    # Formats
    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
    title_fmt = workbook.add_format({'bold': True, 'font_size': 14, 'font_color': '#1F4E78'})
    money_fmt = workbook.add_format({'num_format': '$#,##0.00'})
    pct_fmt = workbook.add_format({'num_format': '0.0%'})
    
    # 1. Summary Sheet
    summary = workbook.add_worksheet('Executive Summary')
    summary.write('A1', 'Infrastructure Feasibility Analysis: ' + report_data['project']['name'], title_fmt)
    summary.write('A3', 'Generated on:', header_fmt)
    summary.write('B3', datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'))
    
    rows = [
        ('Project Country', report_data['project']['country']),
        ('Technology', report_data['project']['technology']),
        ('Capacity (MW)', report_data['project']['capacity_mw']),
        ('Annual Production (MWh)', report_data['energy']['annual_production_mwh']),
        ('NPV (USD)', report_data['financials']['npv_usd']),
        ('IRR (%)', report_data['financials']['irr_percent'] / 100),
        ('LCOE ($/MWh)', report_data['financials']['lcoe_usd_mwh']),
        ('Payback Years', report_data['financials']['payback_years']),
        ('Country Risk Grade', report_data['risk']['risk_grade']),
    ]
    
    for i, (label, val) in enumerate(rows):
        summary.write(i + 5, 0, label, header_fmt)
        if isinstance(val, (int, float)) and 'USD' in label:
            summary.write(i + 5, 1, val, money_fmt)
        elif 'IRR' in label or '%' in label:
            summary.write(i + 5, 1, val, pct_fmt)
        else:
            summary.write(i + 5, 1, val)
            
    # 2. Financials Sheet
    fin = workbook.add_worksheet('Financial Projections')
    fin.write('A1', 'Annual Cash Flow Projections', title_fmt)
    
    # 3. Risk & Scenarios Sheet
    scen = workbook.add_worksheet('Scenario Analysis')
    scen.write('A1', 'Scenario Comparison', title_fmt)
    
    if 'scenarios' in report_data:
        headers = ['Scenario', 'NPV (USD)', 'IRR (%)', 'LCOE ($/MWh)']
        for col, h in enumerate(headers):
            scen.write(2, col, h, header_fmt)
            
        for row, (s_name, s_data) in enumerate(report_data['scenarios'].items()):
            scen.write(row + 3, 0, s_name)
            scen.write(row + 3, 1, s_data.get('npv_usd', 0), money_fmt)
            scen.write(row + 3, 2, s_data.get('irr_percent', 0) / 100, pct_fmt)
            scen.write(row + 3, 3, s_data.get('lcoe_usd_mwh', 0))

    workbook.close()
    output.seek(0)
    return output


def generate_pdf_report(report_data: Dict[str, Any]) -> io.BytesIO:
    """
    Generate an investor-grade PDF report.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, spaceAfter=20, textColor=colors.hexColor("#1F4E78"))
    h2_style = ParagraphStyle('H2Style', parent=styles['Heading2'], fontSize=14, spaceBefore=15, spaceAfter=10, textColor=colors.hexColor("#2E75B6"))
    body_style = styles['BodyText']
    
    elements = []
    
    # Cover Page
    elements.append(Paragraph(f"Project Feasibility Report", title_style))
    elements.append(Paragraph(f"<b>{report_data['project']['name']}</b>", ParagraphStyle('Sub', fontSize=24, alignment=1)))
    elements.append(Spacer(1, 2 * inch))
    elements.append(Paragraph(f"Country: {report_data['project']['country']}", body_style))
    elements.append(Paragraph(f"Capacity: {report_data['project']['capacity_mw']} MW", body_style))
    elements.append(Paragraph(f"Date: {datetime.utcnow().strftime('%B %d, %Y')}", body_style))
    elements.append(PageBreak())
    
    # Executive Summary
    elements.append(Paragraph("1. Executive Summary", h2_style))
    summary_text = (
        f"This report evaluates the feasibility of a {report_data['project']['capacity_mw']} MW "
        f"{report_data['project']['technology']} project in {report_data['project']['country']}. "
        f"The analysis yields an Estimated NPV of ${report_data['financials']['npv_usd']:,.2f} "
        f"and an IRR of {report_data['financials']['irr_percent']:.2f}%."
    )
    elements.append(Paragraph(summary_text, body_style))
    
    # Metrics Table
    data = [
        ['Metric', 'Value'],
        ['Technology', report_data['project']['technology']],
        ['Annual Production', f"{report_data['energy']['annual_production_mwh']:,.0f} MWh"],
        ['Capacity Factor', f"{report_data['energy']['capacity_factor']:.1f}%"],
        ['Levelized Cost (LCOE)', f"${report_data['financials']['lcoe_usd_mwh']:.2f} / MWh"],
        ['Country Risk Score', f"{report_data['risk']['risk_score']:.1f} ({report_data['risk']['risk_grade']})"],
    ]
    t = Table(data, colWidths=[2.5*inch, 2.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.hexColor("#1F4E78")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ]))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(t)
    
    # Financial Analysis
    elements.append(Paragraph("2. Financial Analysis", h2_style))
    elements.append(Paragraph("Key indicators based on risk-adjusted discount rates and project life.", body_style))
    
    # Risk & Scenarios
    elements.append(Paragraph("3. Scenario & Risk Analysis", h2_style))
    elements.append(Paragraph("Sensitivity analysis against price volatility and capex overruns.", body_style))
    
    # Build
    doc.build(elements)
    buffer.seek(0)
    return buffer
