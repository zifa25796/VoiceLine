# VoiceLine

Keep implementation simple and self-documenting. Comment only on non-obvious reasons; do not add docstrings unless requested. VoiceLine owns speech synthesis and its CLI; Daily HTTP adapters belong to POI. Do not track generated audio, databases, personal MCP settings, or binary distributions. Run `uv run python -m unittest discover -s tests -v` here, or use the parent POI environment. Play a short English VoiceLine completion/action notification, under ten words, without saving audio.
