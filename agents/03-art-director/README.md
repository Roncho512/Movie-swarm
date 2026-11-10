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

## Key Requirements

Read them from the production brief and the locked hero props. Do not copy another film's props or year into this agent. A character must stay recognizable. A hero prop must match its locked spec. Environment refs stay the same place as the light changes.

## Status

- [ ] Skill file written
- [ ] Character ref generation prompts tested
- [ ] Vehicle ref generation tested
- [ ] Prop ref generation tested
- [ ] Environment refs at 4 light conditions tested
- [ ] Style bible output validated against schema

## Build Order

Build FIRST (alongside Screenwriter). Every visual agent depends on this output.
