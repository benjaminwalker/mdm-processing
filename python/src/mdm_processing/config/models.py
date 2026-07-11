import re
from enum import Enum

from pydantic import BaseModel, field_validator, model_validator

_TTL_PATTERN = re.compile(r"^P(?!$)(\d+Y)?(\d+M)?(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+S)?)?$")


class AttributeType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"


class AttributeDef(BaseModel):
    name: str
    type: AttributeType
    ttl: str | None = None

    @field_validator("ttl")
    @classmethod
    def validate_ttl(cls, value: str | None) -> str | None:
        if value is not None and not _TTL_PATTERN.match(value):
            raise ValueError(f"ttl must be an ISO 8601 duration, got {value!r}")
        return value


class CandidateKeys(BaseModel):
    match_strategy: str
    threshold: float
    attributes: list[str]

    @field_validator("threshold")
    @classmethod
    def validate_threshold(cls, value: float) -> float:
        if not 0.0 < value <= 1.0:
            raise ValueError(f"threshold must be in (0.0, 1.0], got {value}")
        return value


class EntityConfig(BaseModel):
    entity_type: str
    description: str
    natural_keys: list[str]
    candidate_keys: CandidateKeys | None = None
    attributes: list[AttributeDef]

    @model_validator(mode="after")
    def validate_key_references(self) -> "EntityConfig":
        attribute_names = {attribute.name for attribute in self.attributes}

        unknown_natural_keys = set(self.natural_keys) - attribute_names
        if unknown_natural_keys:
            raise ValueError(f"natural_keys reference unknown attributes: {sorted(unknown_natural_keys)}")

        if self.candidate_keys is not None:
            unknown_candidate_keys = set(self.candidate_keys.attributes) - attribute_names
            if unknown_candidate_keys:
                raise ValueError(
                    f"candidate_keys.attributes reference unknown attributes: {sorted(unknown_candidate_keys)}"
                )

        return self


class SourceChannelConfig(BaseModel):
    channel_code: str
    description: str
    precedence: int
    dedup_required: bool
    dedup_strategy: str | None = None

    @field_validator("precedence")
    @classmethod
    def validate_precedence(cls, value: int) -> int:
        if value < 1:
            raise ValueError(f"precedence must be >= 1, got {value}")
        return value

    @model_validator(mode="after")
    def validate_dedup_strategy(self) -> "SourceChannelConfig":
        if self.dedup_required and self.dedup_strategy is None:
            raise ValueError("dedup_strategy is required when dedup_required is true")
        return self
