# Revision primary-source audit

Audit date: 2026-10-06 (Asia/Shanghai). This is a targeted source and data-access audit, not a systematic review. Existing source, bibliography and thesis files were not modified. Dataset contents were initially inspected in memory. A follow-up request authorized saving the verified Wangchuk CSV to the local raw-data directory; the successful fetch is recorded below.

## Recommended independent URL corpus

**Tandin Wangchuk, “Phishing URL dataset,” Mendeley Data, V1, 2026, DOI 10.17632/3jddhy2f6s.1.** The creator record reports 149,726 URLs: 94,919 legitimate from Common Crawl CC-MAIN-2024-33 and 54,807 phishing from a PhishTank list. Publication is 9 January 2026; the record explicitly licenses the dataset under CC BY 4.0. The benign source archive covers 3–16 August 2024. The phishing observation range is not specified in the creator description, and publication date must not be substituted for collection time. The associated research-paper title is supplied by the creator, but a separate paper citation is unnecessary for use of this dataset.

Primary sources:

- [Creator record and license](https://data.mendeley.com/datasets/3jddhy2f6s/1)
- [Repository metadata snapshot](https://data.mendeley.com/public-api/datasets/3jddhy2f6s/snapshot/1)
- [Repository file metadata](https://data.mendeley.com/public-api/datasets/3jddhy2f6s/files?folder_id=root&version=1&$start=0&$limit=1000)
- [Common Crawl original archive announcement](https://commoncrawl.org/blog/august-2024-crawl-archive-now-available)

Immediate download:

[dataset2.csv](https://data.mendeley.com/public-files/datasets/3jddhy2f6s/files/575f34ca-98c8-42cd-affe-7dad6aaf17a2/file_downloaded)

Repository size: **11,234,312 bytes**. Repository SHA-256, independently matched after downloading into memory:

`fccce1a99282b3cd8a1fe08fa83350fe44f7afc4c8889a6d0a94ef9c4d7897e3`

### Verified local acquisition follow-up

The identical public download URL was successfully fetched again on 2026-10-06 with `curl`, using redirects and a 13 MB maximum file-size bound, without custom headers or authentication. The resulting 11,234,312 bytes matched the expected SHA-256 before writing:

`/Users/geoff/Projects/FinalProject/data/raw/wangchuk_dataset2.csv`

Successful command (stdout must be captured or redirected to a temporary destination and hash-checked before final placement):

```sh
curl --location --fail --silent --show-error --max-filesize 13000000 'https://data.mendeley.com/public-files/datasets/3jddhy2f6s/files/575f34ca-98c8-42cd-affe-7dad6aaf17a2/file_downloaded'
```

Python `urllib` access reportedly returned HTTP 403 in the caller's environment. The successful route used standard `curl` with no additional request headers. Do not treat that difference as evidence that the file or its provenance changed; verify the hash for every subsequent acquisition.

### Independently inspected CSV contents

The CSV has exactly `URL` and `Label` columns. Counts agree with the creator's totals: `Label=0` has 94,919 rows and `Label=1` has 54,807 rows, corresponding to legitimate and phishing respectively. This mapping is supported by the creator's class totals and file contents; the landing-page description does not separately spell out the numeric mapping. Rows have no observation timestamp.

Using Python `urlsplit`, with `http://` prepended only to strings lacking `://`, a non-root path means `path not in ('', '/')`:

| Published class | Total | Non-root path | Root or empty path |
|---|---:|---:|---:|
| Legitimate (`0`) | 94,919 | 80,081 | 14,838 |
| Phishing (`1`) | 54,807 | 28,962 | 25,845 |

Thus 84.37% of legitimate rows contain non-root paths. This is an inspected property of the actual file, not a conclusion inferred from the phrase “Common Crawl.” It makes this corpus a useful challenge to the PhiUSIIL path/source shortcut. It is not proof that the corpus is unbiased or that its labels have been independently verified.

`urlsplit` raised no `ValueError` in this pass. This is a parse check, not comprehensive URL validity certification. Some strings contain scrape artifacts, such as trailing quotes or semicolons. Retain the existing class-independent parser policy and document any new invalid-row exclusions; do not selectively clean one class or visit listed URLs.

### Required evaluation boundaries

1. Preserve the raw file, exact hash, creator metadata, license and download date in the experiment archive. Cite the dataset DOI and indicate transformations.
2. Use the same deterministic URL feature extractor as the original experiment. Do not replace raw strings with supplied features from another dataset.
3. Freeze the PhiUSIIL-trained models, feature set and validation-selected thresholds before external scoring. The external labels may score predictions but must not choose those thresholds or the primary model.
4. Audit exact raw and canonical URL duplicates, conflicting labels, hostname overlap and registered-domain overlap against the full original corpus. Report removal counts by class.
5. For the strongest domain-unseen external subset, remove registered-domain groups appearing in the full PhiUSIIL corpus. This restriction changes the evaluated population; report its remaining rows/domains/classes rather than describing it as the entire external dataset. A separately labeled raw external score can show the effect of this restriction with overlap statistics disclosed.
6. Score the complete eligible subset, or define a deterministic resource-bound sample before scoring. A balanced sample changes class prevalence and therefore precision, F1 and average precision. Report prevalence and the sampling policy.
7. Report phishing recall and benign false-positive rate as well as aggregate metrics. An external result may be considerably worse than the original near-perfect holdout; such a result is substantive evidence about the shortcut, not an experiment failure to hide.
8. This is a separately published corpus, not automatically a source-independent or temporal validation. PhishTank/common public URL pools can recur in other datasets; explicit overlap checks are necessary. No natural-time drift claim follows from the publication year or row order.

## Alternatives screened

### ISCX-URL2016: appropriate paths, access blocked in this audit

The [official UNB dataset description](https://www.unb.ca/cic/datasets/url-2016.html) says benign URLs were crawled from top-ranked websites and domain-only URLs were removed. It separates benign, spam, phishing, malware and defacement categories. For a phishing-only task, use benign versus phishing and exclude the other three categories; do not map all malicious categories to phishing. The official download link opened a contact-information form with a server error. No downloadable raw file or explicit dataset license was confirmed in this audit. Its 2016 name is not a per-record timestamp.

### PhishStorm: creator-owned record, unspecified license and download failure

The [Aalto creator record](https://research.aalto.fi/en/datasets/phishstorm-phishing-legitimate-url-dataset/) describes 96,018 balanced URLs, with a URL column called `domain` and labels 0 legitimate/1 phishing. The record explicitly says the license is unspecified. Its linked 3.24 MB archive is [urlset.csv.zip](https://research.aalto.fi/files/16859732/urlset.csv.zip), but the actual download returned HTTP 403 here. File contents and path fractions were therefore not verified. It is a plausible historical research corpus, but not the strongest immediate choice with documented reuse terms.

### CompPhish V4: usable raw mapping, benign-path distribution unverified

[CompPhish V4](https://data.mendeley.com/datasets/fmbs4kp9wz/4), by Richa Goenka, has CC BY 4.0 terms, a URL/label mapping XLSX of 635,936 bytes, and a stated September 2024–August 2025 collection interval. The creator describes 15,358 samples from PhishTank/OpenPhish and a benign top-websites list. Raw benign path fractions were not checked. The 726 MB HTML archive is unnecessary for URL-only experiments and was not downloaded. Top-sites sourcing can reproduce the unwanted homepage shortcut, so do not select this corpus solely because it has labels and a clear license.

### Tamal phishing-detection dataset: derived mixture and reporting inconsistencies

The [creator dataset record](https://data.mendeley.com/datasets/6tm2d6sz7p/1) is CC BY 4.0. Its [original paper](https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2024.1308634/full) describes mixing the full PhishStorm corpus with additional sources, removing URL-length outliers, and supplying numerical features. Class totals are reversed in different parts of the paper. It should not be used to claim a fresh independent raw-URL cohort without auditing actual raw strings, labels, provenance and overlaps. Length-based curation would also complicate a URL-length-shift experiment.

## Fresh verification of the 2026 Frontiers citation

DOI **10.3389/fcomp.2026.1834407** was rechecked directly against the [publisher full text](https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2026.1834407/full) and a fresh [Crossref metadata response](https://api.crossref.org/works/10.3389/fcomp.2026.1834407).

Both agree on:

- Title: *An integrated evaluation protocol for adversarial robustness, generalization, and explanation stability in URL-based phishing detection*.
- Authors: Tanvir Ahamed; Shawon Chakrabarty Kakon; Fahmid Al Farid; Jia Uddin; Hezerul Bin Abdul Karim.
- Journal: *Frontiers in Computer Science*, volume 8, article 1834407.
- Publication date: 31 August 2026.

The citation is a real publisher and DOI record; it is not supported solely by a search snippet or the previous note. Its text includes domain-disjoint PhiUSIIL experiments and SHAP stability analysis. Its claims and measurements remain the authors' findings and were not independently replicated here. Existence, peer review and DOI registration do not guarantee methodological correctness. Use it as related work; do not copy its broad novelty or deployment-reliability language into this thesis. The Crossref `relation` object returned empty, which alone is not a comprehensive retraction or correction audit.

## Implications for the current draft

The inspected existing feature code computes raw URL lexical features and uses a fixed bundled Public Suffix List with private domains included. Existing static splits use `StratifiedGroupKFold` and test registered-domain overlap, and thresholds use validation labels. These mechanisms address specific identity/preprocessing risks; they do not eliminate dataset-source shortcuts.

The draft already reports that all retained legitimate PhiUSIIL strings have HTTPS and empty paths. The new external corpus can now test this concern without synthesizing fake benign URLs. Even a well-executed external test will not establish real temporal drift, fresh phishing verification, adversarial semantic preservation, or production readiness. Describe its results as archived cross-corpus generalization under the specified exclusion policy.

If feature ablations or diagnostic subsets are chosen after seeing the original or new test outcomes, their results are exploratory. Preserve the original frozen full-model external result before presenting revised features or source-balanced analyses. A new independent result can strengthen the paper by exposing failure as well as success.

Suggested dataset citation for bibliography/Mendeley import: T. Wangchuk, “Phishing URL dataset,” Mendeley Data, V1, Jan. 9, 2026, doi: 10.17632/3jddhy2f6s.1. Dataset citation is sufficient; do not invent metadata for the associated model paper.
