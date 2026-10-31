# Output Language Pair Registry (Vendored Core Contract)

Source: [Academic Research Skills, output-language-pair contract](https://github.com/Imbad0202/academic-research-skills/blob/main/shared/output_language_pair.md). This bundled subset preserves the single currently referenced pair and its validation boundary. It does not install the upstream locale-pack loader or other shared research protocols.

| Token | First language (L1) | Script | Second language (L2) | Script | Status |
| --- | --- | --- | --- | --- | --- |
| `zh-tw-en` | Traditional Chinese (`zh-TW`) | CJK | English (`en`) | Latin | Default |

- Tokens are opaque registry keys. Never infer language order from a token's characters.
- An absent `output_language_pair` uses the default pair. An explicitly supplied unsupported, null, empty, or non-string token is a visible validation failure; it must not silently become the default.
- This setting selects the two abstract languages, not manuscript body language or the separate abstract-cardinality choice.
- The default entry preserves the legacy English/Chinese object keys and headings used by this bundled academic-paper skill.
- Abstract lengths and keyword counts remain in [the academic-paper abstract guide](abstract_writing_guide.md), not in this registry.
- No locale packs, additional language pairs or separate registry loader are bundled here. Other upstream shared contracts referenced by academic-paper remain external dependencies until individually audited and installed.
