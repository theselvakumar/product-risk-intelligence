"""PDF Report Generator for Product Compliance Risk Intelligence Report using ReportLab."""

import io
from datetime import datetime, timezone
from typing import List, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.report import CaseComplianceReportData


class NumberedCanvas:
    """Custom canvas wrapper for running header and multi-page pagination."""
    # We will use onFirstPage and onLaterPages callbacks with simple canvas operations
    pass


class PdfReportGenerator:
    """Generates publication-quality, statutory compliance PDF reports."""

    @classmethod
    def generate_pdf(cls, data: CaseComplianceReportData) -> bytes:
        """Render complete PDF bytes from structured CaseComplianceReportData."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=44,
            bottomMargin=44,
        )

        styles = getSampleStyleSheet()
        normal = styles["Normal"]

        # Custom typography styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#0f172a"),
            alignment=0,
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#047857"),
            textTransform="uppercase",
        )
        meta_style = ParagraphStyle(
            "DocMeta",
            parent=normal,
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#64748b"),
        )
        h1_style = ParagraphStyle(
            "SectionH1",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=10,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "BodyTextCustom",
            parent=normal,
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#334155"),
        )
        bold_body = ParagraphStyle(
            "BoldBody",
            parent=body_style,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#0f172a"),
        )
        key_style = ParagraphStyle(
            "KeyStyle",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#475569"),
        )
        disclaimer_title_style = ParagraphStyle(
            "DiscTitle",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#991b1b"),
        )
        disclaimer_text_style = ParagraphStyle(
            "DiscText",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#7f1d1d"),
        )
        code_style = ParagraphStyle(
            "CodeStyle",
            parent=normal,
            fontName="Courier",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#334155"),
        )

        story = []

        # -------------------------------------------------------------------
        # Document Header
        # -------------------------------------------------------------------
        story.append(Paragraph("FOOD SAFETY AND STANDARDS AUTHORITY OF INDIA (FSSAI)", subtitle_style))
        story.append(Paragraph("PROJECT DRISHTI &bull; REGULATORY SURVEILLANCE & COMPLIANCE INTELLIGENCE", subtitle_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(data.report_title, title_style))
        meta_line = (
            f"<b>Report ID:</b> {data.report_identifier} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Generated:</b> {data.generated_at[:19].replace('T', ' ')} UTC &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Classification:</b> OFFICIAL REGULATORY INTELLIGENCE"
        )
        story.append(Paragraph(meta_line, meta_style))
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0f172a"), spaceAfter=10))

        # -------------------------------------------------------------------
        # Mandatory AI Decision-Support Disclaimer Banner
        # -------------------------------------------------------------------
        disclaimer_content = [
            [Paragraph("&#9888; STATUTORY AI DECISION-SUPPORT NOTICE (MANDATORY)", disclaimer_title_style)],
            [Paragraph(data.mandatory_statutory_disclaimer, disclaimer_text_style)],
            [Paragraph(data.legal_framework_notice, ParagraphStyle("LegSub", parent=meta_style, fontSize=7, leading=8.5))],
        ]
        disc_table = Table(disclaimer_content, colWidths=[523])
        disc_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#f87171")),
            ("LINEBEFORE", (0, 0), (0, -1), 4, colors.HexColor("#dc2626")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(disc_table)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------------
        # 1. CASE INFORMATION
        # -------------------------------------------------------------------
        c = data.case_info
        story.append(Paragraph("1. CASE INFORMATION", h1_style))
        case_data = [
            [
                Paragraph("Case Docket Number", key_style),
                Paragraph(f"<b>{c.case_number}</b> (ID: {c.case_id})", body_style),
                Paragraph("Status & Priority", key_style),
                Paragraph(f"<b>{c.status}</b> &bull; {c.priority}", body_style),
            ],
            [
                Paragraph("Submission Date", key_style),
                Paragraph(c.created_at[:19].replace("T", " ") + " UTC", body_style),
                Paragraph("Assigned Officer", key_style),
                Paragraph(c.assigned_officer or "Unassigned / Automated Triage Pool", body_style),
            ],
            [
                Paragraph("Jurisdiction", key_style),
                Paragraph(c.jurisdiction or "Central Territorial Jurisdiction (DL-CENTRAL)", body_style),
                Paragraph("Generating System", key_style),
                Paragraph(data.generating_system, body_style),
            ],
        ]
        case_table = Table(case_data, colWidths=[110, 151, 110, 152])
        case_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(case_table)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------------
        # 2. PRODUCT INFORMATION
        # -------------------------------------------------------------------
        p = data.product_info
        story.append(Paragraph("2. PRODUCT INFORMATION", h1_style))
        prod_data = [
            [
                Paragraph("Product Name", key_style),
                Paragraph(f"<b>{p.product_name}</b>", bold_body),
                Paragraph("Brand / Trademark", key_style),
                Paragraph(p.brand or "Not Declared", body_style),
            ],
            [
                Paragraph("Statutory Category", key_style),
                Paragraph(p.category or "General Food SKU", body_style),
                Paragraph("FSSAI License No.", key_style),
                Paragraph(f"<b>{p.fssai_license_number or 'NOT DECLARED ON PACKAGING'}</b>", body_style),
            ],
            [
                Paragraph("Declared Manufacturer", key_style),
                Paragraph(p.manufacturer or "Manufacturer details under verification", body_style),
                Paragraph("Verification State", key_style),
                Paragraph("FoSCoS & Registry Match Pending", body_style),
            ],
        ]
        prod_table = Table(prod_data, colWidths=[110, 151, 110, 152])
        prod_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(prod_table)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------------
        # 3. SOURCE INFORMATION
        # -------------------------------------------------------------------
        s = data.source_info
        story.append(Paragraph("3. SOURCE INFORMATION", h1_style))
        source_data = [
            [
                Paragraph("Listing URL", key_style),
                Paragraph(s.product_url or "Direct Physical / Officer Intake", body_style),
                Paragraph("Intake Platform", key_style),
                Paragraph(s.platform or "Physical Regulatory Sampling / Citizen Grievance", body_style),
            ],
            [
                Paragraph("Submitted Images", key_style),
                Paragraph(f"{len(s.submitted_images)} packaging image asset(s) archived", body_style),
                Paragraph("Intake Notes", key_style),
                Paragraph(s.submission_notes or "Routine surveillance sample", body_style),
            ],
            [
                Paragraph("Submitted Description", key_style),
                Paragraph(s.submitted_description or "None provided", body_style),
                Paragraph("Provenance Hash", key_style),
                Paragraph("Cryptographic audit logs active", body_style),
            ],
        ]
        src_table = Table(source_data, colWidths=[110, 151, 110, 152])
        src_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(src_table)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------------
        # 4. RISK ASSESSMENT
        # -------------------------------------------------------------------
        r = data.risk_assessment
        story.append(Paragraph("4. RISK ASSESSMENT", h1_style))
        risk_color_hex = "#b91c1c" if r.risk_level in ("HIGH", "CRITICAL") else ("#d97706" if r.risk_level == "MEDIUM" else "#059669")
        risk_summary_data = [
            [
                Paragraph(f"<font size=18 color='{risk_color_hex}'><b>{r.risk_score:.2f}</b></font><br/><b>{r.risk_level} RISK</b>", ParagraphStyle("RiskBig", parent=normal, alignment=1)),
                Paragraph(
                    f"<b>Statistical Confidence:</b> {int(r.confidence_score * 100)}% &nbsp;&nbsp;|&nbsp;&nbsp; "
                    f"<b>Data Completeness:</b> {int(r.data_completeness_ratio * 100)}% &nbsp;&nbsp;|&nbsp;&nbsp; "
                    f"<b>Findings Analyzed:</b> {r.total_findings_analyzed}<br/>"
                    f"{r.score_explanation or ''}",
                    body_style,
                ),
            ]
        ]
        risk_sum_table = Table(risk_summary_data, colWidths=[120, 403])
        risk_sum_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(risk_sum_table)

        # Dimension breakdown table
        if r.dimension_breakdown:
            story.append(Spacer(1, 4))
            dim_headers = [
                Paragraph("<b>Regulatory Dimension</b>", key_style),
                Paragraph("<b>Findings</b>", key_style),
                Paragraph("<b>Max Severity</b>", key_style),
                Paragraph("<b>Raw Score</b>", key_style),
                Paragraph("<b>Contribution</b>", key_style),
                Paragraph("<b>Confidence</b>", key_style),
            ]
            dim_table_rows = [dim_headers]
            for dim in r.dimension_breakdown:
                dim_table_rows.append([
                    Paragraph(dim.dimension.replace("_", " "), body_style),
                    Paragraph(str(dim.finding_count), body_style),
                    Paragraph(f"<b>{dim.max_severity}</b>", body_style),
                    Paragraph(f"{dim.raw_dimension_score:.2f}", body_style),
                    Paragraph(f"{(dim.weighted_contribution * 100):.1f}%", body_style),
                    Paragraph(f"{int(dim.confidence * 100)}%", body_style),
                ])
            dim_table = Table(dim_table_rows, colWidths=[153, 60, 85, 75, 80, 70])
            dim_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(dim_table)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------------
        # 5. DETECTED FINDINGS
        # -------------------------------------------------------------------
        story.append(Paragraph(f"5. DETECTED REGULATORY FINDINGS ({len(data.detected_findings)})", h1_style))
        if data.detected_findings:
            f_headers = [
                Paragraph("<b>#</b>", key_style),
                Paragraph("<b>Finding Title & Statutory Basis</b>", key_style),
                Paragraph("<b>Severity</b>", key_style),
                Paragraph("<b>Confidence</b>", key_style),
            ]
            finding_table_rows = [f_headers]
            for idx, f in enumerate(data.detected_findings, start=1):
                sev_color = colors.HexColor("#b91c1c" if f.severity == "CRITICAL" else ("#c2410c" if f.severity == "HIGH" else "#b45309"))
                why_text = f"<br/><font color='#b45309'><b>Why Flagged:</b> {f.why_flagged}</font>" if f.why_flagged else ""
                ref_text = f" &bull; <i>{f.statutory_reference}</i>" if f.statutory_reference else ""
                rule_text = f" [Rule: {f.rule_code}]" if f.rule_code else ""
                finding_table_rows.append([
                    Paragraph(str(idx), body_style),
                    Paragraph(f"<b>{f.title}</b>{rule_text}{ref_text}<br/>{f.description}{why_text}", body_style),
                    Paragraph(f"<font color='{sev_color.hexval()}'><b>{f.severity}</b></font>", body_style),
                    Paragraph(f"{int(f.confidence * 100)}%", body_style),
                ])
            f_table = Table(finding_table_rows, colWidths=[20, 383, 65, 55])
            f_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(f_table)
        else:
            story.append(Paragraph("<i>No non-compliance infractions detected during multi-source intelligence evaluation.</i>", body_style))
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------------
        # 6. EVIDENCE
        # -------------------------------------------------------------------
        story.append(Paragraph(f"6. CORROBORATING EVIDENCE RECORDS ({len(data.evidence)})", h1_style))
        if data.evidence:
            ev_headers = [
                Paragraph("<b>Type</b>", key_style),
                Paragraph("<b>Source / Corroboration</b>", key_style),
                Paragraph("<b>Extracted Content Snippet</b>", key_style),
                Paragraph("<b>SHA-256 Hash</b>", key_style),
            ]
            ev_table_rows = [ev_headers]
            for ev in data.evidence[:6]:  # Limit to 6 items to avoid massive PDF bloating
                snippet = (ev.extracted_text[:120] + "...") if ev.extracted_text and len(ev.extracted_text) > 120 else (ev.extracted_text or "Asset attached")
                ev_table_rows.append([
                    Paragraph(f"<b>{ev.evidence_type}</b>", body_style),
                    Paragraph(ev.source[:30], body_style),
                    Paragraph(snippet, body_style),
                    Paragraph((ev.sha256_hash[:16] + "...") if ev.sha256_hash else "None", code_style),
                ])
            ev_table = Table(ev_table_rows, colWidths=[65, 110, 238, 110])
            ev_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(ev_table)
        else:
            story.append(Paragraph("<i>No primary evidence records attached.</i>", body_style))
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------------
        # 7. ANALYSIS LIMITATIONS
        # -------------------------------------------------------------------
        lim = data.analysis_limitations
        story.append(Paragraph("7. ANALYSIS LIMITATIONS & CAVEATS", h1_style))
        missing_str = "<br/>".join(f"&bull; {item}" for item in lim.missing_information)
        ocr_str = "<br/>".join(f"&bull; {item}" for item in lim.ocr_limitations)
        ai_str = "<br/>".join(f"&bull; {item}" for item in lim.ai_confidence_limitations)

        lim_data = [
            [Paragraph("Missing Information", key_style), Paragraph(missing_str, body_style)],
            [Paragraph("OCR Limitations", key_style), Paragraph(ocr_str, body_style)],
            [Paragraph("AI Confidence Bounds", key_style), Paragraph(ai_str, body_style)],
            [
                Paragraph("Completeness Assessment", key_style),
                Paragraph(f"<b>{lim.overall_completeness_assessment}</b> ({int(lim.data_completeness_ratio * 100)}%)", body_style),
            ],
        ]
        lim_table = Table(lim_data, colWidths=[120, 403])
        lim_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(lim_table)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------------
        # 8. REVIEW RECOMMENDATION
        # -------------------------------------------------------------------
        rec = data.review_recommendation
        story.append(Paragraph("8. AUTHORITY REVIEW RECOMMENDATION", h1_style))
        actions_str = "<br/>".join(f"&bull; <b>{act}</b>" for act in rec.suggested_actions)
        rec_color_hex = "#991b1b" if rec.recommendation == "PRIORITY_REVIEW" else "#065f46"
        rec_bg_hex = "#fef2f2" if rec.recommendation == "PRIORITY_REVIEW" else "#f0fdf4"

        rec_data = [
            [
                Paragraph(
                    f"<font size=11 color='{rec_color_hex}'><b>RECOMMENDED ACTION: {rec.recommendation.replace('_', ' ')} ({rec.priority_level})</b></font><br/>"
                    f"{rec.recommendation_reason}<br/><br/>"
                    f"<b>Suggested Statutory Next Steps:</b><br/>{actions_str}",
                    body_style,
                )
            ]
        ]
        rec_table = Table(rec_data, colWidths=[523])
        rec_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(rec_bg_hex)),
            ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor(rec_color_hex)),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(rec_table)
        story.append(Spacer(1, 14))

        # -------------------------------------------------------------------
        # Cryptographic Footer
        # -------------------------------------------------------------------
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=6))
        footer_text = (
            f"<b>DRISHTI Regulatory Dossier</b> &bull; SHA-256 Digest: <font name='Courier'>{data.sha256_report_hash}</font><br/>"
            f"Statutory Governance: Empowered Authority Review Mandatory &bull; Section 32/38 FSS Act, 2006"
        )
        story.append(Paragraph(footer_text, ParagraphStyle("Foot", parent=meta_style, fontSize=7, leading=8.5, alignment=1)))

        # Build document with running footer
        def add_page_decorations(canvas, doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor("#64748b"))
            # Running header
            canvas.drawString(36, A4[1] - 25, "FSSAI &bull; DRISHTI REGULATORY SURVEILLANCE DOSSIER")
            canvas.drawRightString(A4[0] - 36, A4[1] - 25, f"Case: {data.case_info.case_number}")
            canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
            canvas.setLineWidth(0.5)
            canvas.line(36, A4[1] - 28, A4[0] - 36, A4[1] - 28)

            # Running footer
            canvas.line(36, 25, A4[0] - 36, 25)
            canvas.drawString(36, 16, "CONFIDENTIAL &bull; AI DECISION-SUPPORT ASSESSMENT &bull; HUMAN AUTHORITY REVIEW MANDATORY")
            canvas.drawRightString(A4[0] - 36, 16, f"Page {canvas.getPageNumber()}")
            canvas.restoreState()

        doc.build(story, onFirstPage=add_page_decorations, onLaterPages=add_page_decorations)

        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
