"""
Certification gazetteer — Milestone 5 (Entity Parsing continued). See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

Used by `CertificationParser` to normalize certification name variants to
one canonical form, and to sweep Skills/Summary sections for stray
certification mentions not under a dedicated heading. A plain data file,
matching `technology_gazetteer.py`/`degree_gazetteer.py`'s precedent.
"""

from __future__ import annotations

CERTIFICATIONS: tuple[str, ...] = (
    "AWS Certified Solutions Architect", "AWS Certified Solutions Architect Associate",
    "AWS Certified Solutions Architect Professional", "AWS Certified Developer",
    "AWS Certified SysOps Administrator", "AWS Certified Cloud Practitioner",
    "AWS Certified DevOps Engineer", "AWS Certified Security Specialty",
    "Microsoft Certified: Azure Fundamentals", "Microsoft Certified: Azure Administrator",
    "Microsoft Certified: Azure Solutions Architect", "Azure Fundamentals", "Azure Administrator",
    "Google Cloud Professional Cloud Architect", "Google Cloud Associate Cloud Engineer",
    "Certified Kubernetes Administrator", "CKA", "Certified Kubernetes Application Developer", "CKAD",
    "Project Management Professional", "PMP", "Certified ScrumMaster", "CSM",
    "Professional Scrum Master", "PSM",
    "Certified Information Systems Security Professional", "CISSP",
    "Certified Ethical Hacker", "CEH", "CompTIA Security+", "CompTIA A+", "CompTIA Network+",
    "Cisco Certified Network Associate", "CCNA", "Cisco Certified Network Professional", "CCNP",
    "Certified Information Security Manager", "CISM",
    "Six Sigma Green Belt", "Six Sigma Black Belt",
    "Salesforce Certified Administrator", "Salesforce Certified Developer",
    "TensorFlow Developer Certificate", "Databricks Certified Data Engineer",
    "Oracle Certified Professional", "Red Hat Certified Engineer", "RHCE",
)
