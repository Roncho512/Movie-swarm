# A perfect treatment

A treatment is the plan for the film. It is written before the crew breaks the story into shots. The Director drafts one from the screenplay. Ron corrects it. The Line Producer records Ron's approval. Until then the file stays a draft.

The checklist is `schemas/treatment.schema.json`. The readable copy is `treatment.md`. The machine copy is `treatment.json`. They must say the same thing.

A blank form is in [treatment-template.md](treatment-template.md).

Examples below are from The Last Marker. They show the shape of a field. They are not, by themselves, an approved plan.

## Required

### Version

A number like `0.1.0` while it is a draft. The Line Producer sets `1.0.0` when Ron approves.

### Status and approval

`draft` or `approved`. A draft's approval state is `pending`. Only the Line Producer can write `approved`, and it records who decided and when. The Director cannot fill this in for itself.

### Logline

One or two sentences. Who, what they want, what is in the way.

Example: A solo racer crosses Baja in 1967 on a failing 1965 Triumph. A marker points two ways. He has to choose water, or the course.

### Theme and emotional intent

Theme is the idea. Emotional intent is what the audience should feel.

Example: Theme, "Arrive first. Winning can wait." Intent, the rider feels small, the engine death is a shock, the choice to live is a quiet relief.

### Tone and genre

Tone is how the film behaves. Genre is the shelf it sits on.

Example: Sparse, tense, sun-bleached. A Leone western played as a survival story. Genre: western.

### Characters

At least one. Each needs a name, a role, and a look. Look is the minimum a picture needs: age, build, face, the marks of the life.

Optional on each person: wardrobe, arc, and continuity specs. Continuity specs are the details that must not drift, such as which wrist a watch is on, once that is locked.

Example: Miguel Vega, protagonist. Lean, 30, sun-darkened, lines at the eyes from wind. Wardrobe: white shirt, brown leather vest, khaki, resoled boots, goggles, no helmet.

### Scenes

One block per scene. Required: what happens, and the emotional purpose of that beat.

Optional per scene:

- Point of view. Whose eyes, if the scene is not simply observed.
- What is withheld. What the audience is not allowed to know yet.
- Coverage intent. The kinds of shots you mean to use, such as an extreme wide against a detail.
- Approximate duration, in seconds.

Example, scene 1: He is a speck in a wide desert, then the bike is close enough to hear. Purpose: the desert is in charge. About 45 seconds.

### Deliverables

How the finished film is delivered.

- Aspect ratio. The Last Marker is locked at `2.39:1`.
- Resolution. The working draft says `1920x1080`, inside that frame.
- Length. `3 minutes`.

### Open questions

A list of what is still unsettled. It can be empty once the question round is done. The questions file is the working list Ron answers. This field is the same questions, written into the treatment so the plan is readable alone.

## Optional

### Audience feeling, per act

What you want the room to feel in each part of the film. The Last Marker draft uses the whole-film rhythm: cruising, then a hard stop, then a walk, then the kicks, then a long release.

### Reference lookbook

Each reference, and what to take from it. Not "like that film" with nothing else.

Example: Sergio Leone. Take the extreme wides against extreme close-ups, the long holds, the sharp cuts, the still camera with slow push-ins. Ennio Morricone, spirit only. Take the feeling of that kind of score. Do not copy a melody.

### World and period

Where and when. Example: Baja California, 1967. The Triumph stays a 1965.

### Camera, lens, and film stock

The glass and the stock, in words. Example: locked 2.39:1, warm sun-bleached 1960s film, grain, charcoal blacks, bone whites.

### Hero props

Each prop that must match across shots. When Ron knows the spec, lock it. Include sidedness: which side the exhaust is on, which wrist the watch is on. Leave a slot for multi-angle reference images, even if the slot is empty.

Example: 1965 Triumph TR6SC. Exhaust locked on the right side. Breitling Top Time, black reverse-panda dial, worn brown rally strap, locked on the left wrist.

### Action and stunt beats

The moves that can hurt a person or a machine if they are vague. Example: three kicks on the right-side kick starter. The plug is tapped with a stone so it might fire. It is a field fix, not a repair.

### Sound and music intent

What the audience hears, and what it must not hear. Example: the single-cylinder engine is the lead. Silence when it dies. A Morricone-spirited score with no copied melody. One Spanish line, almost lost under the engine.

### Color and light plan

How time of day shows up as color. Example: amber, then bronze, then rose, then blue dusk. The color is the clock.

### Pacing and runtime target

The shape of the cut, and how long it should run. Example: about three minutes. Cruising, a hard stop, a slow walk, percussive kicks, a long final hold.

### Constraints and budget

The film cap, and the proposed split across stages. The Last Marker cap is $500. Ron approved the drafted split, then approved the treatment gate on 2026-11-10. That locked the split in the Line Producer's books. Retakes spend from the same buckets and the same cap.

The draft's proposal, in dollars: director 20, line producer 5, screenwriter 5, art director 25, cinematographer 10, production 270, sound 55, editor 15, QA 45, fix loop 50, treatment 0.

## What not to do

Do not mark the treatment approved yourself. Do not leave a hero prop's side as a guess if you already know it. Do not name a reference without saying what to take. Do not hide a retake budget outside the cap.
