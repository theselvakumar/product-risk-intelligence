"""HTML Report Generator for Product Compliance Risk Intelligence Report."""

import html
from app.schemas.report import CaseComplianceReportData


class HtmlReportGenerator:
    """Renders high-fidelity, printable HTML reports for FSSAI / DRISHTI cases."""

    @classmethod
    def generate_html(cls, data: CaseComplianceReportData) -> str:
        """Produce full standalone HTML string with inline CSS for printing & web viewing."""
        c = data.case_info
        p = data.product_info
        s = data.source_info
        r = data.risk_assessment
        lim = data.analysis_limitations
        rec = data.review_recommendation

        # Severity colors
        severity_colors = {
            "CRITICAL": "#b91c1c",
            "HIGH": "#c2410c",
            "MEDIUM": "#b45309",
            "LOW": "#047857",
            "INFO": "#1d4ed8",
        }

        # Build findings rows HTML
        findings_html = ""
        if data.detected_findings:
            for idx, f in enumerate(data.detected_findings, start=1):
                sev_color = severity_colors.get(f.severity, "#4b5563")
                findings_html += f"""
                <div class="finding-card">
                  <div class="finding-header">
                    <span class="finding-num">#{idx}</span>
                    <span class="finding-title">{html.escape(f.title)}</span>
                    <span class="badge" style="background-color: {sev_color}15; color: {sev_color}; border: 1px solid {sev_color}40;">
                      {html.escape(f.severity)}
                    </span>
                    <span class="badge-sub">Confidence: {int(f.confidence * 100)}%</span>
                  </div>
                  <div class="finding-body">
                    <p class="finding-desc"><strong>Description:</strong> {html.escape(f.description)}</p>
                    {f'<p class="finding-why"><strong>Why Flagged:</strong> {html.escape(f.why_flagged)}</p>' if f.why_flagged else ''}
                    <div class="finding-meta">
                      {f'<span class="meta-tag"><strong>Rule:</strong> {html.escape(f.rule_code)}</span>' if f.rule_code else ''}
                      {f'<span class="meta-tag"><strong>Statutory Ref:</strong> {html.escape(f.statutory_reference)}</span>' if f.statutory_reference else ''}
                      <span class="meta-tag"><strong>Dimension:</strong> {html.escape(f.dimension)}</span>
                    </div>
                  </div>
                </div>
                """
        else:
            findings_html = "<p class='empty-text'>No non-compliance infractions detected during multi-source intelligence evaluation.</p>"

        # Build evidence items HTML
        evidence_html = ""
        if data.evidence:
            for idx, ev in enumerate(data.evidence, start=1):
                evidence_html += f"""
                <div class="evidence-item">
                  <div class="evidence-head">
                    <span class="ev-badge">{html.escape(ev.evidence_type)}</span>
                    <span class="ev-source"><strong>Source:</strong> {html.escape(ev.source)}</span>
                    <span class="ev-time">{html.escape(ev.timestamp[:19].replace('T', ' '))}</span>
                  </div>
                  {f'<pre class="ev-text">{html.escape(ev.extracted_text[:400]) + ("..." if len(ev.extracted_text) > 400 else "")}</pre>' if ev.extracted_text else ''}
                  <div class="ev-foot">
                    <span class="ev-hash"><strong>SHA-256:</strong> {html.escape(ev.sha256_hash or 'Not hashed')}</span>
                  </div>
                </div>
                """
        else:
            evidence_html = "<p class='empty-text'>No primary evidence records attached.</p>"

        # Build dimension breakdown rows
        dim_rows = ""
        for dim in r.dimension_breakdown:
            dim_sev_color = severity_colors.get(dim.max_severity, "#4b5563")
            dim_rows += f"""
            <tr>
              <td><strong>{html.escape(dim.dimension.replace('_', ' '))}</strong></td>
              <td>{dim.finding_count}</td>
              <td><span style="color: {dim_sev_color}; font-weight: bold;">{html.escape(dim.max_severity)}</span></td>
              <td>{dim.raw_dimension_score:.2f}</td>
              <td>{(dim.weighted_contribution * 100):.1f}%</td>
              <td>{int(dim.confidence * 100)}%</td>
            </tr>
            """

        # Build limitations lists
        missing_li = "".join(f"<li>{html.escape(item)}</li>" for item in lim.missing_information)
        ocr_li = "".join(f"<li>{html.escape(item)}</li>" for item in lim.ocr_limitations)
        ai_li = "".join(f"<li>{html.escape(item)}</li>" for item in lim.ai_confidence_limitations)

        # Build recommendations actions
        actions_li = "".join(f"<li><strong>{html.escape(act)}</strong></li>" for act in rec.suggested_actions)

        # Risk score badge color
        risk_color = "#b91c1c" if r.risk_level in ("HIGH", "CRITICAL") else ("#d97706" if r.risk_level == "MEDIUM" else "#059669")

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DRISHTI Compliance Report - {html.escape(c.case_number)}</title>
  <style>
    @page {{
      size: A4;
      margin: 15mm 15mm 20mm 15mm;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      font-size: 11pt;
      line-height: 1.45;
      color: #1e293b;
      background: #ffffff;
      margin: 0;
      padding: 24px;
    }}
    .report-container {{
      max-width: 880px;
      margin: 0 auto;
    }}
    /* Header & Masthead */
    .header {{
      border-bottom: 2px solid #0f172a;
      padding-bottom: 14px;
      margin-bottom: 18px;
    }}
    .gov-banner {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }}
    .gov-title {{
      font-size: 10pt;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #0f172a;
    }}
    .drishti-sub {{
      font-size: 8pt;
      font-weight: 700;
      color: #047857;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .report-title {{
      font-size: 18pt;
      font-weight: 900;
      letter-spacing: -0.02em;
      color: #0f172a;
      margin: 4px 0 2px 0;
    }}
    .report-meta {{
      font-size: 9pt;
      color: #64748b;
      display: flex;
      gap: 16px;
      margin-top: 6px;
    }}
    /* Mandatory Legal Disclaimer Banner */
    .disclaimer-banner {{
      background: #fef2f2;
      border: 1px solid #f87171;
      border-left: 5px solid #dc2626;
      border-radius: 6px;
      padding: 10px 14px;
      margin-bottom: 20px;
      font-size: 9.5pt;
      color: #7f1d1d;
    }}
    .disclaimer-title {{
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin-bottom: 3px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .disclaimer-text {{
      margin: 0;
      font-weight: 600;
    }}
    /* Sections */
    .section {{
      margin-bottom: 22px;
      page-break-inside: avoid;
    }}
    .section-title {{
      font-size: 11pt;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #0f172a;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 4px;
      margin-bottom: 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .section-num {{
      background: #0f172a;
      color: #ffffff;
      padding: 1px 7px;
      border-radius: 4px;
      font-size: 9pt;
      margin-right: 6px;
    }}
    /* Tables */
    table.data-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 9.5pt;
      margin-bottom: 8px;
    }}
    table.data-table th, table.data-table td {{
      padding: 7px 10px;
      text-align: left;
      border: 1px solid #e2e8f0;
    }}
    table.data-table th {{
      background: #f8fafc;
      font-weight: 700;
      color: #334155;
      font-size: 8.5pt;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    table.kv-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 9.5pt;
    }}
    table.kv-table td {{
      padding: 6px 10px;
      border: 1px solid #e2e8f0;
    }}
    table.kv-table td.key {{
      width: 25%;
      font-weight: 700;
      background: #f8fafc;
      color: #475569;
    }}
    table.kv-table td.val {{
      width: 75%;
      color: #0f172a;
    }}
    /* Risk Gauge */
    .risk-card {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .risk-score-box {{
      text-align: center;
      padding-right: 20px;
      border-right: 1px solid #e2e8f0;
    }}
    .risk-num {{
      font-size: 26pt;
      font-weight: 900;
      color: {risk_color};
      line-height: 1;
    }}
    .risk-lbl {{
      font-size: 8.5pt;
      font-weight: 700;
      text-transform: uppercase;
      color: #64748b;
      margin-top: 4px;
    }}
    .risk-details {{
      flex: 1;
      padding-left: 20px;
    }}
    /* Findings Cards */
    .finding-card {{
      border: 1px solid #e2e8f0;
      border-left: 4px solid #0f172a;
      border-radius: 6px;
      padding: 10px 12px;
      margin-bottom: 8px;
      background: #ffffff;
      page-break-inside: avoid;
    }}
    .finding-header {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
    }}
    .finding-num {{
      font-weight: 800;
      color: #64748b;
      font-size: 9pt;
    }}
    .finding-title {{
      font-weight: 800;
      font-size: 10.5pt;
      color: #0f172a;
      flex: 1;
    }}
    .badge {{
      font-size: 8pt;
      font-weight: 800;
      padding: 2px 7px;
      border-radius: 4px;
      text-transform: uppercase;
    }}
    .badge-sub {{
      font-size: 8pt;
      color: #64748b;
      font-weight: 600;
    }}
    .finding-desc {{
      font-size: 9.5pt;
      margin: 0 0 4px 0;
      color: #334155;
    }}
    .finding-why {{
      font-size: 9pt;
      color: #b45309;
      margin: 0 0 6px 0;
    }}
    .finding-meta {{
      font-size: 8.5pt;
      color: #64748b;
      display: flex;
      gap: 12px;
    }}
    .meta-tag {{
      background: #f1f5f9;
      padding: 2px 6px;
      border-radius: 4px;
    }}
    /* Evidence items */
    .evidence-item {{
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 10px;
      margin-bottom: 8px;
      background: #f8fafc;
      font-size: 9pt;
      page-break-inside: avoid;
    }}
    .evidence-head {{
      display: flex;
      justify-content: space-between;
      margin-bottom: 6px;
    }}
    .ev-badge {{
      background: #0f172a;
      color: #ffffff;
      font-size: 7.5pt;
      font-weight: 800;
      padding: 2px 6px;
      border-radius: 4px;
      text-transform: uppercase;
    }}
    .ev-source {{
      color: #334155;
      font-size: 8.5pt;
    }}
    .ev-time {{
      color: #94a3b8;
      font-size: 8pt;
    }}
    .ev-text {{
      background: #ffffff;
      border: 1px solid #cbd5e1;
      padding: 8px;
      border-radius: 4px;
      font-family: Consolas, monospace;
      font-size: 8.5pt;
      margin: 4px 0;
      white-space: pre-wrap;
      word-break: break-all;
    }}
    .ev-foot {{
      font-size: 7.5pt;
      color: #64748b;
      font-family: monospace;
      margin-top: 4px;
    }}
    /* Recommendations Box */
    .rec-box {{
      border: 2px solid {'#dc2626' if rec.recommendation == 'PRIORITY_REVIEW' else '#059669'};
      background: {'#fef2f2' if rec.recommendation == 'PRIORITY_REVIEW' else '#f0fdf4'};
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 12px;
    }}
    .rec-head {{
      font-size: 13pt;
      font-weight: 900;
      color: {'#991b1b' if rec.recommendation == 'PRIORITY_REVIEW' else '#065f46'};
      margin-bottom: 4px;
    }}
    .rec-reason {{
      font-size: 9.5pt;
      color: #334155;
      margin-bottom: 8px;
    }}
    .rec-actions {{
      margin: 0;
      padding-left: 18px;
      font-size: 9pt;
      color: #0f172a;
    }}
    .rec-actions li {{
      margin-bottom: 4px;
    }}
    /* Footer */
    .footer {{
      border-top: 1px solid #cbd5e1;
      padding-top: 12px;
      margin-top: 24px;
      font-size: 8pt;
      color: #64748b;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .empty-text {{
      font-style: italic;
      color: #94a3b8;
      font-size: 9.5pt;
    }}
  </style>
</head>
<body>
  <div class="report-container">
    <!-- Header -->
    <div class="header">
      <div class="gov-banner">
        <div>
          <div class="gov-title">Food Safety and Standards Authority of India (FSSAI)</div>
          <div class="drishti-sub">Project DRISHTI &bull; Regulatory Surveillance & Compliance Intelligence System</div>
        </div>
        <div style="text-align: right; font-size: 8.5pt; color: #475569;">
          <div><strong>CONFIDENTIAL</strong></div>
          <div>Internal Decision Support</div>
        </div>
      </div>
      <h1 class="report-title">{html.escape(data.report_title)}</h1>
      <div class="report-meta">
        <span><strong>Report ID:</strong> {html.escape(data.report_identifier)}</span>
        <span><strong>Generated:</strong> {html.escape(data.generated_at[:19].replace('T', ' '))} UTC</span>
        <span><strong>Status:</strong> {html.escape(c.status)}</span>
      </div>
    </div>

    <!-- Mandatory Statutory AI Decision-Support Disclaimer -->
    <div class="disclaimer-banner">
      <div class="disclaimer-title">
        <span>&#9888; STATUTORY AI DECISION-SUPPORT NOTICE (MANDATORY)</span>
      </div>
      <p class="disclaimer-text">{html.escape(data.mandatory_statutory_disclaimer)}</p>
    </div>

    <!-- 1. CASE INFORMATION -->
    <div class="section">
      <div class="section-title">
        <span><span class="section-num">1</span> Case Information</span>
      </div>
      <table class="kv-table">
        <tr>
          <td class="key">Case Docket Number</td>
          <td class="val"><strong>{html.escape(c.case_number)}</strong> (ID: {html.escape(c.case_id)})</td>
        </tr>
        <tr>
          <td class="key">Docket Status & Priority</td>
          <td class="val"><span class="badge" style="background: #0f172a; color: #fff;">{html.escape(c.status)}</span> &bull; <strong>{html.escape(c.priority)}</strong></td>
        </tr>
        <tr>
          <td class="key">Submission Date</td>
          <td class="val">{html.escape(c.created_at[:19].replace('T', ' '))} UTC</td>
        </tr>
        <tr>
          <td class="key">Assigned Authority Officer</td>
          <td class="val">{html.escape(c.assigned_officer or 'Unassigned / Automated Triage Pool')}</td>
        </tr>
        <tr>
          <td class="key">Territorial Jurisdiction</td>
          <td class="val">{html.escape(c.jurisdiction or 'Central Jurisdiction')}</td>
        </tr>
      </table>
    </div>

    <!-- 2. PRODUCT INFORMATION -->
    <div class="section">
      <div class="section-title">
        <span><span class="section-num">2</span> Product Information</span>
      </div>
      <table class="kv-table">
        <tr>
          <td class="key">Product Name</td>
          <td class="val"><strong>{html.escape(p.product_name)}</strong></td>
        </tr>
        <tr>
          <td class="key">Brand / Trademark</td>
          <td class="val">{html.escape(p.brand or 'Not Declared')}</td>
        </tr>
        <tr>
          <td class="key">Statutory Category</td>
          <td class="val">{html.escape(p.category or 'General Food SKU')}</td>
        </tr>
        <tr>
          <td class="key">Declared Manufacturer</td>
          <td class="val">{html.escape(p.manufacturer or 'Under Verification')}</td>
        </tr>
        <tr>
          <td class="key">FSSAI License Number</td>
          <td class="val"><strong style="font-family: monospace;">{html.escape(p.fssai_license_number or 'NOT DECLARED ON PACKAGING')}</strong></td>
        </tr>
      </table>
    </div>

    <!-- 3. SOURCE INFORMATION -->
    <div class="section">
      <div class="section-title">
        <span><span class="section-num">3</span> Source Information</span>
      </div>
      <table class="kv-table">
        <tr>
          <td class="key">Product Listing URL</td>
          <td class="val">{f'<a href="{html.escape(s.product_url)}" target="_blank">{html.escape(s.product_url)}</a>' if s.product_url else 'Direct Physical / Officer Intake'}</td>
        </tr>
        <tr>
          <td class="key">Platform / Channel</td>
          <td class="val">{html.escape(s.platform or 'Physical Regulatory Sampling / Citizen Grievance')}</td>
        </tr>
        <tr>
          <td class="key">Submitted Images</td>
          <td class="val">{len(s.submitted_images)} packaging image asset(s) archived with cryptographic hash verification</td>
        </tr>
        <tr>
          <td class="key">Submitted Description</td>
          <td class="val">{html.escape(s.submitted_description or 'None provided.')}</td>
        </tr>
      </table>
    </div>

    <!-- 4. RISK ASSESSMENT -->
    <div class="section">
      <div class="section-title">
        <span><span class="section-num">4</span> Risk Assessment</span>
      </div>
      <div class="risk-card">
        <div class="risk-score-box">
          <div class="risk-num">{r.risk_score:.2f}</div>
          <div class="risk-lbl">{html.escape(r.risk_level)} RISK</div>
        </div>
        <div class="risk-details">
          <div style="font-size: 10pt; font-weight: bold; margin-bottom: 4px; color: #0f172a;">
            Statistical Confidence: {int(r.confidence_score * 100)}% &bull; Data Completeness: {int(r.data_completeness_ratio * 100)}%
          </div>
          <div style="font-size: 9pt; color: #475569;">
            {html.escape(r.score_explanation or '')}
          </div>
        </div>
      </div>

      {f'''
      <table class="data-table">
        <thead>
          <tr>
            <th>Regulatory Dimension</th>
            <th>Findings</th>
            <th>Max Severity</th>
            <th>Dimension Score</th>
            <th>Contribution</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {dim_rows}
        </tbody>
      </table>
      ''' if r.dimension_breakdown else ''}
    </div>

    <!-- 5. DETECTED FINDINGS -->
    <div class="section">
      <div class="section-title">
        <span><span class="section-num">5</span> Detected Regulatory Findings ({len(data.detected_findings)})</span>
      </div>
      {findings_html}
    </div>

    <!-- 6. EVIDENCE -->
    <div class="section">
      <div class="section-title">
        <span><span class="section-num">6</span> Corroborating Evidence Records ({len(data.evidence)})</span>
      </div>
      {evidence_html}
    </div>

    <!-- 7. ANALYSIS LIMITATIONS -->
    <div class="section">
      <div class="section-title">
        <span><span class="section-num">7</span> Analysis Limitations & Caveats</span>
      </div>
      <table class="kv-table">
        <tr>
          <td class="key">Missing Information</td>
          <td class="val"><ul style="margin: 0; padding-left: 16px;">{missing_li}</ul></td>
        </tr>
        <tr>
          <td class="key">OCR Limitations</td>
          <td class="val"><ul style="margin: 0; padding-left: 16px;">{ocr_li}</ul></td>
        </tr>
        <tr>
          <td class="key">AI Confidence Limitations</td>
          <td class="val"><ul style="margin: 0; padding-left: 16px;">{ai_li}</ul></td>
        </tr>
        <tr>
          <td class="key">Overall Completeness</td>
          <td class="val"><strong>{html.escape(lim.overall_completeness_assessment)}</strong> ({int(lim.data_completeness_ratio * 100)}%)</td>
        </tr>
      </table>
    </div>

    <!-- 8. REVIEW RECOMMENDATION -->
    <div class="section">
      <div class="section-title">
        <span><span class="section-num">8</span> Authority Review Recommendation</span>
      </div>
      <div class="rec-box">
        <div class="rec-head">
          RECOMMENDED ACTION: {html.escape(rec.recommendation.replace('_', ' '))} ({html.escape(rec.priority_level)})
        </div>
        <p class="rec-reason">{html.escape(rec.recommendation_reason)}</p>
        <div style="font-size: 9pt; font-weight: 700; margin-bottom: 4px;">Recommended Authority Next Steps:</div>
        <ul class="rec-actions">
          {actions_li}
        </ul>
      </div>
    </div>

    <!-- Footer -->
    <div class="footer">
      <div>
        <strong>DRISHTI Surveillance Dossier</strong> &bull; SHA-256 Digest: <span style="font-family: monospace;">{html.escape(data.sha256_report_hash or '')}</span>
      </div>
      <div>
        Empowered Authority Review Mandatory
      </div>
    </div>
  </div>
</body>
</html>
"""
