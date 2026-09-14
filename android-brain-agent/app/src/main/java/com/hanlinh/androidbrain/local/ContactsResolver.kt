package com.hanlinh.androidbrain.local

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.ContactsContract
import androidx.core.content.ContextCompat

sealed interface ContactMatch {
    data object Saved : ContactMatch
    data object NotSaved : ContactMatch
    data object PermissionUnavailable : ContactMatch
}

/** Resolves contact membership locally; no address-book content is uploaded. */
class ContactsResolver(private val context: Context) {
    fun isSavedNumber(number: String): ContactMatch {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) {
            return ContactMatch.PermissionUnavailable
        }

        val normalized = PhoneNumberNormalizer.normalize(number) ?: return ContactMatch.NotSaved
        return try {
            val uri = Uri.withAppendedPath(
                ContactsContract.PhoneLookup.CONTENT_FILTER_URI,
                Uri.encode(normalized),
            )
            context.contentResolver.query(
                uri,
                arrayOf(ContactsContract.PhoneLookup._ID),
                null,
                null,
                null,
            )?.use { cursor ->
                if (cursor.moveToFirst()) ContactMatch.Saved else ContactMatch.NotSaved
            } ?: ContactMatch.NotSaved
        } catch (_: SecurityException) {
            ContactMatch.PermissionUnavailable
        } catch (_: RuntimeException) {
            // OEM contact providers can fail; uncertain state must not be classified as unknown.
            ContactMatch.PermissionUnavailable
        }
    }
}
