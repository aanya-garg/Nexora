# Host testing dataset

Inputs supplied: Sample_JD.pdf and drive-download-20260912T084145Z-1-001.zip.
The archive contains 18 PDF resume documents. All 18 produced extracted text.
The PDF describes a Junior Full Stack Developer Intern role. No candidate scores
or relevance labels were supplied. No thresholds or weights were tuned on testing resumes.

The prepared local directory is data/testing, separate from data/training.
Both are excluded from Git. Parser warnings remain visible: missing/empty sections
are not invented. Extracted requirements with complex alternatives, qualifications,
or unspecified priority require review; literal keyword matching alone does not
verify those qualifications.

## Prepare on another machine

```powershell
python training_data.py PATH_TO_TESTING_ZIP --split testing
python evaluate_dataset.py --dataset data/testing/parsed_resumes.json --split testing --jd PATH_TO_SAMPLE_JD --prepare-only
```

Preparation writes keyword evidence to preparation.json and explicitly labels it
keyword_only_not_final_scores. It does not create fake rankings.

## Run the real pipeline

```powershell
python -m pip install -e ".[test,semantic]"
python setup_model.py
python evaluate_dataset.py --dataset data/testing/parsed_resumes.json --split testing --jd PATH_TO_SAMPLE_JD
```

The final command writes results.json with 0–100 scores, rankings, evidence,
explanations, JD issues and validation. setup_model.py is an explicit one-time online
download; evaluation itself uses the cached model only. The real model is currently
unavailable in the local review environment, so final testing rankings have not yet
been generated or verified. Do not report keyword-only preparation as final results.
