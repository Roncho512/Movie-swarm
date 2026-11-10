# 04. Cinematographer (Shot Planning Agent)

Translates scenes into precise shot lists with generation prompts and tool routing.

## Role

- Read the scene manifest and visual style bible
- Produce a shot list for the entire film
- Write the generation prompt for each shot (this is the primary creative output)
- Route each shot to the optimal generation tool
- Identify multi-shot groups for batch generation (Seedance)
- Define reference assets needed for each generation call
- Note continuity requirements between adjacent shots

## Inputs

- Scene manifest (`scene-manifest.schema.json`)
- Visual style bible (`visual-style-bible.schema.json`)

## Outputs

- `shot-list.schema.json`

## Primary Tools

- Claude API (cinematic knowledge, tool capability matrix)

## Tool Routing Matrix

| Shot Type | Primary Tool | Rationale |
|---|---|---|
| Dialogue with lip sync | Veo 3.1 | Native audio, realistic faces |
| Multi-shot action sequence | Seedance 2.0 | Multi-reference, connected shots, joint audio |
| Stylized / artistic | Runway Gen-4.5 | Cinematic quality, style control |
| Rapid iteration / storyboard | Veo 3.1 Lite | Zero credits, fast turnaround |
| Standard coverage | Veo 3.1 Fast | Balance of quality and cost |

## Status

The program reads the production's look file and the approved treatment. It writes a camera package and a storyboard. It does not invent a look, and it does not generate images unless a caller passes an image client.

## Build Order

Run it through the Director, after Ron has approved the treatment. The previs gate stays closed until Ron reviews the package.
