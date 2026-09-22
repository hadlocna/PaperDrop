# Learning games and creative thermal artwork

## Child experience

Wrong answers retain the same question and choices, disable the attempted wrong answer, and play gentle feedback followed by the exact question in the child's selected language. No star is removed. Correct answers play a short three-note sparkle followed by spoken praise; the next round starts automatically. Home cancels pending audio and progression.

Five stars save a personalized, numbered collectible achievement card. Space, garden, ocean and castle themes rotate, with a UUID-seeded character and decorations. A child chooses Print; nothing prints automatically. The latest card remains available under Games → My prize, including after restarting. Artwork and print IDs survive retries, so an uncertain print cannot be automatically duplicated. Cards are generated locally without waiting for an image API and use 576-pixel monochrome artwork.

Riddles offers 14 concrete and reasoning questions, four distinct illustrated answers, Repeat, and Home. English, French, German, Italian and European Portuguese labels and AI-generated Marin speech are included. The release pack contains 505 validated cached voice clips, including 85 new clips. The musical star cue is synthesized locally.

## Image model and art direction

The web Magic Image Creator already used `gpt-image-2.5-flare`. Official OpenAI documentation checked on 22 September 2026 lists it as the current fast, high-quality everyday image model in the GPT Image 2.5 family. The model is now a shared constant for web, recorded voice and realtime voice paths, retaining their existing quality settings. Sunburst is the higher-capability alternative; this change preserves the existing speed/cost choice rather than silently upgrading to that tier.

The shared parent prompt preserves the request's subjects, action, captions, language and format. It permits comics, maps, puzzles, diagrams, illustrated notes, cards and posters. Coloring-page style is optional. Small black accents, sparse hatching and stippling are allowed; dense black backgrounds, muddy gray, hairlines and unreadably small details are discouraged. White paper, monochrome contrast and legibility at 576 dots remain the physical constraints. The old assumptions that the sender is a father and every image is a gentle doodle are removed. The web image call now receives both the original request and the proposed layout; previously it dropped the layout.

References: https://developers.openai.com/api/docs/models/gpt-image-2.5-flare and https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst

## Validation

- 40 Stream Deck tests pass, including repeat-question audio ordering, no reward for mistakes, five chimes per win, unique/persistent cards, preview, explicit print and retry retention.
- 33 backend tests pass and the TypeScript production build passes. Web model selection, prompt/layout preservation, input validation and moderation are covered.
- All 505 required WAVs opened successfully with valid channels, sample width and nonempty audio. The star waveform and concatenated cue ordering are tested.
- One live call through the web creator's controller generated a three-panel fox/seed comic and the requested caption. The output and its 576-dot monochrome conversion were visually reviewed.
- Example reward artwork was visually reviewed. Printed paper and human confirmation of speaker intelligibility remain separate acceptance checks.
