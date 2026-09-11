# Skill: game_dev

Covers game design, gameplay systems, Godot, Unity, web games, game AI, level design, 2D/3D games, and optimization.

- Start from core loop, player objective, controls, feedback, failure/reward states, and target platform.
- Separate gameplay rules, presentation, persistence, and engine-specific integration.
- Prefer deterministic/state-driven logic for mechanics that need reliable testing.
- For AI/NPC systems, define perception, state/decision model, navigation, actions, and recovery from invalid states.
- Profile before optimizing; distinguish CPU, GPU, memory, draw-call, physics, and asset bottlenecks.
- Use engine-specific references only after the game route selects the relevant engine/context.
