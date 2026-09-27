# CodeXray

Python code analysis and similarity comparison with text, AST, fingerprint,
control-flow, and explainable approach signals.

## Run locally

Use Python 3.10 or newer:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

Connect this GitHub repository, choose the `main` branch, set `app.py` as the
main file, and deploy. Streamlit installs the packages listed in
`requirements.txt`.

The app works without CodeBERT. To enable optional semantic scoring, install
`torch` and `transformers`, then turn on the CodeBERT option in Compare or Batch;
the model downloads on first use. Invalid or incomplete Python is compared
using a clearly labeled source/token fallback, since AST and approach analysis
require valid syntax.
