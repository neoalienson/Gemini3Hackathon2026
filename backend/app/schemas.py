from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from .models import DataSourceType, DataSourceStatus, ResourceType, Permission

# DataSource Schemas
class DataSourceBase(BaseModel):
    name: str
    type: DataSourceType
    host: str
    port: int
    database: str
    username: str
    project_id: Optional[str] = None
    dataset: Optional[str] = None
    location: Optional[str] = None

class DataSourceCreate(DataSourceBase):
    password: Optional[str] = None

class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    status: Optional[DataSourceStatus] = None
    project_id: Optional[str] = None
    dataset: Optional[str] = None
    location: Optional[str] = None

class DataSourceResponse(DataSourceBase):
    id: str
    status: DataSourceStatus
    last_sync: Optional[datetime] = None
    
    model_config = {"from_attributes": True}

# Table Schemas
class ColumnSchema(BaseModel):
    name: str
    type: str
    primary_key: Optional[bool] = False
    foreign_key: Optional[Dict[str, str]] = None
    description: Optional[str] = None

class TableSchema(BaseModel):
    name: str
    # In Pydantic v2, we can use `schema` directly, but keeping alias for API compatibility
    schema_name: Optional[str] = Field(None, alias="schema")
    columns: List[ColumnSchema]
    row_count: int
    description: Optional[str] = None

    model_config = {"populate_by_name": True}

# DataCube Schemas
class DataCubeBase(BaseModel):
    name: str
    description: str
    query: str
    data_source_id: str = Field(..., alias="dataSourceId")  # Accept camelCase from frontend, store as snake_case
    dimensions: List[str]
    measures: List[str]
    metadata: Optional[Dict[str, Any]] = None
    
    model_config = {"populate_by_name": True}

class DataCubeCreate(DataCubeBase):
    pass

class DataCubeUpdate(DataCubeBase):
    pass

class DataCubeResponse(DataCubeBase):
    id: str
    createdAt: str
    
    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "cube-123",
                "name": "Sales Cube",
                "description": "Sales data",
                "query": "SELECT * FROM sales",
                "dataSourceId": "source-123",
                "dimensions": ["region", "date"],
                "measures": ["sales", "revenue"],
                "metadata": {},
                "createdAt": "2026-01-27T00:00:00"
            }
        }
    }

class DataCubeQuery(BaseModel):
    query: str

class DataCubeQueryResponse(BaseModel):
    data: List[Dict[str, Any]]
    columns: List[str]

class DataCubeGenerateRequest(BaseModel):
    user_request: str
    data_source_id: str

class DataCubeGenerateResponse(BaseModel):
    name: str
    description: str
    query: str
    dimensions: List[str]
    measures: List[str]
    metadata: Optional[Dict[str, Any]] = None

class SqlPreviewRequest(BaseModel):
    sql: str
    max_rows: int = 5

class SqlPreviewResponse(BaseModel):
    rows: List[Dict[str, Any]]
    columns: List[str]

class DataCubePreviewRequest(BaseModel):
    limit: int = 20
    offset: int = 0

# Dashboard Schemas
class WidgetSchema(BaseModel):
    id: str
    type: str
    title: str
    config: Dict[str, Any]
    x: int
    y: int
    width: int
    height: int

class DashboardBase(BaseModel):
    name: str
    description: str
    data_cube_id: str
    widgets: List[WidgetSchema]

class DashboardCreate(DashboardBase):
    pass

class DashboardResponse(DashboardBase):
    id: str
    createdAt: str
    updatedAt: str
    
    model_config = {"from_attributes": True}

# Data Entitlement Schemas
class DataEntitlementBase(BaseModel):
    user_id: str
    resource_type: ResourceType
    resource_id: str
    permissions: List[Permission]
    granted_by: str

class DataEntitlementCreate(DataEntitlementBase):
    pass

class EntitledResource(BaseModel):
    resourceType: ResourceType
    resourceId: str
    resourceName: str
    permissions: List[Permission]
    grantedAt: str

# App Config Schemas
class AppConfigBase(BaseModel):
    key: str
    value: Optional[str] = None
    description: Optional[str] = None

class AppConfigCreate(AppConfigBase):
    pass

class AppConfigResponse(AppConfigBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}

# Data Marketplace Response
class DataMarketplaceResponse(BaseModel):
    dataSources: List[DataSourceResponse]
    dataCubes: List[DataCubeResponse]
    dashboards: List[DashboardResponse]

# AI Chat Schemas
class AIChatMessage(BaseModel):
    message: str

class AIChatResponse(BaseModel):
    response: str
    timestamp: str

# Insight Exploration (ADK agent) Schemas
class InsightExplorationQuery(BaseModel):
    query: str

class InsightExplorationResponse(BaseModel):
    content: str
