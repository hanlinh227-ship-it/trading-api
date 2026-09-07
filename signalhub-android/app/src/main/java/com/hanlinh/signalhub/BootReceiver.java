package com.hanlinh.signalhub;

import android.Manifest;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;

public class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) return;

        boolean enabled = context.getSharedPreferences("signalhub", Context.MODE_PRIVATE)
                .getBoolean("monitoring", false);
        if (!enabled) return;

        if (Build.VERSION.SDK_INT >= 33 &&
                context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            context.getSharedPreferences("signalhub", Context.MODE_PRIVATE)
                    .edit().putBoolean("monitoring", false).apply();
            return;
        }

        try {
            Intent service = new Intent(context, MonitorService.class);
            if (Build.VERSION.SDK_INT >= 26) context.startForegroundService(service);
            else context.startService(service);
        } catch (Throwable ignored) {
            // Some Android/OEM builds reject background FGS starts after reboot.
            // Fail closed instead of crashing the app process. Opening SignalHub
            // later will start the monitor again while the app is foregrounded.
            context.getSharedPreferences("signalhub", Context.MODE_PRIVATE)
                    .edit().putBoolean("monitoring", false).apply();
        }
    }
}
