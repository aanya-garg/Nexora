# Integrated EvidenceRank contract

The executable frontend entry point is `pipeline.analyze_candidates(jd_path, resume_paths)`. See BACKEND.md for setup and output examples.

- A: `parse_jd` returns raw_text, clean_text, warnings. `parse_resume` returns candidate_id, candidate_name, raw_text, sections (strings), normalized_skills, warnings. Supported formats: PDF/TXT/DOCX/XML and valid DOCX files named .docxl.
- B: `extract_requirements` returns requirements and warnings. Requirements have id, text, skill and type (required/preferred/null when unspecified). `match_candidates` returns nested per-candidate requirement results with 0–100 keyword scores and exact evidence.
- Adapters: combine JD parsing and requirements, map original section text into chunks, flatten keyword results. Private keyword/semantic matching in C uses fractions on 0–1. This is an internal mathematical representation, not a public score.
- C: `score_candidate` produces final_score, all four score_breakdown components and every requirement's keyword_score/semantic_score on **0–100**. Each requirement includes id, text, match_type, evidence. `rank_candidates` deterministically sorts them. `scoring.compute_final_score` is the pure weight-slider function.
- D: explanations, recruiter comparisons, JD quality flags and validation consume C's public 0–100 results. UI is separate from D's core responsibilities.

No runtime LLM/API calls. The real local embedding model must be installed and cached during explicit setup. Never substitute synthetic scores when dependencies or a JD are unavailable.
