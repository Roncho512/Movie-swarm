# Script Supervisor

The Script Supervisor checks shots and scenes against the locked hero props. The props and the phrases live in the production folder. This role does not know which film it is working on.

A continuity check is the file it writes before anyone generates a picture. It is not the QA report, which comes after a cut exists.

Run it through the Director, after the Prop Master has locked the props:

```bash
python3 scripts/director.py --production productions/the-last-marker --run first-film-1 --offline dispatch \
  --agent script-supervisor --crew-command check --estimate 0
```

The Line Producer checks the treatment gate and the screenwriter allocation. The estimate is not charged. The previs gate stays closed until Ron reviews the package.
