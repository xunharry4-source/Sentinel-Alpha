from __future__ import annotations

from sentinel_alpha.api.app import create_app
from sentinel_alpha.api.persistent_workflow_service import PersistentWorkflowService

app = create_app(PersistentWorkflowService())
