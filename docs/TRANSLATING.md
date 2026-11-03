# Translating MirrorLab

MirrorLab speaks Spanish and English, in the desktop app and on the website. Fixing or
improving existing text is a one-file change. **Adding a third language is a real piece of work**
today, because both language switches are written for exactly two languages; open an issue first
so it can be planned.

## Improving the existing text

- **Desktop app:** [`src/mirrorlab/desktop/strings.py`](../src/mirrorlab/desktop/strings.py), one
  dictionary per language, keyed by identifiers such as `section.privacy`. Keep the keys and any
  `{placeholders}`. `pytest tests/test_desktop.py` fails if the two languages differ in keys.
  Run `python scripts/media/record_desktop.py --lang es` to see the result in the window.
- **Website:** [`web/src/lib/i18n.ts`](../web/src/lib/i18n.ts). The `Dict` type is derived from the
  Spanish dictionary, so TypeScript tells you if the English one drifts. Run `npm test` in `web/`.

## What adding a language involves

Desktop: add the code to `LANGUAGES`, a full dictionary, a case in `detect_language`, and replace
the two-way toggle in `window.py` with a cycle or a menu.

Website: extend `Lang` and `LANGS`, add the dictionary to `STRINGS`, handle it in `coerceLang`,
`nextLang`, `langFromPath` and `pathForLang` (for example `/fr/`), and teach `web/seo-plugin.ts`
about the new path so the page, canonical URL, `hreflang` entries and sitemap are generated.

A partial translation is welcome as a draft pull request.

## Guidelines

- Write natural interface text, not a word-for-word translation. Sentence case, plain verbs.
- Keep a button's name the same everywhere it appears.
- Do not translate command names, file names or the product name.
