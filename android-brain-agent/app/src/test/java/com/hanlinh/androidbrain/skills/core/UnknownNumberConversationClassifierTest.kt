package com.hanlinh.androidbrain.skills.core

import com.hanlinh.androidbrain.local.ContactMatch
import org.junit.Assert.assertEquals
import org.junit.Test

class UnknownNumberConversationClassifierTest {
    @Test fun visible_phone_number_absent_from_contacts_is_unknown_confirmed() {
        val classifier = UnknownNumberConversationClassifier { ContactMatch.NotSaved }

        assertEquals(
            ConversationClassification.UnknownConfirmed,
            classifier.classify("090 123 4567"),
        )
    }

    @Test fun saved_phone_number_is_kept() {
        val classifier = UnknownNumberConversationClassifier { ContactMatch.Saved }

        assertEquals(
            ConversationClassification.SavedContact,
            classifier.classify("+84 90 123 4567"),
        )
    }

    @Test fun names_and_alphanumeric_service_senders_are_never_called_unknown_numbers() {
        val classifier = UnknownNumberConversationClassifier { ContactMatch.NotSaved }

        assertEquals(ConversationClassification.NotPhoneNumber, classifier.classify("Mum"))
        assertEquals(ConversationClassification.NotPhoneNumber, classifier.classify("VM-BANK"))
    }

    @Test fun unavailable_contacts_permission_fails_closed() {
        val classifier = UnknownNumberConversationClassifier { ContactMatch.PermissionUnavailable }

        assertEquals(
            ConversationClassification.PermissionUnavailable,
            classifier.classify("0901234567"),
        )
    }
}
