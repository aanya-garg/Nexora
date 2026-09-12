from mock_data import MOCK_CANDIDATES, MOCK_JD_TEXT
from explanations import generate_top3_explanations
from comparison import compare, not_evidenced, strongest_on_requirement
from jd_quality import detect_jd_issues
from validation import validate_ranking

SEP = "\n" + "=" * 70 + "\n"

print(SEP + "TOP-3 EXPLANATIONS" + SEP)
for item in generate_top3_explanations(MOCK_CANDIDATES):
    print(f"[{item['candidate_id']}] {item['candidate_name']}")
    print(item["explanation"])
    print()

print(SEP + "RECRUITER Q&A -- 'Why is candidate_01 above candidate_02?'" + SEP)
c1 = next(c for c in MOCK_CANDIDATES if c["candidate_id"] == "candidate_01")
c2 = next(c for c in MOCK_CANDIDATES if c["candidate_id"] == "candidate_02")
result = compare(c1, c2)
print(result["sentence"])

print(SEP + "RECRUITER Q&A -- 'What is candidate_02 not clearly evidencing?'" + SEP)
print(not_evidenced(c2))

print(SEP + "RECRUITER Q&A -- 'Who has stronger backend evidence?'" + SEP)
for row in strongest_on_requirement(MOCK_CANDIDATES, "Backend"):
    print(row)

print(SEP + "JD QUALITY / BIAS LENS" + SEP)
for issue in detect_jd_issues(MOCK_JD_TEXT):
    print(issue)

print(SEP + "VALIDATION / QA CHECK" + SEP)
report = validate_ranking(MOCK_CANDIDATES)
for k, v in report.items():
    print(f"{k}: {v}")
