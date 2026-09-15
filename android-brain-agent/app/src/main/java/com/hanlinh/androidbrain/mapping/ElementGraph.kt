package com.hanlinh.androidbrain.mapping

data class RelativeBounds(
    val left: Double,
    val top: Double,
    val right: Double,
    val bottom: Double,
) {
    init {
        require(left in 0.0..1.0 && top in 0.0..1.0 && right in 0.0..1.0 && bottom in 0.0..1.0)
        require(right >= left && bottom >= top)
    }
}

data class ElementDescriptor(
    val elementId: String,
    val semanticRole: String? = null,
    val resourceIds: Set<String> = emptySet(),
    val textAnchors: Set<String> = emptySet(),
    val contentDescriptionAnchors: Set<String> = emptySet(),
    val relativeBounds: RelativeBounds? = null,
    val visualAnchors: Set<String> = emptySet(),
    val supportedActions: Set<String> = emptySet(),
    val confidence: Double,
    val staleScore: Double = 0.0,
) {
    init {
        require(elementId.isNotBlank())
        require(confidence in 0.0..1.0)
        require(staleScore in 0.0..1.0)
    }
}

class ElementGraph {
    private val elements = linkedMapOf<String, ElementDescriptor>()
    @Synchronized fun put(element: ElementDescriptor) { elements[element.elementId] = element }
    @Synchronized fun get(elementId: String): ElementDescriptor? = elements[elementId]
    @Synchronized fun all(): List<ElementDescriptor> = elements.values.toList()
}
