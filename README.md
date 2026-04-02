# Space Fighter

Space Fighter is a fast arcade shooter built with Python and Pygame. You launch from the mission hangar, push through ten escalating sectors, collect refills and score boosts, and survive long enough to clear each level's objective.

## What The Project Includes

- 10 handcrafted campaign levels
- continuous threat spawning until each level reaches a real outcome
- standard combat waves plus boss sectors
- pickups for health, ammo, multishot, and score
- neon-styled menu, HUD, pause screen, and result screens
- keyboard and joystick input
- local progress and high-score saving through `save_data.json`

## Tech Stack

- Python 3.10+
- Pygame

Install the dependency with:

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

The game now launches in fullscreen and scales the `1200x800` play area to your display.

## Controls

### Keyboard

- `Arrow keys`: move
- `Space`: fire
- `P`: pause or resume
- `Esc`: leave the current run

### Joystick

- left stick or d-pad: move
- `A` / `button 0`: fire
- `Start` / `button 7`: pause or resume
- `B` / `button 1`: leave the current run

## Level Flow

- The game opens in the mission hangar.
- Only unlocked sectors can be launched.
- Standard sectors keep sending threats until the target score is reached.
- Boss sectors keep sending threats until the target score is reached, then the boss encounter begins.
- A run ends only when the player is destroyed or the current objective is cleared.

## Save Data

Progress is stored in `save_data.json`.

Tracked values:

- `highest_completed_level`
- `highest_unlocked_level`
- `high_score`

## Project Layout

- `main.py`: game loop, spawning, combat flow, HUD, level resolution
- `menu.py`: mission hangar and level selection frontend
- `functions.py`: music and result overlays
- `controls.py`: keyboard and joystick movement helpers
- `classes/`: player, enemies, bosses, campaign data, progress, effects, and frontend helpers
- `images/`: sprites and UI art
- `game_sounds/`: music and sound effects

## Notes

- Progress persists between launches.
- Menu visuals are regenerated each launch, but saved campaign progress stays intact.
- If audio or display setup fails, verify that Pygame is installed correctly and that your environment supports graphics and sound.
