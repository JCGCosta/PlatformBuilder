from pydantic import BaseModel
from typing import List, Any

class ProjectInfo(BaseModel):
    name: str
    dir_path: str 

class ProjectSchema(BaseModel):
    project_info: ProjectInfo
    concepts_sources: List[Any] = []
    active_concepts: List[Any] = []
    connections: List[Any] = []