# Skill: generative_media

Covers image generation/editing, video generation/editing, character consistency, scene continuity, camera direction, and storyboards.

- Preserve exact number and identity of required subjects; do not introduce unrequested characters/objects.
- Anchor persistent traits: face/body, clothing, product geometry, held objects, vehicle orientation, environment continuity, and screen direction.
- For video, define start state -> action -> end state and keep movement physically plausible.
- Use camera moves only when they add value; static or limited camera is preferable when generation stability is more important.
- Prevent continuity failures by explicitly fixing spatial relationships and what remains stationary.
- Use Runway when appropriate for generation/editing and to3D only when 3D conversion is genuinely required.
