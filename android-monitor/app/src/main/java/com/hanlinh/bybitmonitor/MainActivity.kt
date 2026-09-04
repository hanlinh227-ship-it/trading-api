package com.hanlinh.bybitmonitor

import android.Manifest
import android.graphics.Color as AndroidColor
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.*
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.core.view.WindowCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.hanlinh.bybitmonitor.service.MonitorForegroundService
import com.hanlinh.bybitmonitor.ui.MonitorScreen
import com.hanlinh.bybitmonitor.ui.MonitorViewModel

private val baseTypography = Typography()
private val monoTypography = Typography(
    displayLarge = baseTypography.displayLarge.copy(fontFamily = FontFamily.Monospace),
    displayMedium = baseTypography.displayMedium.copy(fontFamily = FontFamily.Monospace),
    displaySmall = baseTypography.displaySmall.copy(fontFamily = FontFamily.Monospace),
    headlineLarge = baseTypography.headlineLarge.copy(fontFamily = FontFamily.Monospace),
    headlineMedium = baseTypography.headlineMedium.copy(fontFamily = FontFamily.Monospace),
    headlineSmall = baseTypography.headlineSmall.copy(fontFamily = FontFamily.Monospace),
    titleLarge = baseTypography.titleLarge.copy(fontFamily = FontFamily.Monospace),
    titleMedium = baseTypography.titleMedium.copy(fontFamily = FontFamily.Monospace),
    titleSmall = baseTypography.titleSmall.copy(fontFamily = FontFamily.Monospace),
    bodyLarge = baseTypography.bodyLarge.copy(fontFamily = FontFamily.Monospace),
    bodyMedium = baseTypography.bodyMedium.copy(fontFamily = FontFamily.Monospace),
    bodySmall = baseTypography.bodySmall.copy(fontFamily = FontFamily.Monospace),
    labelLarge = baseTypography.labelLarge.copy(fontFamily = FontFamily.Monospace),
    labelMedium = baseTypography.labelMedium.copy(fontFamily = FontFamily.Monospace),
    labelSmall = baseTypography.labelSmall.copy(fontFamily = FontFamily.Monospace)
)

private val terminalColors = darkColorScheme(
    primary = Color(0xFF00E5FF),
    onPrimary = Color(0xFF001417),
    secondary = Color(0xFF70FFB1),
    tertiary = Color(0xFFFFCC66),
    background = Color(0xFF030507),
    onBackground = Color(0xFFE8EEF2),
    surface = Color(0xFF080C10),
    onSurface = Color(0xFFE8EEF2),
    surfaceVariant = Color(0xFF0D141A),
    onSurfaceVariant = Color(0xFF9BB0BD),
    outline = Color(0xFF1E3945),
    error = Color(0xFFFF5C6C)
)

class MainActivity:ComponentActivity(){
    override fun onCreate(savedInstanceState:Bundle?){
        super.onCreate(savedInstanceState)
        window.statusBarColor=AndroidColor.BLACK
        window.navigationBarColor=AndroidColor.BLACK
        WindowCompat.getInsetsController(window,window.decorView).apply{
            isAppearanceLightStatusBars=false
            isAppearanceLightNavigationBars=false
        }
        setContent{
            val vm:MonitorViewModel=viewModel()
            val state by vm.state.collectAsState()
            var bg by remember{mutableStateOf(MonitorForegroundService.isEnabled(this))}
            val permission=rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()){}
            LaunchedEffect(Unit){if(Build.VERSION.SDK_INT>=33)permission.launch(Manifest.permission.POST_NOTIFICATIONS)}
            MaterialTheme(colorScheme=terminalColors,typography=monoTypography){
                MonitorScreen(state,vm::pair,vm::refresh,vm::disconnect,bg){on->
                    bg=on
                    MonitorForegroundService.setEnabled(this,on)
                }
            }
        }
    }
}
