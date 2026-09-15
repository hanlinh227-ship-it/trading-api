# Animation-Safe Video Prompt Design

## Goal

Strengthen the existing canonical `video_prompt` skill so AI animation/video prompt requests produce motion instructions with lower ambiguity and lower risk of continuity, anatomy, direction, contact, object-permanence, vehicle-orientation, and camera-motion failures. This change must not create a competing primary skill or alter the generic `animation` trigger owned by the 3D design domain.

## Authority and scope

- Canonical primary reasoning skill remains `video_prompt` in the `prompt_media` domain.
- `scene_continuity`, `camera_direction`, `character_consistency`, `negative_constraints`, and `prompt_debugging` remain separate canonical skills with their existing trigger ownership.
- The generic trigger `animation` remains owned by the 3D `animation` skill.
- `video_prompt` may own specific generative-video intents such as `animation prompt`, `image to video prompt`, and `i2v prompt` because those do not replace the generic 3D animation intent.
- No new primary skill, provider, permission, local runtime dependency, or parallel reasoning authority is introduced.

## Animation safety contract

Before final wording, `video_prompt` must reason over a compact shot state and preserve the following invariants when material:

1. **Subject count and identity** — no silent cloning, removal, wardrobe/shape mutation, or identity swap.
2. **Action ownership** — every meaningful action has an unambiguous actor/object owner.
3. **Start state** — initial pose, position, orientation, held objects, contacts, and relevant spatial relationships are explicit or inherited from a supplied reference frame.
4. **End state** — the shot finishes in a physically and temporally compatible state.
5. **Contact continuity** — hands, feet, seats, tools, props, doors, wheels, and other contacts remain attached/released only when the action explicitly changes the contact.
6. **Trajectory** — moving subjects/objects have a coherent path; no teleporting or spontaneous reversal.
7. **Screen direction** — left/right travel and vehicle orientation remain consistent unless a visible turn/reversal is requested.
8. **Timing and spacing** — acceleration/deceleration and action timing are plausible for the subject and duration.
9. **Arcs and body mechanics** — locomotion and gestures respect plausible body mechanics and support/weight transfer.
10. **Camera ownership** — distinguish subject motion from camera motion; avoid instructions whose apparent motion could be attributed to both without clarification.
11. **Object permanence/environment reaction** — props, vehicles, scenery, and relevant secondary motion persist and react causally rather than morphing or moving independently.
12. **Continuity handoff** — the end state is compatible with supplied start/end frames or adjacent-scene continuity facts.

## Motion budget

Default to one continuous temporal event per generated shot:

- one dominant action per principal subject;
- one coherent interaction chain;
- zero or one major camera move;
- no unnecessary simultaneous scene/style transitions.

When the requested shot exceeds this budget or contains material contradictions, simplify the movement while preserving intent or split it into multiple shots instead of producing an internally inconsistent prompt.

## Input modes

### Text-to-video

Describe subject state, primary action, environment motion, camera behavior, and end state with enough visual context for generation.

### Image-to-video

Treat the input/reference frame as authoritative for appearance, composition, identity, count, orientation, props, and spatial layout unless the user explicitly changes them. Focus prompt wording on motion and temporal change rather than redundantly re-describing the still image.

### Start/end frame interpolation

Treat both frames as hard boundary states. The requested motion must provide a plausible transition between them without adding intermediate mutations that contradict either boundary.

## Internal forbidden states vs provider wording

Maintain internal invariants as hard checks, but do not blindly emit a universal long negative list. Adapt wording to the target model/provider while preserving meaning.

Examples:

- Internal: `FORBID vehicle_orientation_flip`
- Positive provider wording: `The car maintains the same forward-facing orientation throughout the shot.`

- Internal: `FORBID camera_motion`
- Positive provider wording: `Locked camera. The camera remains stationary throughout the shot.`

Negative wording may still be used when the target model explicitly benefits from it, but provider style never weakens the invariant itself.

## Provider/model adaptation

Provider guidance is an adapter, not reasoning authority.

- **Runway-family behavior:** concise, motion-first, positive operational wording, minimal re-description for image-to-video, explicit identity/location labels when multiple subjects act differently.
- **LTX-family behavior:** chronological literal action sequence, explicit temporal order, cinematography phrased as a coherent shot.
- **Hunyuan-family behavior:** preserve semantic/state locks before decorative prompt expansion; fidelity-preserving rewrite is preferred when enhancement risks dropping constraints.
- **Wan-family behavior:** richer cinematic movement is allowed only after state, trajectory, contact, direction, and camera constraints are fixed.
- **Generic fallback:** concise chronological wording with the full safety contract preserved.

No provider adapter may claim deterministic render fidelity.

## Prompt compilation order

Internally reason in this order, then compile to natural render-ready prose:

1. reference/identity lock;
2. start state;
3. primary action and actor ownership;
4. contact/trajectory/body mechanics/physics;
5. camera and screen direction;
6. environment/secondary motion;
7. end state;
8. continuity locks;
9. model-specific wording/minification.

The user-facing prompt should not expose internal metadata unless requested.

## Routing

Add exact specialist triggers to `video_prompt` without taking the generic 3D animation trigger:

- `animation prompt`
- `image to video prompt`
- `i2v prompt`

Trigger ownership must remain unambiguous under the Skill Gateway compiler.

## Regression evaluation

The implementation must include a configuration-level regression test that fails before the canonical skill contract is strengthened and passes only when the required animation-safety semantics are present.

Representative cases for future prompt-quality evaluation:

- E01 single character walking;
- E02 hand picks up an object;
- E03 two characters perform different actions;
- E04 character enters/exits a vehicle;
- E05 two vehicles travel in opposite directions;
- E06 rolling/falling ball;
- E07 character holds a persistent prop;
- E08 static camera plus moving subject;
- E09 tracking camera plus moving subject;
- E10 start/end-frame transition;
- E11 crowded scene;
- E12 requested transformation;
- E13 anthropomorphic-animal anatomy;
- E14 child-safe cartoon locomotion;
- E15 deliberately contradictory motion request.

Evaluation dimensions: identity, count, anatomy, object permanence, contact, direction, trajectory, physics, camera ownership, continuity, prompt simplicity, and model compatibility.

## Open-source/reference intake

External repositories and official prompting guides are reference/evidence only. No code reuse or runtime dependency is required. Reference candidates should record provenance/license/maintenance state and remain non-authoritative.

Reference patterns used for this design include AnimateDiff/SparseCtrl motion-control concepts, LTX-Video chronological prompting, Wan video-generation motion behavior, provider prompting guidance, and classical animation/body-mechanics concepts. All imported guidance remains subordinate to repository authority, current project constraints, and the canonical skill contract.

## Success criteria

- `video_prompt` remains the sole canonical primary skill for generative video prompting.
- `animation` remains owned by the 3D animation skill.
- Specific animation-prompt/I2V intents route to `video_prompt` without trigger collision.
- The compiled `video_prompt` execution capsule contains the strengthened animation-safety output contract.
- Regression tests demonstrate RED before the contract change and GREEN after it.
- Existing router/registry/release/retrieval/consolidation invariants remain green.
- No permission expansion, skill-count growth, mandatory local dependency, or false guarantee is introduced.
