"""Live CDE/ERP connectors (TS-333)."""

from app.modules.integrations.connectors.aconex import AconexConnector
from app.modules.integrations.connectors.autodesk import AutodeskConnector
from app.modules.integrations.connectors.base import BaseConnector
from app.modules.integrations.connectors.dynamic import DynamicRestConnector
from app.modules.integrations.connectors.erp import ERPConnector
from app.modules.integrations.connectors.procore import ProcoreConnector
from app.modules.integrations.connectors.sharepoint import SharePointConnector

CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {
    "procore": ProcoreConnector,
    "autodesk": AutodeskConnector,
    "aconex": AconexConnector,
    "sharepoint": SharePointConnector,
    "erp": ERPConnector,
    "dynamic": DynamicRestConnector,
}

__all__ = [
    "BaseConnector",
    "CONNECTOR_REGISTRY",
    "ProcoreConnector",
    "AutodeskConnector",
    "AconexConnector",
    "SharePointConnector",
    "ERPConnector",
]
