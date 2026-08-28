function VerifyEntityMatch(
  entity_a: string,
  context_a: string,
  entity_b: string,
  context_b: string,
) -> bool {
  client "openai/gpt-4o-mini"
  prompt #"
    Decide whether these two mentions refer to the same real-world entity. If you
    are not confident, answer false.

    Mention A: {{ entity_a }}
    Context A: {{ context_a }}
    Mention B: {{ entity_b }}
    Context B: {{ context_b }}

    {{ ctx.output_format }}
  "#
}
