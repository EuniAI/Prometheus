from pydantic import BaseModel


class RepositoryResponse(BaseModel):
    """
    Response model for a repository.
    """

    model_config = {
        "from_attributes": True,
    }

    id: int
    url: str
    commit_id: str | None
    is_working: bool
    user_id: int | None
    kg_max_ast_depth: int
    kg_chunk_size: int
    kg_chunk_overlap: int
