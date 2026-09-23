These are 768 px white-background copies of the eight portraits in
`agent/streamdeck/assets/portraits/`. The backend has its own copies because
the production service builds from `backend/`.

`src/services/cousinImages.ts` maps spoken names to these files. Keep that map
and this directory in sync with `agent/streamdeck/family.json` when a cousin or
portrait changes. Only portraits named in a drawing request are sent as image
references to the image edits API.
