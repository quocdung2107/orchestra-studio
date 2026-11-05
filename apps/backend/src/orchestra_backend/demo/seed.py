"""Demo Video Studio now comes from templates/company/demo-video-studio.yaml (ADR-0014)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from orchestra_backend.companies.models import Company
from orchestra_backend.templates_svc.service import instantiate_company

DEMO_TEMPLATE_ID = "demo-video-studio"


def seed_demo_company(session: Session, templates_dir: Path, known_runtimes: set[str]) -> Company:
    return instantiate_company(session, templates_dir, DEMO_TEMPLATE_ID, known_runtimes)
