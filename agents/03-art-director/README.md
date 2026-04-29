# 03. Art Director (Visual Design Agent)

Establishes the visual language. The consistency anchor for the entire production.

## Role

- Generate character reference sheets (8-10 images per character, multi-angle)
- Generate vehicle reference sheets
- Generate prop reference sheets (for items requiring cross-shot consistency)
- Generate environment reference images (key locations at different times of day)
- Define the color system and lighting rules
- Produce the visual style bible that every visual agent references

## Inputs

- Scene manifest (`scene-manifest.schema.json`)
- Production brief (style directives)

## Outputs

- `visual-style-bible.schema.json`
- Reference image files in `visual-assets/`

## Primary Tools

- ChatGPT Images 2.0 (character refs — up to 8 images per prompt, facial consistency, 2K)
- Google Flow / Nano Banana Pro (video-ready refs that feed directly into Veo)

## Secondary Tools

- Midjourney (stylized concept art, mood boards)

## Key Requirements for The Last Marker

- Miguel Vega must be recognizable across all 25 shots
- The 1965 Triumph TR6SC must be visually consistent (single cylinder, right-side exhaust, distinct tank shape)
- The Breitling Top Time must be identifiable in 3 shots across 3 scenes (black reverse panda dial, worn brown leather rally strap)
- Four distinct lighting conditions need style frames (amber → bronze → rose → blue dusk)
- Desert environment refs showing the same mountain range at different times of day

## Status

- [ ] Skill file written
- [ ] Character ref generation prompts tested
- [ ] Vehicle ref generation tested
- [ ] Prop ref generation tested
- [ ] Environment refs at 4 light conditions tested
- [ ] Style bible output validated against schema

## Build Order

Build FIRST (alongside Screenwriter). Every visual agent depends on this output.
