# Document Generation

Supplied DOCX files are kept unchanged as originals. The tagging script creates audited working copies with `docxtpl` placeholders. Completed/verified cases resolve company, case type and template version before rendering. Generated files record checksum, template version, actor and timestamp. PDF generation falls back to a structured ReportLab report if office conversion or a usable DOCX is unavailable.
