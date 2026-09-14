package com.hanlinh.androidbrain.skills.core

import com.hanlinh.androidbrain.local.ContactMatch
import com.hanlinh.androidbrain.local.ContactsResolver
import com.hanlinh.androidbrain.local.PhoneNumberNormalizer

enum class ConversationClassification {
    UnknownConfirmed,
    SavedContact,
    NotPhoneNumber,
    PermissionUnavailable,
}

/**
 * A sender is unknown only when it is visibly phone-like and the local contacts
 * provider deterministically confirms that the normalized number is not saved.
 */
class UnknownNumberConversationClassifier(
    private val contactLookup: (String) -> ContactMatch,
) {
    constructor(resolver: ContactsResolver) : this(resolver::isSavedNumber)

    fun classify(sender: String): ConversationClassification {
        val normalized = PhoneNumberNormalizer.normalize(sender)
            ?: return ConversationClassification.NotPhoneNumber
        return when (contactLookup(normalized)) {
            ContactMatch.Saved -> ConversationClassification.SavedContact
            ContactMatch.NotSaved -> ConversationClassification.UnknownConfirmed
            ContactMatch.PermissionUnavailable -> ConversationClassification.PermissionUnavailable
        }
    }
}
