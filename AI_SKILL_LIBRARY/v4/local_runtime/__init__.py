"""Personal AI federation local runtime plane.

Claude implementation lane for the Open Model Universe. Everything in this
package is *execution* machinery: model lifecycle, compute discovery,
hardware-aware placement, wake/sleep, priority admission.

It holds no routing authority. `task_router` selects the route, the Model Mesh
selects candidates, and this package only answers "can this candidate actually
run here, right now, and at what cost to the rest of the box".
"""
