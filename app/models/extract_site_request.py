from pydantic import BaseModel, Field, HttpUrl


class ExtractSiteRequest(BaseModel):
    url: HttpUrl
    max_pages: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of pages to extract (1–50).",
    )
