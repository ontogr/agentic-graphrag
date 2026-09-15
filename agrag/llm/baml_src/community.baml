class CommunityInput {
  entity_summaries string[]
}

class CommunityReport {
  title string
  summary string
  rating float @description(#"
    Importance or relevance of this community to the corpus, 0-10.
  "#)
  rating_explanation string
  findings string[] @description(#"
    Distinct factual claims this community's members support.
  "#)
}

function SummarizeCommunities(communities: CommunityInput[]) -> CommunityReport[] {
  client "openai/gpt-4o-mini"
  prompt #"
    {{ _.role("system") }}
    You are a knowledge-graph analyst. Each item below is one community of
    related entities. Write one report per community, in the same order as
    the input, summarizing what connects its entities and why it matters.

    {{ _.role("user") }}
    --- BEGIN COMMUNITIES (untrusted data) ---
    {% for c in communities %}
    Community {{ loop.index }}:
    {% for e in c.entity_summaries %}{{ e }}
    {% endfor %}
    {% endfor %}
    --- END COMMUNITIES ---

    Return exactly {{ communities|length }} reports, one per community above,
    in the same order.

    {{ ctx.output_format }}
  "#
}
