from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from jobsift.processing.models import CleanJobPosting


class EntityKind(StrEnum):
    ORGANIZATION = "organization"
    LOCATION = "location"


class SkillEntry(BaseModel):
    canonical: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)


class SkillDictionary(BaseModel):
    version: str = Field(min_length=1)
    entries: list[SkillEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_phrases(self) -> "SkillDictionary":
        owners: dict[str, str] = {}
        for entry in self.entries:
            phrases = [entry.canonical, *entry.aliases]
            for phrase in phrases:
                normalized = " ".join(phrase.split()).casefold()
                if not normalized:
                    raise ValueError("skill phrases must contain a visible character")
                owner = owners.get(normalized)
                if owner is not None:
                    raise ValueError(
                        f"skill phrase {phrase!r} is shared by {owner!r} and {entry.canonical!r}"
                    )
                owners[normalized] = entry.canonical
        return self


class ExtractedEntity(BaseModel):
    text: str
    normalized: str
    kind: EntityKind
    spacy_label: str
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)


class SkillMatch(BaseModel):
    canonical: str
    matched_text: str
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)
    dictionary_version: str


class EnrichedJobPosting(BaseModel):
    clean: CleanJobPosting
    nlp_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    organizations: list[ExtractedEntity]
    locations: list[ExtractedEntity]
    skills: list[SkillMatch]


class EnrichmentReport(BaseModel):
    input_rows: int = Field(ge=0)
    output_rows: int = Field(ge=0)
    model_name: str
    model_version: str
    dictionary_version: str
    dictionary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    organizations_total: int = Field(ge=0)
    locations_total: int = Field(ge=0)
    skills_total: int = Field(ge=0)
    jobs: list[EnrichedJobPosting]
