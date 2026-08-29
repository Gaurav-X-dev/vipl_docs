# Import System

The `VIPL_STANDARD_V1` mapping implements the 18 columns extracted from Image 3. Processing is upload → parse → header mapping → row validation → preview → transactional commit. Parsed-content checksums prevent the same workbook from bypassing duplicate protection when XLSX metadata changes. Company/KRN and fallback business keys protect individual cases. Each populated form value retains batch, original column/value, import timestamp and later edit history.
