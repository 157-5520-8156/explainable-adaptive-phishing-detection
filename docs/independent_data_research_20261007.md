# Independent webpage data for external validation

Research checked on 7 October 2026. No model was trained and no external prediction was examined during this investigation. Downloaded creator Python files were inspected as text only; no downloaded code or pickle was executed.

## Decision

Use **CompPhish V4** as the first additional source. Its official release provides modest mapping/feature workbooks and a 726 MB archive of HTML. This is a separately collected corpus, rather than a Hannousse/PhiUSIIL/Wangchuk mirror. However, both CompPhish and Hannousse draw phishing reports from PhishTank/OpenPhish, so different collectors do not guarantee disjoint campaigns or templates. Remove overlapping canonical URLs, registrable domains and HTML duplicates against development data before a frozen external evaluation. [Creator dataset](https://data.mendeley.com/datasets/fmbs4kp9wz/4), [primary data article](https://doi.org/10.1016/j.dib.2026.113219).

**The existing 68-input PageBundle cannot be directly validated with CompPhish's released feature workbook.** A new common passive-HTML representation, extracted identically from archived pages in both corpora, is the defensible option. Freeze the feature contract, model/threshold selection and external domain exclusions before scoring. If the Hannousse HTML cannot be recovered without executing its serialized objects, report that limitation and retain URL-only external validation; do not invent the missing page measurements.

## Candidate comparison

| Candidate | First-party evidence and access | Suitability and limitations |
|---|---|---|
| CompPhish V4 | [Mendeley release](https://data.mendeley.com/datasets/fmbs4kp9wz/4), CC BY 4.0; September 2024–August 2025 collection; 15,358 samples; URL/label/HTML serial mapping plus raw HTML and 70-feature workbook. | Selected. Small metadata/workbooks obtained and checked against creator SHA-256. Raw HTML is unsanitized; read as data without rendering/scripts. Collection period is not a per-row timestamp. |
| Phish360 | [Author university page](https://web.cs.hacettepe.edu.tr/~selman/phish360-dataset/) links to the [author's benchmark repository](https://github.com/almakhamreh/Multimodal-Phishing-Benchmarks) and [Drive folder](https://drive.google.com/drive/folders/1ulQYtb63pZlhgcKMuTeiDze1onsY1yKT). Public folder lists `Phish360_legit.parquet` (500,062,998 bytes) and `Phish360_phish.parquet` (137,932,113 bytes). Website example columns are URL, full_html, BeautifulSoup_text, image_path, class. | Promising fallback. Need actual Parquet schema/label values and dataset-specific reuse terms before use; repository MIT license alone does not establish ownership of page content. University description says 2020–2023 while associated [paper](https://doi.org/10.3390/app16020751) describes a broader collection span; do not assume row chronology. |
| Van Dooremaal et al. | [TU Eindhoven record](https://research.tue.nl/en/datasets/phishing-website-dataset/) identifies the original [Zenodo dataset](https://zenodo.org/records/4922598), CC BY 4.0. Creator API returns benign, phishing and associated raw-data ZIPs of 9,987,034,510; 20,729,283,530; and 7,470,979,443 bytes. | Authoritative independent archive, but ~38 GB download before extraction. Exact URL-to-page metadata and label contract still require ZIP inspection. Do not substitute a third party's repackaging while claiming creator provenance. |
| Putra phishing website dataset | [Original Zenodo deposit](https://zenodo.org/records/8041387), CC BY 4.0, released July 2023; describes 10,395 sites, 5,244 legitimate and 5,151 phishing. Multiple class-prefixed ZIPs plus brands CSV; metadata describes HTML and discovery information. | Feasible source in principle, but raw archives total tens of GB and individual benign parts commonly exceed 2 GB. Actual metadata schema and label verification method have not been independently checked. Release date is not capture time. |
| MTLP / Çolhak et al. | [Author paper](https://arxiv.org/html/2401.04820v3) directly links the [Google Drive ZIP](https://drive.google.com/file/d/1Lp3ueOd7AxmAl2Y0jJ2U2XlEFa6q8AcT/view). Public preview gives URL/HTML/WHOIS/screenshot-ID fields and ZIP size 18,551,769,446 bytes. | Paper evaluates 65,595 records; current ZIP preview describes 100,000, so release identity must be reconciled. Dataset reuse license is not established by the paper's license. Larger and less precisely versioned than CompPhish. |

## CompPhish acquisition and actual schema

Official metadata was saved to `build/dataset_candidates/compphish_metadata.json` from the [creator API](https://data.mendeley.com/public-api/datasets/fmbs4kp9wz). `download_audit.json` records source URLs, observed byte counts and matched creator hashes. The mapping and feature files agree on the actual 15,358 rows, 8,154 label-0 legitimate and 7,204 label-1 phishing records; URL/label fields are complete and serial numbers unique. These are local file checks, not estimates from the article.

| Artifact | Official URL | Creator SHA-256 |
|---|---|---|
| HTML ZIP, 725,995,327 bytes | [All_HTML.zip](https://data.mendeley.com/public-files/datasets/fmbs4kp9wz/files/b0366589-b008-47f0-882f-518ee6213cde/file_downloaded) | `12440e4f911fabf4ec2c712ae014cb43e638e9a6adc6c7c6a506a8a7df24fcf7` |
| Mapping workbook, 635,936 bytes | [Mapping_File.xlsx](https://data.mendeley.com/public-files/datasets/fmbs4kp9wz/files/867c433a-8cf3-459e-bb07-54f0f83fea60/file_viewed) | `e6dda6a21d925f8aba36090f295b08e9808a5dfe8dd3276bf8cd82022855f14a` |
| Feature workbook, 4,726,765 bytes | [All_Features_threshold90.xlsx](https://data.mendeley.com/public-files/datasets/fmbs4kp9wz/files/aadc8397-86e9-4d01-a19e-a4144b3a058d/file_downloaded) | `6e87b7997c2d0e9e3f1e02fd5ee1240442385f9bea5f0a40e46e7b6e43ada21b` |
| Dictionary, 18,182 bytes | [Data_Dictionary.xlsx](https://data.mendeley.com/public-files/datasets/fmbs4kp9wz/files/fd4547ab-3100-45ca-bd62-171523e8f720/file_viewed) | `a4237dd99d7f4a55edc3ffe88a416db77b1734f7c5d52677f8f0c86bf8b88470` |

Some `file_downloaded` endpoints returned HTTP 200 JSON error bodies rather than files. The corresponding official `file_viewed` endpoints returned bytes matching the published hashes. A status code alone is therefore insufficient acquisition evidence.

Acquisition subsequently completed: the full 725,995,327-byte CompPhish HTML ZIP matches its creator SHA-256, and all ten Hannousse raw parts (288,872,675 bytes total) match their individual creator hashes. The complete CompPhish ZIP contains exactly one `.txt` page for each of the 15,358 mapping serials, with no extra or missing serials. Artifacts remain under `data/raw/archives`; acquisition JSON records retain URLs, byte counts, hashes and method.

`scripts/recover_official_archive_ranges.py` recovered intermittent file-serving failures using Mozilla user agent, exact HTTP 206 byte ranges, bounded chunks, retries and complete hash verification. It rejects success-status JSON bodies, mismatched ranges and incomplete/incorrect archives. Four acquisition boundary tests passed. No archive was deserialized by this acquisition step. The public page's Download All implementation also provides an official fallback at `https://data.mendeley.com/public-api/zip/{dataset_id}/download/{version}`; the Hannousse V3 bulk ZIP is approximately 59 MB compressed and contains the ten raw parts, CSV and scripts. Per-member creator hashes remain necessary if using that bulk alternative.

The [creator README](https://data.mendeley.com/public-files/datasets/fmbs4kp9wz/files/15a313c5-6ac2-4b02-add0-9ec2a25670cf/file_viewed) associates HTML `.txt` filenames with manually assigned serial numbers and describes HTTP retrieval with Selenium fallback. Inaccessible pages were removed. This creates capture/availability selection and potentially mixed static/rendered representations. No evidence supports interpreting label arrival or model replay order as historical time.

## Feature contract audit

The current model takes 44 recomputed URL measurements and 24 Hannousse content measurements. CompPhish has 73 columns including URL/label/serial; its content columns do not share that contract. The creator [dictionary](https://data.mendeley.com/public-files/datasets/fmbs4kp9wz/files/fd4547ab-3100-45ca-bd62-171523e8f720/file_viewed) and [extractor source archive](https://data.mendeley.com/public-files/datasets/fmbs4kp9wz/files/86e5d2e1-8900-43ab-aa8f-0f0799c8f9f3/file_viewed) show concrete differences: hyperlink totals include form actions, missing-title rules include generic titles, and favicon/title mismatch criteria differ. Renaming superficially similar columns would change meaning.

Hannousse's official `content_features.py`, inspected as text and checked against its creator hash, makes live linked-resource requests for four redirect/error ratios. Passive archived HTML cannot reconstruct these historical responses. Its raw page archives are ten pickle parts, approximately 289 MB in total, listed in [original release metadata](https://data.mendeley.com/public-api/datasets/c2gw7fy2j4). Any recovery must parse data without invoking pickle globals. A common, versioned passive parser on both corpora avoids pretending that differing creator features are equivalent. It also makes missing/failed HTML explicit instead of encoding fabricated zeros.

## Evaluation conditions

1. Use creator labels with documented mapping; remove conflicts rather than resolving them from model output.
2. Normalize URLs consistently, group by registrable domain, audit exact and normalized HTML duplicates, and exclude external domains represented in development.
3. Keep raw bytes, hashes, exclusions, parsed records and model predictions. Report excluded class/domain counts and any unresolved archive association.
4. Select architecture and threshold only on development data. An external score is still valid if poor; further redesign after viewing it must be labeled exploratory and requires another independent source for a fresh test.
5. Report FPR and recall together with domain-level uncertainty. Report prevalence and domain concentration; a balanced released corpus is not production prevalence.
