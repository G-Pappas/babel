# Babel — a live Omarchy theme

Silhouette pixel-art workers build a monument brick by brick. When it's done, a
random disaster flattens it, and the survivors walk back in and start the next one.

- Monuments: pyramid, parthenon, skyscraper, eiffel, colosseum, taj-mahal, babel
- Disasters: kaiju, tsunami, meteor, tornado, earthquake, ufo
- One cycle ≈ 5 minutes (build 200s, admire 45s, disaster, cleanup 25s)
- Every monitor runs its own scene, on the layer below windows

## Install

    ./install.sh               # links babel/ into ~/.config/omarchy/themes, adds hooks
    omarchy theme set babel    # the hook starts the live layer; other themes stop it

## Develop

    babel/live/babel-live.py --window --speed 10           # preview in a window
    babel/live/babel-live.py --snapshot out.png --monument eiffel --disaster kaiju --at 9

Timings, palette and sizes are constants at the top of `babel-live.py`.
