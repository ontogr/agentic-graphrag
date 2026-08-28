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
    Extract every entity and relation from the text below. Use only the declared
    entity and relation labels; do not invent new ones.

    {{ _.role("user") }}
    {{ chunk_text }}

    {{ ctx.output_format }}
  "#
}
