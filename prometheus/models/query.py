from pydantic import BaseModel


class Query(BaseModel):
    essential_query: str
    extra_requirements: str
    purpose: str
