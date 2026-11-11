from hashlib import sha256
from pathlib import Path

import spacy
from spacy.language import Language
from spacy.matcher import PhraseMatcher
from spacy.tokens import Doc

from jobsift.processing.enrichment_models import (
    EnrichedJobPosting,
    EnrichmentReport,
    EntityKind,
    ExtractedEntity,
    SkillDictionary,
    SkillMatch,
)
from jobsift.processing.models import CleanJobPosting

_ORGANIZATION_LABELS = {"ORG"}
_LOCATION_LABELS = {"GPE", "LOC", "FAC"}


def load_skill_dictionary(path: Path) -> SkillDictionary:
    return SkillDictionary.model_validate_json(path.read_text())


class SpacyJobEnricher:
    def __init__(
        self,
        nlp: Language,
        dictionary: SkillDictionary,
        *,
        batch_size: int = 64,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least one")
        if not {"ner", "entity_ruler"}.intersection(nlp.pipe_names):
            raise ValueError("spaCy pipeline must provide ner or entity_ruler")
        self._nlp = nlp
        self._dictionary = dictionary
        self._batch_size = batch_size
        self._model_name = str(nlp.meta.get("name") or nlp.lang)
        self._model_version = str(nlp.meta.get("version") or "unknown")
        self._dictionary_sha256 = sha256(
            dictionary.model_dump_json().encode()
        ).hexdigest()
        self._matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
        for entry in dictionary.entries:
            phrases = [entry.canonical, *entry.aliases]
            self._matcher.add(entry.canonical, [nlp.make_doc(phrase) for phrase in phrases])

    @classmethod
    def from_model(
        cls,
        dictionary: SkillDictionary,
        *,
        model_name: str = "en_core_web_sm",
        batch_size: int = 64,
    ) -> "SpacyJobEnricher":
        return cls(spacy.load(model_name), dictionary, batch_size=batch_size)

    def enrich(self, clean_jobs: list[CleanJobPosting]) -> EnrichmentReport:
        texts = [self._job_text(job) for job in clean_jobs]
        documents = self._nlp.pipe(texts, batch_size=self._batch_size)
        enriched = [
            self._enrich_job(job, text, document)
            for job, text, document in zip(clean_jobs, texts, documents, strict=True)
        ]
        return EnrichmentReport(
            input_rows=len(clean_jobs),
            output_rows=len(enriched),
            model_name=self._model_name,
            model_version=self._model_version,
            dictionary_version=self._dictionary.version,
            dictionary_sha256=self._dictionary_sha256,
            organizations_total=sum(len(job.organizations) for job in enriched),
            locations_total=sum(len(job.locations) for job in enriched),
            skills_total=sum(len(job.skills) for job in enriched),
            jobs=enriched,
        )

    @staticmethod
    def _job_text(job: CleanJobPosting) -> str:
        fields = (job.title, job.company, job.location, job.description)
        return "\n".join(value for value in fields if value and value != "Unknown")

    def _enrich_job(
        self,
        job: CleanJobPosting,
        text: str,
        document: Doc,
    ) -> EnrichedJobPosting:
        organizations = self._entities(document, _ORGANIZATION_LABELS, EntityKind.ORGANIZATION)
        locations = self._entities(document, _LOCATION_LABELS, EntityKind.LOCATION)
        skills = self._skills(document)
        return EnrichedJobPosting(
            clean=job,
            nlp_text_sha256=sha256(text.encode()).hexdigest(),
            organizations=organizations,
            locations=locations,
            skills=skills,
        )

    @staticmethod
    def _entities(
        document: Doc,
        accepted_labels: set[str],
        kind: EntityKind,
    ) -> list[ExtractedEntity]:
        entities: list[ExtractedEntity] = []
        seen: set[str] = set()
        for entity in document.ents:
            normalized = " ".join(entity.text.split()).casefold()
            if entity.label_ not in accepted_labels or normalized in seen:
                continue
            seen.add(normalized)
            entities.append(
                ExtractedEntity(
                    text=entity.text,
                    normalized=normalized,
                    kind=kind,
                    spacy_label=entity.label_,
                    start_char=entity.start_char,
                    end_char=entity.end_char,
                )
            )
        return entities

    def _skills(self, document: Doc) -> list[SkillMatch]:
        matches = sorted(self._matcher(document), key=lambda match: (match[1], match[2]))
        skills: list[SkillMatch] = []
        seen: set[str] = set()
        for match_id, start, end in matches:
            canonical = self._nlp.vocab.strings[match_id]
            if canonical in seen:
                continue
            seen.add(canonical)
            span = document[start:end]
            skills.append(
                SkillMatch(
                    canonical=canonical,
                    matched_text=span.text,
                    start_char=span.start_char,
                    end_char=span.end_char,
                    dictionary_version=self._dictionary.version,
                )
            )
        return skills
