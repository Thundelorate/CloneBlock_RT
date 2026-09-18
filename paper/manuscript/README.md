# ICASSP 2027 manuscript workspace

This directory is a paper-engineering scaffold, not a submission-ready paper.
The scientific argument and final prose must be reviewed and owned by the
authors. Numerical claims are linked to frozen experiment artifacts under
`../../artifacts/tables/paper_icassp/`.

## Layout

- `main.tex`: four-page technical-paper skeleton using the official style.
- `tables/`: compact candidate tables generated from the evidence ledger.
- `refs.bib`: verified core references plus explicit TODO entries.
- `AUTHOR_CHECKLIST.md`: decisions that require an author rather than code.

The official ICASSP 2027 template is stored in `../official_template/`. The
current conference instructions allow four pages of technical content and an
optional fifth page containing only references, funding acknowledgements, and
ethics statements:

- https://cmsworkshops.com/ICASSP2027/papers/paper_kit.php
- https://cmsworkshops.com/ICASSP2027/papers.php

## Compile

From this directory, run:

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Before submission, replace every `AUTHOR TODO`, add all authors and ORCIDs,
verify the PDF is at most 5 MB, and run the official format checker.
