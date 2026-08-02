from pydantic import BaseModel, Field


class GithubImportRequest(BaseModel):
    url: str = Field(..., description="https://github.com/<owner>/<repo>")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
