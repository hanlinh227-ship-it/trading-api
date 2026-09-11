# Skill: prompt_engineering

Covers image/video/agent prompts, negative constraints, prompt debugging, and optimization.

- Translate intent into explicit subject, environment, action, camera/composition, timing, style, and hard constraints.
- Put identity/count/geometry constraints before decorative language when consistency matters.
- State what must remain unchanged and what may change.
- Use positive operational instructions instead of long contradictory negative lists where possible.
- For video, describe one physically coherent action sequence per shot and avoid simultaneous impossible camera/subject motion.
- Debug generation failures by identifying which instruction caused ambiguity, not by blindly lengthening the prompt.
- Adapt wording to the target model/tool instead of assuming one universal prompt format.
