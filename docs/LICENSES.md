# Software Licenses & Third-Party Dependencies

Signalpost is released under the **MIT License**.

All direct and transitive dependencies in `requirements.txt` are licensed under permissive, OSI-approved open source licenses (MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, Python Software Foundation License). No copyleft (GPL/AGPL) or restrictive commercial licenses are present.

## Core Dependencies

| Package | Version | License | Usage |
| :--- | :--- | :--- | :--- |
| **beautifulsoup4** | 4.15.0 | MIT | HTML / XML parsing and DOM tree traversal |
| **extruct** | 0.18.0 | BSD-3-Clause | Extraction of embedded metadata (JSON-LD, Microdata) |
| **lxml** | 6.1.2 | BSD-3-Clause | High-performance C-based XML/HTML parsing and XPath |
| **pydantic** | 2.13.4 | MIT | Data validation, contract typing, and serialization |
| **pypdf** | 6.16.1 | BSD-3-Clause | Extraction of text spans from official PDF annual accounts |
| **tldextract** | 5.3.2 | BSD-3-Clause | Accurate domain and registered-domain extraction |
| **trafilatura** | 2.2.0 | Apache-2.0 | Clean text extraction and structural content scraping |
| **requests** | 2.34.2 | Apache-2.0 | HTTP client library for network requests |

## Transitive Dependencies

| Package | License | Package | License |
| :--- | :--- | :--- | :--- |
| `annotated-types` | MIT | `courlan` | Apache-2.0 |
| `babel` | BSD-3-Clause | `dateparser` | BSD-3-Clause |
| `certifi` | MPL-2.0 | `filelock` | The Unlicense |
| `charset-normalizer` | MIT | `htmldate` | Apache-2.0 |
| `html-text` | BSD-3-Clause | `idna` | BSD-3-Clause |
| `html5lib` | MIT | `justext` | BSD-2-Clause |
| `jstyleson` | MIT | `mf2py` | MIT |
| `lxml-html-clean` | BSD-3-Clause | `pyparsing` | MIT |
| `pyrdfa3` | W3C / BSD | `python-dateutil` | Apache-2.0 / BSD |
| `pytz` | MIT | `rdflib` | BSD-3-Clause |
| `regex` | Apache-2.0 | `requests-file` | Apache-2.0 |
| `six` | MIT | `soupsieve` | MIT |
| `tld` | MPL-2.0 / LGPL | `typing-extensions` | Python Software Foundation |
| `tzlocal` | MIT | `urllib3` | MIT |
| `w3lib` | BSD-3-Clause | `webencodings` | BSD-3-Clause |

## Data Sources & Public Content Licenses

1. **Brønnøysundregistrene (Enhetsregisteret & Regnskapsregisteret)**:
   - **Licence**: Norwegian Licence for Open Government Data (NLOD 2.0).
   - Allows commercial and non-commercial reuse, adaptation, and distribution with attribution.
2. **NAV Arbeidsplassen (`pam-stilling-feed`)**:
   - **Terms**: Open public job search feed. Signalpost complies strictly with retention terms (inactive ads pruned, personal contact lists never persisted).
