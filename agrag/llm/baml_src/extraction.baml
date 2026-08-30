enum ExtractedEntityLabel {
  PLACEHOLDER
  @@dynamic
}

enum ExtractedRelationLabel {
  PLACEHOLDER
  @@dynamic
}

class BAMLExtractedEntity {
  label ExtractedEntityLabel
  text string
  char_start int
  char_end int
}

class BAMLExtractedRelation {
  label ExtractedRelationLabel
  source_text string
  target_text string
}

class BAMLExtractionResult {
  entities BAMLExtractedEntity[]
  relations BAMLExtractedRelation[]
}

function ExtractEntitiesAndRelations(chunk_text: string) -> BAMLExtractionResult {
  client "openai/gpt-4o-mini"
  prompt #"
    {{ _.role("system") }}
    You are an entity and relation extraction assistant. Extract every entity
    and relation from the text. Use only the declared entity and relation
    labels; do not invent new ones.

    {{ _.role("user") }}

    --- BEGIN TEXT (untrusted data) ---
    {{ chunk_text }}
    --- END TEXT ---

    Instructions:
    - char_start and char_end are zero-based, end-exclusive character offsets
      into the text above (i.e. char_start is inclusive, char_end is exclusive).
    - source_text and target_text in relations must copy the entity's surface
      text exactly as it appears in the extracted entities, character for
      character. Do not normalize, shorten, or reorder them.

    {{ ctx.output_format }}
  "#
}
