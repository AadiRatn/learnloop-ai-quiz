# LearnLoop

**AI-powered quiz generation and learning progress**

LearnLoop turns study notes into multiple-choice questions, asks the learner to review generated questions, then provides locally scored practice and topic-level progress. Groq-hosted Qwen generates question drafts; the reviewed answer key is used for deterministic quiz scoring.

## Run locally

Use Python 3.10 or later:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

Set `GROQ_API_KEY` in the Streamlit secrets settings before generating questions. For local use, create `.streamlit/secrets.toml` with:

```toml
GROQ_API_KEY = "your-groq-api-key"
```

Never commit that file or share the key. On Streamlit Community Cloud, add the key under the app's **Settings → Secrets**. The repository intentionally does not include credentials.

## Deploy to Streamlit Community Cloud

Push this project to GitHub, create a Streamlit Community Cloud app from that repository, and set `app.py` as the entry point. Add `GROQ_API_KEY` in the app's **Settings → Secrets** before using live generation. Do not put the key in the repository or in a public issue. The live model is configured in `quiz_core.py` and may change as Groq updates its available models.

## Use LearnLoop

1. In **Prepare**, paste notes or upload a text-based PDF, set a title, and choose 3–12 questions.
2. Create a generation job, then generate questions with Groq.
3. In **Review**, check each draft against its source, edit if needed, and explicitly approve it.
4. In **Practice**, take a full-pack quiz or a weak-topics quiz. All questions must be answered before submission.
5. In **Progress**, review topic scores, revision suggestions, attempt history, and answer explanations. Export progress as JSON.

The **Load verified demo** button imports saved model output, so the review, quiz, and progress flows can be demonstrated without making an API call.

## Data and limitations

The app keeps work in SQLite for the current Streamlit browser session. On the hosted app, each visitor gets a separate session database; session data is temporary and is not intended as long-term storage. Local development can set `LEARNLOOP_DB` to choose a database path.

PDF ingestion requires selectable text; scanned PDFs need OCR first. Automated checks confirm that evidence text matches the source, but they cannot verify educational correctness. Human review is required before a question can be used in a quiz. Weak-topic analysis uses a 70% threshold and should be treated as revision guidance, not a diagnosis.

## Project files

| File | Responsibility |
|---|---|
| `app.py` | Four-page Streamlit interface |
| `quiz_core.py` | Notes/PDF ingestion, Groq generation, validation and scoring |
| `database.py` | SQLite jobs, packs, review and attempt snapshots |
| `sample_notes.md` | Original demo material across three topics |
| `demo_bundle.json` | Saved model output and reviewed demo edits for no-key demonstrations |
| `test_learnloop.py`, `verify_ui.py` | Core tests and complete scripted Streamlit workflow |
| `requirements.txt`, `requirements-dev.txt` | Runtime and verification dependencies |

## Verification

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest test_learnloop -v
python verify_ui.py
```

Tests use separate temporary databases. Core tests contain explicitly labelled synthetic fixtures; `verify_ui.py` uses the saved reviewed demo. No model call or API key is required to repeat these software checks. Testing live question generation requires a valid Groq key and network access.

## Limits

- This is an educational prototype, not a proctored exam system.
- Text checks prove that evidence phrases occur in the notes; they do not prove that the question has one correct answer or a sound explanation. Human review remains required.
- The model generates basic MCQs. It can repeat concepts or produce weak distractors. A new pack over identical notes may test the same facts.
- The 70% threshold and revision advice are deterministic, interpretable rules. They are not a trained learner-diagnosis model.
- A higher score on reused questions is not evidence of improved performance on unseen questions. The UI labels this limitation.
- PDF parsing requires selectable text. OCR, equation recognition, multilingual evaluation and handwriting are outside the tested scope. PDF topic grouping is coarser than explicit headings in pasted notes.
- The demo and prompt experiments are a small development set, not a general accuracy benchmark.
