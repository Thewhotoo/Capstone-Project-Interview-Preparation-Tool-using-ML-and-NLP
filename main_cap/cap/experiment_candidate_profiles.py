"""
Experiment Candidate Profiles — research-milestone data, not a new
mechanism. Four additional `CandidateProfile`-shaped plain dicts (frontend,
data/ML, DevOps/cloud, mobile), matching EXACTLY the same shape
`_planning_test_fixtures.sample_profile_dict()` already uses, consumed by
the existing, unmodified `Planner`/`TopicPool`/`QuestionRealizer`
(Phases 1/2) — nothing here defines a new generation mechanism, a new
schema, or a new architectural concept. `_planning_test_fixtures.py` itself
is untouched — it is reserved for Planning-phase tests; these profiles
exist only for this research experiment's pool-diversity purposes.

Purpose: the first end-to-end experiment (session 7) drew its entire pool
from ONE hardcoded backend-flavored profile (8 discussion units total).
That means any trained-vs-heuristic comparison could only ever reflect
performance on one narrow topic distribution. These four profiles, plus the
existing backend one, span five substantially different technical domains
so the generation pool — and any held-out split computed over it — actually
represents more than one candidate's resume.
"""

from __future__ import annotations

from _planning_test_fixtures import sample_profile_dict


def frontend_profile_dict() -> dict:
    return {
        "candidate_name": "Frontend Candidate",
        "contact_details": {"email": "frontend@example.com"},
        "skills": ["JavaScript", "TypeScript", "React", "CSS"],
        "education": [],
        "experience": [
            {
                "company": "Northwind Retail",
                "role": "Frontend Engineer",
                "duration": "2022-2024",
                "summary": "Owned the checkout flow for a high-traffic e-commerce site.",
            }
        ],
        "projects": [
            {
                "title": "Component Design System",
                "summary": "A shared React component library used across five internal products.",
                "technologies": ["React", "TypeScript", "Jest", "Webpack"],
                "concepts": ["Component composition", "Accessibility"],
                "interview_seeds": [
                    "Why TypeScript over plain JavaScript for this library?",
                    "How components handle state internally",
                ],
            },
            {
                "title": "Marketing Site Redesign",
                "summary": "A static marketing site rebuilt for performance.",
                "technologies": ["HTML", "CSS"],
                "concepts": ["Static site generation"],
                "interview_seeds": [],
            },
        ],
        "certifications": ["Meta Front-End Developer Professional Certificate"],
        "predicted_domain": "Frontend Engineering",
        "experience_level": "Intermediate",
        "confidence": 0.8,
        "resume_summary": "A frontend engineering candidate focused on component architecture.",
        "interview_blueprint": {
            "resume_verification_topics": [],
            "technical_topics": [
                {
                    "topic": "React component composition patterns",
                    "originating_project": "Component Design System",
                    "originating_experience": "",
                    "evidence": "built a shared React component library",
                },
                {
                    "topic": "Checkout flow performance",
                    "originating_project": "",
                    "originating_experience": "Frontend Engineer",
                    "evidence": "owned the checkout flow for a high-traffic site",
                },
            ],
            "starting_difficulty": "intermediate",
            "estimated_strengths": ["Strong grasp of component architecture"],
            "estimated_weaknesses": ["Component Design System"],
        },
    }


def data_ml_profile_dict() -> dict:
    return {
        "candidate_name": "Data/ML Candidate",
        "contact_details": {"email": "dataml@example.com"},
        "skills": ["Python", "Pandas", "scikit-learn", "PyTorch"],
        "education": [],
        "experience": [
            {
                "company": "Helios Analytics",
                "role": "Data Scientist",
                "duration": "2021-2024",
                "summary": "Built forecasting models for the demand planning team.",
            }
        ],
        "projects": [
            {
                "title": "Customer Churn Prediction Pipeline",
                "summary": "An end-to-end pipeline predicting subscription churn.",
                "technologies": ["Python", "Pandas", "scikit-learn", "PyTorch"],
                "concepts": ["Feature engineering", "Model evaluation"],
                "interview_seeds": [
                    "How features were engineered from raw event logs",
                    "Why PyTorch over scikit-learn for the final model",
                ],
            },
            {
                "title": "Internal Analytics Dashboard",
                "summary": "A dashboard summarizing model performance for stakeholders.",
                "technologies": ["Python"],
                "concepts": ["Data visualization"],
                "interview_seeds": [],
            },
        ],
        "certifications": ["AWS Certified Machine Learning – Specialty"],
        "predicted_domain": "Data Science / Machine Learning",
        "experience_level": "Intermediate",
        "confidence": 0.8,
        "resume_summary": "A data science candidate focused on predictive modeling.",
        "interview_blueprint": {
            "resume_verification_topics": [],
            "technical_topics": [
                {
                    "topic": "Feature engineering for churn prediction",
                    "originating_project": "Customer Churn Prediction Pipeline",
                    "originating_experience": "",
                    "evidence": "built an end-to-end churn prediction pipeline",
                },
                {
                    "topic": "Demand forecasting model iteration",
                    "originating_project": "",
                    "originating_experience": "Data Scientist",
                    "evidence": "built forecasting models for the demand planning team",
                },
            ],
            "starting_difficulty": "intermediate",
            "estimated_strengths": ["Strong grasp of feature engineering"],
            "estimated_weaknesses": ["Customer Churn Prediction Pipeline"],
        },
    }


def devops_cloud_profile_dict() -> dict:
    return {
        "candidate_name": "DevOps/Cloud Candidate",
        "contact_details": {"email": "devops@example.com"},
        "skills": ["Terraform", "Kubernetes", "AWS", "GitHub Actions"],
        "education": [],
        "experience": [
            {
                "company": "Cascade Systems",
                "role": "DevOps Engineer",
                "duration": "2020-2024",
                "summary": "Owned CI/CD and infrastructure-as-code for a multi-team platform.",
            }
        ],
        "projects": [
            {
                "title": "Multi-Region Kubernetes Deployment Pipeline",
                "summary": "A CI/CD pipeline deploying services across multiple AWS regions.",
                "technologies": ["Kubernetes", "Terraform", "AWS", "GitHub Actions"],
                "concepts": ["Infrastructure as code", "Blue-green deployment"],
                "interview_seeds": [
                    "How the rollout strategy handles a failed region",
                    "Why Terraform over CloudFormation here",
                ],
            },
            {
                "title": "Internal Observability Stack",
                "summary": "A self-hosted metrics and alerting stack.",
                "technologies": ["Kubernetes"],
                "concepts": ["Monitoring"],
                "interview_seeds": [],
            },
        ],
        "certifications": ["Certified Kubernetes Administrator (CKA)"],
        "predicted_domain": "DevOps / Cloud Infrastructure",
        "experience_level": "Senior",
        "confidence": 0.8,
        "resume_summary": "A DevOps candidate focused on infrastructure-as-code and CI/CD.",
        "interview_blueprint": {
            "resume_verification_topics": [],
            "technical_topics": [
                {
                    "topic": "Multi-region rollout and failure handling",
                    "originating_project": "Multi-Region Kubernetes Deployment Pipeline",
                    "originating_experience": "",
                    "evidence": "built a CI/CD pipeline deploying across multiple AWS regions",
                },
                {
                    "topic": "CI/CD ownership across teams",
                    "originating_project": "",
                    "originating_experience": "DevOps Engineer",
                    "evidence": "owned CI/CD and infrastructure-as-code for a multi-team platform",
                },
            ],
            "starting_difficulty": "advanced",
            "estimated_strengths": ["Strong grasp of infrastructure as code"],
            "estimated_weaknesses": ["Multi-Region Kubernetes Deployment Pipeline"],
        },
    }


def mobile_profile_dict() -> dict:
    return {
        "candidate_name": "Mobile Candidate",
        "contact_details": {"email": "mobile@example.com"},
        "skills": ["Swift", "SwiftUI", "Combine"],
        "education": [],
        "experience": [
            {
                "company": "Trailhead Apps",
                "role": "iOS Engineer",
                "duration": "2021-2024",
                "summary": "Built and shipped a consumer grocery-list app.",
            }
        ],
        "projects": [
            {
                "title": "Offline-First Grocery List App",
                "summary": "A grocery list app that works fully offline and syncs later.",
                "technologies": ["Swift", "SwiftUI", "Combine"],
                "concepts": ["Offline sync", "Local persistence"],
                "interview_seeds": [
                    "How conflicts are resolved when syncing offline changes",
                    "Why Combine over completion handlers for this app",
                ],
            },
            {
                "title": "App Store Release Automation",
                "summary": "Scripts automating the App Store release process.",
                "technologies": ["Swift"],
                "concepts": ["Release automation"],
                "interview_seeds": [],
            },
        ],
        "certifications": ["Apple Certified iOS App Developer"],
        "predicted_domain": "Mobile Engineering",
        "experience_level": "Intermediate",
        "confidence": 0.8,
        "resume_summary": "A mobile engineering candidate focused on offline-first apps.",
        "interview_blueprint": {
            "resume_verification_topics": [],
            "technical_topics": [
                {
                    "topic": "Offline sync conflict resolution",
                    "originating_project": "Offline-First Grocery List App",
                    "originating_experience": "",
                    "evidence": "built a grocery list app that syncs after working offline",
                },
                {
                    "topic": "Shipping and releasing an iOS app",
                    "originating_project": "",
                    "originating_experience": "iOS Engineer",
                    "evidence": "built and shipped a consumer grocery-list app",
                },
            ],
            "starting_difficulty": "intermediate",
            "estimated_strengths": ["Strong grasp of offline-first architecture"],
            "estimated_weaknesses": ["Offline-First Grocery List App"],
        },
    }


def all_experiment_profiles() -> tuple[dict, ...]:
    """The full set of profiles this experiment's pool is built from: the
    existing backend profile (`_planning_test_fixtures.sample_profile_dict`,
    reused rather than duplicated) plus the four domains defined here."""
    return (
        sample_profile_dict(),
        frontend_profile_dict(),
        data_ml_profile_dict(),
        devops_cloud_profile_dict(),
        mobile_profile_dict(),
    )
