// Retry policy attached to every dynamically registered ClientRegistry client.
//
// Values must match agrag.llm.client_config.RetryConfig's defaults. BAML retry_policy
// blocks are static and cannot read env vars for numeric fields, so this policy cannot
// reflect a non-default RetryConfig; build_client_registry rejects those explicitly.
retry_policy AgragDefaultRetry {
  max_retries 3
  strategy {
    type exponential_backoff
    delay_ms 200
    multiplier 1.5
    max_delay_ms 10000
  }
}
