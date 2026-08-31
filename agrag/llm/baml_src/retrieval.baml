function GenerateCypherQuery(question: string, schema_description: string) -> string {
  client GENERIC_TEXT2CYPHER
  prompt #"
    {{ _.role("system") }}
    Write one read-only Cypher query that answers the question, using only
    the labels and relationship types in schema_description.

    {{ _.role("user") }}
    Schema: {{ schema_description }}
    Question: {{ question }}

    {{ ctx.output_format }}
  "#
}
