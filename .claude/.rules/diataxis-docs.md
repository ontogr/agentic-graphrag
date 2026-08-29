---
description: Write docs using Diátaxis: tutorials for learning, how-to guides for tasks, reference for facts, explanation for understanding
globs: *.mdx
---
# Diátaxis Documentation Framework

## What binds this repo

The rest of this file is generic Diátaxis reference. For `agrag` docs, apply
these points:

- Keep tutorials, how-to guides, reference, and explanation content separated
  where practical; link between modes instead of blending them into one page.
- Write concretely and concisely: prefer one precise sentence over a paragraph
  of generalities, and include real commands, data formats, or short snippets.
- Explain the why behind non-obvious design decisions and tradeoffs.
- User-facing docs live under `docs/`; update them when code behavior changes.

Use the sections below to identify which of the four modes a page belongs to.

## Prose style: ASD-STE100

User-facing prose (headings, paragraphs, list items, table cells — not code samples) follows
Simplified Technical English:

- One approved meaning per word on a given page.
- About 20 words or fewer per instruction sentence, about 25 for a description.
- Active voice; name the actor.
- One instruction per sentence; use a numbered list instead of "and."
- "Must" for a required action, "can" for an optional one.
- No stacked nouns: split "the vector store connection timeout setting" into
  "the timeout for the connection to the vector store."
- No vague verbs such as "handle" or "leverage"; name the real action.
- No slashes or ampersands in prose; write "or" and "and" in full.
- One idea per paragraph.

## Core Concept

The fundamental idea behind Diátaxis is that documentation needs fall into four distinct categories. Each category serves a different purpose and requires a different approach to writing. The framework is not just a list of types, but a systematic way to think about documentation.

## The Four Documentation Types

### 1. Tutorials
- **Definition**: A tutorial is a lesson that guides a learner through a practical experience
- **Core Purpose**: Skills acquisition through doing
- **Key Attributes**:
  - Always practical - the user must do something
  - Designed around a specific learning experience
  - Instructor takes responsibility for learner's success
  - Learning happens through action, not through being taught
- **Special Challenge**: The instructor must be "present" through written instruction alone
- **What to Avoid**:
  - Don't explain concepts in depth - link to explanations instead
  - Don't assume prior knowledge
  - Don't focus on options or alternatives
  - Don't include reference material
  - Don't show all possible ways to do something
- **Example**: Like a driving lesson - the goal is developing skills and confidence, not reaching a destination

### 2. How-to Guides
- **Definition**: Step-by-step guidance to achieve a specific goal
- **Core Purpose**: Practical problem solving
- **Key Attributes**:
  - Addresses a specific real-world task or problem
  - Written for users who know what they need to do
  - Focused on completing work rather than learning
  - Assumes necessary competence
- **What to Avoid**:
  - Don't teach basic concepts
  - Don't explain why things work
  - Don't cover every possible variation
  - Don't include detailed technical specifications
  - Don't focus on learning objectives
- **Examples**:
  - "How to store cellulose nitrate film"
  - "How to configure frame profiling"
  - "Troubleshooting deployment problems"

### 3. Reference
- **Definition**: Technical descriptions of the machinery
- **Core Purpose**: Information
- **Key Attributes**:
  - Contains pure technical facts
  - Must be accurate and complete
  - Structure mirrors the code/system architecture
  - Neutral and objective - like a map
  - Serves users who know what they're looking for
- **What to Avoid**:
  - Don't include tutorials or guides
  - Don't explain concepts
  - Don't include opinions or recommendations
  - Don't provide step-by-step instructions
  - Don't teach or guide the reader
  - Don't include best practices
- **Distinction**: Like a map that could be used by both a navigator plotting a course or a magistrate in a legal case

### 4. Explanation
- **Definition**: Discussion that clarifies and illuminates a particular topic
- **Core Purpose**: Understanding
- **Key Attributes**:
  - Provides background and context
  - Can take different approaches to a topic
  - May include opinions and alternative views
  - Connects different concepts
  - Answers "why" questions
- **What to Avoid**:
  - Don't include practical steps
  - Don't mix with tutorials
  - Don't focus on specific tasks
  - Don't include detailed technical specifications
  - Don't try to be completely objective
  - Don't include best practices
- **Important Note**: Should be separated from tutorials to avoid overloading learners

## The Diátaxis Map

The documentation types are arranged along two axes:

| Axis      | Practical                | Theoretical              |
|-----------|-------------------------|-------------------------|
| Learning  | Tutorials               | Explanation             |
| Work      | How-to Guides           | Reference              |

This creates natural tensions and relationships:
- Tutorials ↔ How-to guides (practical knowledge)
- Reference ↔ Explanation (theoretical knowledge)
- Tutorials ↔ Explanation (learning-oriented)
- How-to guides ↔ Reference (work-oriented)

## The Diátaxis Compass

Use this tool to identify documentation types:

| If content...    | ...and serves the user's... | Then it belongs in... |
|-----------------|---------------------------|---------------------|
| Guides action   | Learning                 | Tutorials           |
| Guides action   | Work                     | How-to guides       |
| Explains theory | Work                     | Reference          |
| Explains theory | Learning                 | Explanation        |

## Intentionally simple:

1. Look at your current documentation
2. Ask: "How could this be better?"
3. Choose ONE small improvement
4. Make that improvement
5. Repeat

## Key Principles

1. **Separation of Concerns**
   - Keep the four types distinct
   - Don't mix tutorials with explanation
   - Link between types instead of combining them

2. **Minimal Approach**
   - Start with small improvements
   - You don't need to read or understand everything
   - Each improvement suggests the next

3. **Pragmatic Usage**
   - Use what works for you
   - No need to commit to the entire framework
   - Even small improvements are valuable

4. **Concrete and concise writing**
   - State exactly what something does and why
   - Prefer one precise sentence over a paragraph of generalities
   - Include concrete examples, command invocations, data formats, or short code
     snippets when they help the reader act correctly
   - Explain the why behind non-obvious design decisions or tradeoffs
   - Use diagrams or short step-by-step flows for complex component interactions
   - Keep each document focused on a clear audience and purpose

## Important Notes

- The framework is a practical tool, not a theoretical construct
- You don't need to understand all of Diátaxis to start using it
- The documentation will naturally evolve as you make improvements
- Let real documentation problems guide your use of the framework

[Source: [Diátaxis Documentation Framework](https://diataxis.fr/start-here/)]
