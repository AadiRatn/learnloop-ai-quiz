# LearnLoop demonstration guide

## Five-minute walkthrough

1. **Prepare:** load the sample notes, then show topic organization, question-count selection, and the saved generation job. With a valid Groq secret, generate live questions; without one, use the saved demo pack.
2. **Review:** compare a draft question with its source passage. Edit if needed and show that approval requires explicit confirmation.
3. **Practice:** start a full-pack quiz. Show that the answer key and explanations remain hidden until submission and that unanswered questions block submission.
4. **Progress:** show the score, topic breakdown, attempt history, and revision advice. Use **Weak topics** to demonstrate targeted practice.
5. **Export:** download progress as JSON. Explain that repeated questions in revision practice do not prove improvement on unseen questions.

## Questions to be ready for

**Where is GenAI used?** Groq-hosted Qwen drafts question wording, choices, explanations, and a source quote. Python handles validation, scoring, and topic summaries.

**Why require human review?** Automatic checks can verify structure and that evidence text appears in the source. They cannot guarantee semantic correctness or that only one answer is defensible.

**What is stored?** Jobs include study material; packs include source passages and reviewed questions; attempts retain the selected questions and scoring snapshot. Hosted app data is scoped to the browser session and is temporary.

**What are the limits?** PDF input requires selectable text. The 70% threshold is a transparent revision heuristic, not a diagnosis. Weak-topic practice reuses questions and does not measure transfer to unseen material.

**What remains for evaluation?** Test live generation and failure handling with the deployment's configured Groq key, then assess question quality on unseen notes with educator review. Do not present the saved demo score as a learning-outcome result.
