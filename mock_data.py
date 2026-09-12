"""
Mock data matching the shared EvidenceRank candidate_result schema.
Swap this out for Person 3's real output later -- nothing else in this
package needs to change.
"""

MOCK_JD_TEXT = """
We are looking for a rockstar Junior Full Stack Developer Intern to join
TechNova Solutions. The ideal candidate is a digital native and recent
graduate with 5+ years of experience with React. He must have strong
communication skills and a Bachelor's degree. Experience with MongoDB,
Node.js and Git is a plus. Experience with Docker is required.
"""

MOCK_CANDIDATES = [
    {
        "candidate_id": "candidate_01",
        "candidate_name": "Aisha Verma",
        "final_score": 88.7,
        "score_breakdown": {"keyword": 86.0, "semantic": 91.2, "experience": 84.0, "evidence_strength": 90.0},
        "requirements": [
            {"id": "REQ001", "text": "React", "keyword_score": 100, "semantic_score": 98,
             "match_type": "EXACT", "evidence": "Built a React dashboard for tracking inventory."},
            {"id": "REQ002", "text": "Backend API development", "keyword_score": 45, "semantic_score": 92,
             "match_type": "SEMANTIC", "evidence": "Developed REST APIs using Express and deployed them on Heroku."},
            {"id": "REQ003", "text": "MongoDB", "keyword_score": 100, "semantic_score": 97,
             "match_type": "NORMALIZED", "evidence": "Used Mongo DB for persistence in the capstone project."},
            {"id": "REQ004", "text": "Docker", "keyword_score": 0, "semantic_score": 12,
             "match_type": "NOT_EVIDENCED", "evidence": None},
            {"id": "REQ005", "text": "Git", "keyword_score": 90, "semantic_score": 80,
             "match_type": "EXACT", "evidence": "Managed version control using Git and GitHub for all projects."},
        ],
    },
    {
        "candidate_id": "candidate_02",
        "candidate_name": "Rahul Nair",
        "final_score": 71.3,
        "score_breakdown": {"keyword": 65.0, "semantic": 78.0, "experience": 60.0, "evidence_strength": 70.0},
        "requirements": [
            {"id": "REQ001", "text": "React", "keyword_score": 60, "semantic_score": 70,
             "match_type": "SEMANTIC", "evidence": "Worked on a single-page app using a component-based JS framework."},
            {"id": "REQ002", "text": "Backend API development", "keyword_score": 30, "semantic_score": 55,
             "match_type": "SEMANTIC", "evidence": "Built a small Flask service for a college project."},
            {"id": "REQ003", "text": "MongoDB", "keyword_score": 0, "semantic_score": 20,
             "match_type": "NOT_EVIDENCED", "evidence": None},
            {"id": "REQ004", "text": "Docker", "keyword_score": 0, "semantic_score": 10,
             "match_type": "NOT_EVIDENCED", "evidence": None},
            {"id": "REQ005", "text": "Git", "keyword_score": 80, "semantic_score": 75,
             "match_type": "EXACT", "evidence": "Used Git for collaborative coursework."},
        ],
    },
    {
        "candidate_id": "candidate_03",
        "candidate_name": "Priya Shah",
        "final_score": 42.5,
        "score_breakdown": {"keyword": 20.0, "semantic": 55.0, "experience": 30.0, "evidence_strength": 40.0},
        "requirements": [
            {"id": "REQ001", "text": "React", "keyword_score": 0, "semantic_score": 30,
             "match_type": "NOT_EVIDENCED", "evidence": None},
            {"id": "REQ002", "text": "Backend API development", "keyword_score": 0, "semantic_score": 20,
             "match_type": "NOT_EVIDENCED", "evidence": None},
            {"id": "REQ003", "text": "MongoDB", "keyword_score": 0, "semantic_score": 15,
             "match_type": "NOT_EVIDENCED", "evidence": None},
            {"id": "REQ004", "text": "Docker", "keyword_score": 0, "semantic_score": 10,
             "match_type": "NOT_EVIDENCED", "evidence": None},
            {"id": "REQ005", "text": "Git", "keyword_score": 50, "semantic_score": 60,
             "match_type": "SEMANTIC", "evidence": "Familiar with basic command-line tools and version tracking."},
        ],
    },
]
