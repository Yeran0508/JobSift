JOB_INDEX_SETTINGS: dict[str, object] = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "analysis": {
        "filter": {
            "jobs_english_possessive": {
                "type": "stemmer",
                "language": "possessive_english",
            },
            "jobs_english_stop": {"type": "stop", "stopwords": "_english_"},
            "jobs_english_stemmer": {"type": "stemmer", "language": "english"},
            "jobs_tech_synonyms": {
                "type": "synonym_graph",
                "synonyms": [
                    "js, javascript",
                    "k8s, kubernetes",
                    "postgres, postgresql",
                ],
            },
        },
        "analyzer": {
            "jobs_index": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": [
                    "lowercase",
                    "asciifolding",
                    "jobs_english_possessive",
                    "jobs_english_stop",
                    "jobs_english_stemmer",
                ],
            },
            "jobs_search": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": [
                    "lowercase",
                    "asciifolding",
                    "jobs_tech_synonyms",
                    "jobs_english_possessive",
                    "jobs_english_stop",
                    "jobs_english_stemmer",
                ],
            },
        },
    },
}

_TEXT_WITH_KEYWORD = {
    "type": "text",
    "analyzer": "jobs_index",
    "search_analyzer": "jobs_search",
    "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
}

JOB_INDEX_MAPPINGS: dict[str, object] = {
    "dynamic": "strict",
    "properties": {
        "document_id": {"type": "keyword"},
        "source": {"type": "keyword"},
        "source_job_id": {"type": "keyword"},
        "content_fingerprint": {"type": "keyword"},
        "title": _TEXT_WITH_KEYWORD,
        "company": _TEXT_WITH_KEYWORD,
        "location": {"type": "keyword", "ignore_above": 512},
        "description": {
            "type": "text",
            "analyzer": "jobs_index",
            "search_analyzer": "jobs_search",
        },
        "url": {"type": "keyword", "index": False},
        "posted_at": {"type": "date"},
        "employment_type": {"type": "keyword"},
        "salary_min": {"type": "double"},
        "salary_max": {"type": "double"},
        "salary_currency": {"type": "keyword"},
        "salary_period": {"type": "keyword"},
        "skills": {"type": "keyword", "eager_global_ordinals": True},
        "organizations": {"type": "keyword"},
        "entity_locations": {"type": "keyword"},
        "acquired_at": {"type": "date"},
        "nlp_text_sha256": {"type": "keyword"},
        "nlp_model": {"type": "keyword"},
        "nlp_model_version": {"type": "keyword"},
        "skill_dictionary_version": {"type": "keyword"},
    },
}


def job_index_definition() -> dict[str, object]:
    return {"settings": JOB_INDEX_SETTINGS, "mappings": JOB_INDEX_MAPPINGS}
